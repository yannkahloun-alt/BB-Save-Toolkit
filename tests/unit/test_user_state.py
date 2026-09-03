import json
from pathlib import Path

import pytest

from bbtool.app import user_state
from bbtool.app.user_state import (
    ArchetypeState,
    CorruptStateError,
    IncompatibleStateError,
    LastSuccessState,
    PreferencesState,
    StateConflictError,
    StateLockError,
    UserStateError,
    UserStateStore,
)


def store(tmp_path):
    return UserStateStore(tmp_path / "profile", clock=lambda: "2026-09-03T12:00:00Z")


def test_missing_state_returns_typed_defaults_without_touching_profile(tmp_path):
    state = store(tmp_path)

    assert state.load("preferences") == PreferencesState()
    assert state.load("archetypes") == ArchetypeState()
    assert state.load("last_success") == LastSuccessState()
    assert not any(state.path_for(feature).exists() for feature in user_state.FEATURES)


def test_preferences_survive_process_equivalent_restart(tmp_path):
    first = store(tmp_path)
    saved = first.save(
        "preferences",
        PreferencesState(selected_save_path="D:/saves/campaign.sav", auto_refresh=True),
        expected_revision=0,
    )

    second = store(tmp_path)
    assert second.load("preferences") == saved
    metadata = second.load("metadata")
    assert metadata.created_at == "2026-09-03T12:00:00Z"
    assert metadata.updated_at == "2026-09-03T12:00:00Z"


