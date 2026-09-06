from pathlib import Path

import bb_windows
import bbtool.app.app_server as app_server
import bbtool.app.first_run as first_run
import bbtool.app.main as app_main
from bbtool.app.archetype_catalog import ArchetypeCatalogStore
from bbtool.app.config import load_config
from bbtool.app.first_run import (
    default_battle_brothers_quicksave,
    initialize_first_run_save_default,
)
from bbtool.app.local_application import LocalApplication
from bbtool.app.user_state import PreferencesState, UserStateStore


ROOT = Path(__file__).resolve().parents[2]


def make_application(state_root: Path) -> LocalApplication:
    config = load_config(
        ROOT / "config" / "archetypes.json",
        ROOT / "config" / "classification.json",
    )
    store = UserStateStore(state_root)
    return LocalApplication(
        store,
        ArchetypeCatalogStore(store, config.roles),
        config.classification,
    )


def test_default_quicksave_uses_resolved_documents_path(tmp_path):
    documents = tmp_path / "Users" / "Player" / "Documents"

    assert default_battle_brothers_quicksave(documents) == (
        documents / "Battle Brothers" / "savegames" / "quicksave.sav"
    )


def test_default_quicksave_respects_redirected_documents_path(tmp_path):
    documents = tmp_path / "OneDrive" / "Documents"

    assert default_battle_brothers_quicksave(documents) == (
        documents / "Battle Brothers" / "savegames" / "quicksave.sav"
    )


def test_first_run_persists_default_even_when_quicksave_is_missing(tmp_path):
    state_root = tmp_path / "state"
    documents = tmp_path / "OneDrive" / "Documents"
    expected = documents / "Battle Brothers" / "savegames" / "quicksave.sav"

    selected = initialize_first_run_save_default(
        state_root=state_root,
        documents_resolver=lambda: documents,
    )

    preferences = UserStateStore(state_root).load("preferences")
    assert selected == expected
    assert preferences.revision == 1
    assert preferences.selected_save_path == str(expected)
    assert not expected.exists()

    followed = make_application(state_root).followed_save()
    assert followed["selected_path"] == str(expected)
    assert followed["available"] is False
    assert followed["warning"]["code"] == "selected_save_unavailable"


def test_existing_persisted_selection_wins_over_first_run_default(tmp_path):
    state_root = tmp_path / "state"
    store = UserStateStore(state_root)
    chosen = tmp_path / "chosen.sav"
    store.save(
        "preferences",
        PreferencesState(selected_save_path=str(chosen)),
        expected_revision=0,
    )

    result = initialize_first_run_save_default(
        state_root=state_root,
        documents_resolver=lambda: tmp_path / "Documents",
    )

    preferences = store.load("preferences")
    assert result == chosen
    assert preferences.revision == 1
    assert preferences.selected_save_path == str(chosen)


def test_concurrent_first_writer_during_documents_lookup_wins(tmp_path):
    state_root = tmp_path / "state"
    store = UserStateStore(state_root)
    chosen = tmp_path / "chosen-by-concurrent-writer.sav"

    def resolve_documents() -> Path:
        store.save(
            "preferences",
            PreferencesState(selected_save_path=str(chosen)),
            expected_revision=0,
        )
        return tmp_path / "Documents"

    result = initialize_first_run_save_default(
        state_root=state_root,
        documents_resolver=resolve_documents,
    )

    preferences = store.load("preferences")
    assert result == chosen
    assert preferences.revision == 1
    assert preferences.selected_save_path == str(chosen)


def test_explicit_no_selection_is_not_replaced_on_later_startup(tmp_path):
    state_root = tmp_path / "state"
    store = UserStateStore(state_root)
    store.save(
        "preferences",
        PreferencesState(selected_save_path=None),
        expected_revision=0,
    )

    result = initialize_first_run_save_default(
        state_root=state_root,
        documents_resolver=lambda: tmp_path / "Documents",
    )

    preferences = store.load("preferences")
    assert result is None
    assert preferences.revision == 1
    assert preferences.selected_save_path is None


def test_user_replacement_selection_persists_and_is_not_redefaulted(tmp_path):
    state_root = tmp_path / "state"
    documents = tmp_path / "Documents"
    initialize_first_run_save_default(
        state_root=state_root,
        documents_resolver=lambda: documents,
    )
    app = make_application(state_root)
    chosen = tmp_path / "campaign.sav"
    chosen.write_bytes(b"save")

    selected = app.select_followed_save(str(chosen), expected_revision=1)
    assert selected["revision"] == 2
    app.close()

    initialize_first_run_save_default(
        state_root=state_root,
        documents_resolver=lambda: tmp_path / "Other" / "Documents",
    )
    preferences = UserStateStore(state_root).load("preferences")
    assert preferences.revision == 2
    assert preferences.selected_save_path == str(chosen.resolve())


def test_missing_quicksave_does_not_select_an_unrelated_save(tmp_path):
    state_root = tmp_path / "state"
    documents = tmp_path / "Documents"
    savegames = documents / "Battle Brothers" / "savegames"
    savegames.mkdir(parents=True)
    unrelated = savegames / "autosave_1.sav"
    unrelated.write_bytes(b"other")
    expected = savegames / "quicksave.sav"

    initialize_first_run_save_default(
        state_root=state_root,
        documents_resolver=lambda: documents,
    )

    preferences = UserStateStore(state_root).load("preferences")
    assert preferences.selected_save_path == str(expected)
    assert preferences.selected_save_path != str(unrelated)
    followed = make_application(state_root).followed_save()
    assert followed["available"] is False


def test_cli_serve_app_initializes_default_before_starting_server(monkeypatch):
    calls = []
    monkeypatch.setattr(
        first_run,
        "initialize_first_run_save_default",
        lambda: calls.append("initialize"),
    )
    monkeypatch.setattr(
        app_server,
        "serve_local_application",
        lambda **_kwargs: calls.append("serve"),
    )

    app_main.main(["--serve-app"])

    assert calls == ["initialize", "serve"]


def test_installed_launcher_initializes_only_commands_that_start_app(monkeypatch):
    calls = []
    monkeypatch.setattr(
        bb_windows,
        "initialize_first_run_save_default",
        lambda: calls.append("initialize"),
    )

    for command in ([], ["open"], ["background"], ["restart"]):
        bb_windows._initialize_for_launch(command)
    for command in (["stop"], ["status"], ["invalid"]):
        bb_windows._initialize_for_launch(command)

    assert calls == ["initialize", "initialize", "initialize", "initialize"]