def test_all_required_feature_payloads_are_canonical_and_versioned(tmp_path):
    state = store(tmp_path)
    state.save(
        "archetypes",
        ArchetypeState(entries=({"id": "custom_one"},)),
        expected_revision=0,
    )
    state.save(
        "last_success",
        LastSuccessState(
            source_fingerprint="sha256:source",
            config_fingerprint="sha256:config",
            source_timestamp="2026-09-03T11:00:00Z",
            completed_at="2026-09-03T12:00:00Z",
        ),
        expected_revision=0,
    )

    for feature in ("metadata", "archetypes", "last_success"):
        raw = state.path_for(feature).read_text(encoding="utf-8")
        assert raw.endswith("\n")
        assert json.loads(raw)["schema_version"] == 1
        assert raw == json.dumps(json.loads(raw), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def test_optimistic_revision_rejects_stale_writer_after_restart(tmp_path):
    first = store(tmp_path)
    observed = first.load("preferences")
    first.save("preferences", PreferencesState(auto_refresh=True), expected_revision=observed.revision)

    second = store(tmp_path)
    with pytest.raises(StateConflictError, match="expected 0, found 1"):
        second.save(
            "preferences",
            PreferencesState(selected_save_path="stale.sav"),
            expected_revision=observed.revision,
        )
    assert second.load("preferences").auto_refresh is True


def test_os_lock_timeout_fails_conservatively(tmp_path):
    state = UserStateStore(tmp_path / "profile", lock_timeout=0)
    with (
        user_state._exclusive_lock(state._lock_path("preferences"), 1),
        pytest.raises(StateLockError, match="timed out"),
    ):
        state.save("preferences", PreferencesState(), expected_revision=0)


def test_atomic_write_failure_preserves_previous_valid_file(tmp_path, monkeypatch):
    state = store(tmp_path)
    initial = state.save(
        "preferences", PreferencesState(auto_refresh=True), expected_revision=0
    )
    real_replace = user_state.os.replace

    def fail_current(source, destination):
        if Path(destination) == state.path_for("preferences"):
            raise OSError("simulated interruption")
        return real_replace(source, destination)

    monkeypatch.setattr(user_state.os, "replace", fail_current)
    with pytest.raises(OSError, match="simulated interruption"):
        state.save(
            "preferences",
            PreferencesState(selected_save_path="new.sav"),
            expected_revision=initial.revision,
        )

    assert json.loads(state.path_for("preferences").read_text())["auto_refresh"] is True
    assert not list(state.path_for("preferences").parent.glob("*.tmp"))


def test_corruption_is_visible_and_explicit_backup_recovery_is_feature_scoped(tmp_path):
    state = store(tmp_path)
    first = state.save("preferences", PreferencesState(auto_refresh=True), expected_revision=0)
    state.save(
        "preferences",
        PreferencesState(selected_save_path="new.sav"),
        expected_revision=first.revision,
    )
    state.path_for("preferences").write_text("{broken", encoding="utf-8")
    state.save("last_success", LastSuccessState(source_fingerprint="safe"), expected_revision=0)

    with pytest.raises(CorruptStateError):
        state.load("preferences")
    recovered = state.recover_from_backup("preferences")
    assert recovered == PreferencesState(revision=3, auto_refresh=True)
    assert state.load("last_success").source_fingerprint == "safe"


def test_future_schema_is_read_only_and_not_overwritten(tmp_path):
    state = store(tmp_path)
    path = state.path_for("preferences")
    path.parent.mkdir(parents=True)
    future = b'{"schema":"bbtool.preferences.v2","schema_version":2,"revision":8}\n'
    path.write_bytes(future)

    with pytest.raises(IncompatibleStateError, match="newer"):
        state.load("preferences")
    with pytest.raises(IncompatibleStateError):
        state.save("preferences", PreferencesState(), expected_revision=8)
    assert path.read_bytes() == future


def test_explicit_migration_is_atomic_validated_and_restart_safe(tmp_path):
    state = store(tmp_path)
    path = state.path_for("preferences")
    path.parent.mkdir(parents=True)
    legacy = (
        b'{"schema":"bbtool.preferences.v0","schema_version":0,"revision":2,'
        b'"selected_save":"old.sav","auto_refresh":true}\n'
    )
    path.write_bytes(legacy)

    migrated = state.load("preferences")
    assert migrated == PreferencesState(
        revision=3, selected_save_path="old.sav", auto_refresh=True
    )
    assert path.with_suffix(".json.bak").read_bytes() == legacy
    assert store(tmp_path).load("preferences") == migrated

    with pytest.raises(StateConflictError, match="expected 2, found 3"):
        state.save(
            "preferences", PreferencesState(auto_refresh=False),
            expected_revision=2,
        )


def test_migration_failure_preserves_original_bytes(tmp_path):
    state = store(tmp_path)
    path = state.path_for("preferences")
    path.parent.mkdir(parents=True)
    legacy = b'{"schema":"wrong","schema_version":0,"revision":2,"selected_save":null,"auto_refresh":false}\n'
    path.write_bytes(legacy)

    with pytest.raises(user_state.MigrationError, match="migration from version 0 failed"):
        state.load("preferences")
    assert path.read_bytes() == legacy
    assert not path.with_suffix(".json.bak").exists()


def test_restore_migrates_older_backup_before_committing(tmp_path):
    state = store(tmp_path)
    backup = tmp_path / "legacy-backup"
    backup.mkdir()
    (backup / "preferences.json").write_text(
        json.dumps({
            "schema": "bbtool.preferences.v0",
            "schema_version": 0,
            "revision": 7,
            "selected_save": "legacy.sav",
            "auto_refresh": True,
        }),
        encoding="utf-8",
    )

    state.restore(backup)

    assert state.load("preferences") == PreferencesState(
        revision=8, selected_save_path="legacy.sav", auto_refresh=True
    )


def test_recovery_migrates_valid_pre_migration_backup(tmp_path):
    state = store(tmp_path)
    path = state.path_for("preferences")
    path.parent.mkdir(parents=True)
    legacy = {
        "schema": "bbtool.preferences.v0",
        "schema_version": 0,
        "revision": 2,
        "selected_save": "legacy.sav",
        "auto_refresh": True,
    }
    path.write_text(json.dumps(legacy), encoding="utf-8")
    migrated = state.load("preferences")
    path.write_text("corrupt", encoding="utf-8")

    recovered = state.recover_from_backup("preferences")

    assert recovered == PreferencesState(
        revision=migrated.revision + 1,
        selected_save_path="legacy.sav",
        auto_refresh=True,
    )


def test_explicit_backup_restore_and_reset_lifecycle(tmp_path):
    state = store(tmp_path)
    saved = state.save(
        "preferences", PreferencesState(selected_save_path="portable.sav"), expected_revision=0
    )
    backup = state.backup(tmp_path / "manual-backup")
    state.reset_feature("preferences", expected_revision=saved.revision)
    assert state.load("preferences") == PreferencesState(revision=saved.revision + 1)

    state.restore(backup)
    restored = store(tmp_path).load("preferences")
    assert restored == PreferencesState(
        revision=saved.revision + 2, selected_save_path="portable.sav"
    )
    state.reset_all()
    assert state.load("preferences") == PreferencesState(revision=restored.revision + 1)
    assert state.path_for("preferences").with_suffix(".json.bak").exists()


def test_reset_revision_tombstone_rejects_writer_that_observed_missing_state(tmp_path):
    state = store(tmp_path)
    stale = state.load("preferences")
    created = state.save(
        "preferences", PreferencesState(auto_refresh=True), expected_revision=0
    )
    state.reset_feature("preferences", expected_revision=created.revision)

    with pytest.raises(StateConflictError, match="expected 0, found 2"):
        state.save(
            "preferences",
            PreferencesState(selected_save_path="resurrected.sav"),
            expected_revision=stale.revision,
        )
    assert state.load("preferences") == PreferencesState(revision=2)


def test_reset_of_missing_feature_reserves_revision_against_stale_writer(tmp_path):
    state = store(tmp_path)
    stale = state.load("preferences")

    state.reset_feature("preferences", expected_revision=0)

    assert state.load("preferences") == PreferencesState(revision=1)
    with pytest.raises(StateConflictError, match="expected 0, found 1"):
        state.save(
            "preferences", PreferencesState(auto_refresh=True),
            expected_revision=stale.revision,
        )


def test_missing_primary_with_revision_tombstone_is_not_first_run(tmp_path):
    state = store(tmp_path)
    stale = state.load("preferences")
    created = state.save(
        "preferences", PreferencesState(auto_refresh=True), expected_revision=0
    )
    state.reset_feature("preferences", expected_revision=created.revision)
    state.path_for("preferences").unlink()

    with pytest.raises(CorruptStateError, match="payload is missing"):
        state.load("preferences")
    with pytest.raises(CorruptStateError, match="payload is missing"):
        state.save(
            "preferences", PreferencesState(auto_refresh=True),
            expected_revision=stale.revision,
        )


def test_recovery_highwater_prevents_revision_reuse_after_corruption(tmp_path):
    state = store(tmp_path)
    first = state.save(
        "preferences", PreferencesState(selected_save_path="first.sav"),
        expected_revision=0,
    )
    observed = state.save(
        "preferences", PreferencesState(selected_save_path="second.sav"),
        expected_revision=first.revision,
    )
    state.path_for("preferences").write_text("corrupt", encoding="utf-8")

    recovered = state.recover_from_backup("preferences")

    assert recovered.revision == observed.revision + 1
    with pytest.raises(StateConflictError, match="expected 2, found 3"):
        state.save(
            "preferences", PreferencesState(selected_save_path="stale.sav"),
            expected_revision=observed.revision,
        )


def test_explicit_recovery_repairs_one_corrupt_highwater_copy(tmp_path):
    state = store(tmp_path)
    first = state.save(
        "preferences", PreferencesState(selected_save_path="first.sav"),
        expected_revision=0,
    )
    state.save(
        "preferences", PreferencesState(selected_save_path="second.sav"),
        expected_revision=first.revision,
    )
    state.path_for("preferences").write_text("corrupt", encoding="utf-8")
    state._revision_path("preferences").write_text("corrupt", encoding="ascii")

    recovered = state.recover_from_backup("preferences")

    assert recovered == PreferencesState(
        revision=3, selected_save_path="first.sav"
    )
    assert state._revision_path("preferences").read_text() == "3\n"
    assert state._revision_mirror_path("preferences").read_text() == "3\n"


def test_two_corrupt_highwater_copies_block_recovery_conservatively(tmp_path):
    state = store(tmp_path)
    first = state.save(
        "preferences", PreferencesState(selected_save_path="first.sav"),
        expected_revision=0,
    )
    state.save(
        "preferences", PreferencesState(selected_save_path="second.sav"),
        expected_revision=first.revision,
    )
    state.path_for("preferences").write_text("corrupt", encoding="utf-8")
    state._revision_path("preferences").write_text("corrupt", encoding="ascii")
    state._revision_mirror_path("preferences").write_text("corrupt", encoding="ascii")

    with pytest.raises(CorruptStateError, match="copies are unusable"):
        state.recover_from_backup("preferences")


def test_two_missing_highwater_copies_block_corrupt_primary_recovery(tmp_path):
    state = store(tmp_path)
    first = state.save(
        "preferences", PreferencesState(selected_save_path="first.sav"),
        expected_revision=0,
    )
    state.save(
        "preferences", PreferencesState(selected_save_path="second.sav"),
        expected_revision=first.revision,
    )
    state.path_for("preferences").write_text("corrupt", encoding="utf-8")
    state._revision_path("preferences").unlink()
    state._revision_mirror_path("preferences").unlink()

    with pytest.raises(CorruptStateError, match="copies are unusable"):
        state.recover_from_backup("preferences")


def test_explicit_recovery_rebuilds_missing_highwater_copy(tmp_path):
    state = store(tmp_path)
    first = state.save(
        "preferences", PreferencesState(selected_save_path="first.sav"),
        expected_revision=0,
    )
    state.save(
        "preferences", PreferencesState(selected_save_path="second.sav"),
        expected_revision=first.revision,
    )
    state.path_for("preferences").write_text("corrupt", encoding="utf-8")
    state._revision_path("preferences").unlink()

    recovered = state.recover_from_backup("preferences")

    assert recovered.revision == 3
    assert state._revision_path("preferences").read_text() == "3\n"
    assert state._revision_mirror_path("preferences").read_text() == "3\n"


def test_restore_advances_local_revision_and_rejects_stale_writer(tmp_path):
    state = store(tmp_path)
    historical = state.save(
        "preferences",
        PreferencesState(selected_save_path="historical.sav"),
        expected_revision=0,
    )
    backup = state.backup(tmp_path / "historical-backup")
    current = state.save(
        "preferences",
        PreferencesState(selected_save_path="current.sav"),
        expected_revision=historical.revision,
    )

    state.restore(backup)

    restored = state.load("preferences")
    assert restored == PreferencesState(
        revision=current.revision + 1, selected_save_path="historical.sav"
    )
    with pytest.raises(StateConflictError, match="expected 1, found 3"):
        state.save(
            "preferences",
            PreferencesState(selected_save_path="stale.sav"),
            expected_revision=historical.revision,
        )
    recovery = state.path_for("preferences").with_suffix(".json.bak")
    assert json.loads(recovery.read_text())["selected_save_path"] == "current.sav"


def test_backup_preserves_complete_root_but_not_volatile_lock_files(tmp_path):
    state = store(tmp_path)
    future_domain = state.root / "campaigns" / "stable-key" / "assignments.json"
    future_domain.parent.mkdir(parents=True)
    future_domain.write_text('{"future":"preserved"}', encoding="utf-8")
    (state.root / ".ignored.lock").write_text("volatile", encoding="utf-8")

    backup = state.backup(tmp_path / "complete-backup")
    assert (backup / future_domain.relative_to(state.root)).read_bytes() == future_domain.read_bytes()
    assert not (backup / ".ignored.lock").exists()

    future_domain.unlink()
    state.restore(backup)
    assert future_domain.read_text(encoding="utf-8") == '{"future":"preserved"}'


def test_restore_backs_up_existing_forward_compatible_domain_file(tmp_path):
    state = store(tmp_path)
    future_domain = state.root / "campaigns" / "stable-key" / "assignments.json"
    future_domain.parent.mkdir(parents=True)
    future_domain.write_text('{"version":"backup"}', encoding="utf-8")
    backup = state.backup(tmp_path / "domain-backup")
    future_domain.write_text('{"version":"current"}', encoding="utf-8")

    state.restore(backup)

    assert future_domain.read_text() == '{"version":"backup"}'
    assert future_domain.with_suffix(".json.bak").read_text() == (
        '{"version":"current"}'
    )


def test_reset_all_clears_future_bounded_domain_files_with_backup(tmp_path):
    state = store(tmp_path)
    future_domain = state.root / "campaigns" / "stable-key" / "assignments.json"
    future_domain.parent.mkdir(parents=True)
    future_domain.write_text('{"assignment":"user-owned"}', encoding="utf-8")

    state.reset_all()

    assert not future_domain.exists()
    assert future_domain.with_suffix(".json.bak").read_text() == (
        '{"assignment":"user-owned"}'
    )


def test_reset_all_preflights_every_feature_before_mutating_any(tmp_path):
    state = store(tmp_path)
    preferences = state.save(
        "preferences", PreferencesState(auto_refresh=True), expected_revision=0
    )
    state.save(
        "last_success", LastSuccessState(source_fingerprint="valid"),
        expected_revision=0,
    )
    state.path_for("last_success").write_text("corrupt", encoding="utf-8")

    with pytest.raises(CorruptStateError):
        state.reset_all()

    assert state.load("preferences") == preferences


def test_restore_preflights_every_local_feature_before_mutating_any(tmp_path):
    source = store(tmp_path)
    original = source.save(
        "preferences", PreferencesState(selected_save_path="before.sav"),
        expected_revision=0,
    )
    backup = source.backup(tmp_path / "restore-source")
    source.save(
        "preferences", PreferencesState(selected_save_path="after.sav"),
        expected_revision=original.revision,
    )
    source.save(
        "last_success", LastSuccessState(source_fingerprint="valid"),
        expected_revision=0,
    )
    before_restore = source.load("preferences")
    source.path_for("last_success").write_text("corrupt", encoding="utf-8")

    with pytest.raises(CorruptStateError):
        source.restore(backup)

    assert source.load("preferences") == before_restore


def test_failed_reset_all_keeps_prior_feature_recoverable(tmp_path, monkeypatch):
    state = store(tmp_path)
    preferences = state.save(
        "preferences", PreferencesState(auto_refresh=True), expected_revision=0
    )
    state.save(
        "archetypes", ArchetypeState(entries=({"id": "custom"},)),
        expected_revision=0,
    )
    real_atomic_write = user_state._atomic_write
    failed = False

    def fail_once(path, data):
        nonlocal failed
        if path == state.path_for("archetypes") and not failed:
            failed = True
            raise OSError("simulated reset interruption")
        return real_atomic_write(path, data)

    monkeypatch.setattr(user_state, "_atomic_write", fail_once)
    with pytest.raises(OSError, match="simulated reset interruption"):
        state.reset_all()

    recovered = state.recover_from_backup("preferences")
    assert recovered.auto_refresh == preferences.auto_refresh


def test_backup_rejects_nested_destination_and_invalid_source(tmp_path):
    state = store(tmp_path)
    with pytest.raises(UserStateError, match="outside"):
        state.backup(state.root / "backup")
    bad = tmp_path / "bad-backup"
    bad.mkdir()
    (bad / "preferences.json").write_text("{}", encoding="utf-8")
    with pytest.raises(CorruptStateError):
        state.restore(bad)


def test_backup_rejects_missing_primary_with_recovery_evidence(tmp_path):
    state = store(tmp_path)
    first = state.save(
        "preferences", PreferencesState(selected_save_path="first.sav"),
        expected_revision=0,
    )
    state.save(
        "preferences", PreferencesState(selected_save_path="second.sav"),
        expected_revision=first.revision,
    )
    state.path_for("preferences").unlink()

    with pytest.raises(CorruptStateError, match="degraded preferences"):
        state.backup(tmp_path / "must-not-look-valid")
    assert not (tmp_path / "must-not-look-valid").exists()


def test_restore_rejects_degraded_recognized_source_before_mutation(tmp_path):
    state = store(tmp_path)
    current = state.save(
        "preferences", PreferencesState(selected_save_path="current.sav"),
        expected_revision=0,
    )
    degraded = tmp_path / "degraded-backup"
    degraded.mkdir()
    (degraded / "preferences.json.bak").write_text(
        json.dumps({
            "schema": "bbtool.preferences.v1",
            "schema_version": 1,
            "revision": 1,
            "selected_save_path": "old.sav",
            "auto_refresh": False,
        }),
        encoding="utf-8",
    )
    (degraded / ".preferences.json.revision").write_text("2\n")

    with pytest.raises(CorruptStateError, match="degraded preferences"):
        state.restore(degraded)
    assert state.load("preferences") == current


@pytest.mark.parametrize(
    "damage", ["missing", "both_missing", "corrupt", "disagree"]
)
def test_restore_rejects_invalid_source_revision_pair(tmp_path, damage):
    source = UserStateStore(tmp_path / "source")
    source.save(
        "preferences", PreferencesState(selected_save_path="source.sav"),
        expected_revision=0,
    )
    backup = source.backup(tmp_path / "backup")
    primary_revision = backup / ".preferences.json.revision"
    mirror_revision = backup / ".preferences.json.revision.bak"
    if damage == "missing":
        mirror_revision.unlink()
        message = "incomplete preferences revision"
    elif damage == "both_missing":
        primary_revision.unlink()
        mirror_revision.unlink()
        message = "missing preferences revision"
    elif damage == "corrupt":
        primary_revision.write_text("broken", encoding="ascii")
        message = "revision copy"
    else:
        mirror_revision.write_text("9\n", encoding="ascii")
        message = "inconsistent preferences revisions"
    target = store(tmp_path)
    current = target.save(
        "preferences", PreferencesState(selected_save_path="target.sav"),
        expected_revision=0,
    )

    with pytest.raises(CorruptStateError, match=message):
        target.restore(backup)
    assert target.load("preferences") == current


def test_path_resolver_is_platform_appropriate_and_override_is_exact(tmp_path, monkeypatch):
    assert user_state.resolve_user_state_root(override=tmp_path) == tmp_path.resolve()
    monkeypatch.setattr(user_state.sys, "platform", "linux")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    assert user_state.resolve_user_state_root() == (tmp_path / "xdg" / "BB-Save-Toolkit").resolve()


def test_output_retention_cannot_reach_separate_user_state_root(tmp_path):
    from bbtool.app.output import prune_outputs

    output = tmp_path / "outputs"
    output.mkdir()
    state = UserStateStore(tmp_path / "profile")
    state.save("preferences", PreferencesState(auto_refresh=True), expected_revision=0)
    archives = []
    for index in range(3):
        path = output / f"quicksave-20260903-12000{index}.zip"
        path.write_bytes(b"output")
        archives.append(path)

    prune_outputs(output, "quicksave", archives[-1], max_outputs=1)
    assert state.load("preferences").auto_refresh is True
    assert state.root not in output.parents and output not in state.root.parents


def test_incremental_cache_retention_cannot_reach_user_state_root(tmp_path):
    from bbtool.incremental.manifest import prune_manifests
    from bbtool.models import CampaignIdentity

    output = tmp_path / "outputs"
    output.mkdir()
    identity_payload = {
        "schema": "bbtool.campaign_identity.v1",
        "basis": "native_campaign_id",
        "value": 7,
        "confidence": "exact",
        "reason": None,
    }
    for index in range(2):
        run = output / f"run{index}"
        run.mkdir()
        (run / f"run{index}-incremental-manifest.json").write_text(
            json.dumps({
                "schema": "bb-incremental-v2",
                "source_save_path": "C:/saves/example.sav",
                "campaign_identity": identity_payload,
            }),
            encoding="utf-8",
        )
    state = UserStateStore(tmp_path / "profile")
    state.save("preferences", PreferencesState(auto_refresh=True), expected_revision=0)

    prune_manifests(output, campaign_identity=CampaignIdentity(7), keep=1)

    assert state.load("preferences").auto_refresh is True
