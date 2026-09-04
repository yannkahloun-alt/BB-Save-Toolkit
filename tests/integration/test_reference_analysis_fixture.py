import hashlib
import json
from pathlib import Path
import runpy

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests/fixtures/reference_analysis"


def _load(name):
    return json.loads((FIXTURE / name).read_text(encoding="utf-8"))


def test_reference_analysis_manifest_and_files_are_compatible():
    manifest = _load("manifest.json")
    assert manifest["schema"] == "bbtool.reference_analysis.v3"
    assert set(manifest["files"]) == {
        "roster", "recruits", "role_fit", "classification",
        "archetypes", "classification_config", "analysis_health", "presentation",
    }
    for entry in manifest["files"].values():
        path = FIXTURE / entry["path"]
        assert path.is_file()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == entry["sha256"]
        assert b"\r\n" not in path.read_bytes()
        json.loads(path.read_text(encoding="utf-8"))


def test_reference_analysis_relations_and_public_data_contract():
    roster = _load("reference-roster.json")
    fits = _load("reference-role-fit.json")
    summaries = _load("reference-classification.json")
    roles = _load("reference-archetypes.json")["roles"]
    bro_ids = {bro["BrotherID"] for bro in roster}
    role_names = {role["name"] for role in roles}

    assert len(bro_ids) == len(roster) >= 4
    assert {row["BrotherID"] for row in fits} == bro_ids
    assert {row["Role"] for row in fits} == role_names
    assert {row["BrotherID"] for row in summaries} == bro_ids
    assert {row["BestRole"] for row in summaries} <= role_names
    assert {row["Category"] for row in summaries} == {"Invest", "Use", "Fodder", "Trash"}
    assert any(row["LevelUpAdvice"] for row in summaries)
    assert len(fits) == len(roster) * len(roles)
    assert all("FutureRolls" not in bro for bro in roster)
    assert all("FutureRolls" not in json.dumps(value) for value in (fits, summaries))
    assert {rec["TryoutDone"] for rec in _load("reference-recruits.json")} == {True, False}
    presentation = _load("reference-target-presentation.json")
    assert presentation["schema"] == "bbtool.target_presentation.v1"
    assert len(presentation["validity"]["artifacts"]["role_projection"]) == \
        len(fits)
    assert len(presentation["validity"]["artifacts"][
        "strategic_classification"
    ]) == len(roster)


def test_reference_analysis_contains_no_machine_paths_or_volatile_metadata():
    combined = "\n".join(path.read_text(encoding="utf-8") for path in FIXTURE.glob("*.json"))
    assert "generated_at" not in combined
    assert "source_save" not in combined
    assert ":\\\\Users\\\\" not in combined
    assert "/home/" not in combined


def test_reference_analysis_is_current_and_deterministic():
    generator = runpy.run_path(str(FIXTURE / "generate.py"))
    first = generator["_payloads"]()
    second = generator["_payloads"]()
    assert first == second
    for key, filename in generator["FILES"].items():
        expected = json.dumps(first[key], indent=2, ensure_ascii=False, sort_keys=True) + "\n"
        assert (FIXTURE / filename).read_text(encoding="utf-8") == expected
        assert (FIXTURE / filename).read_bytes() == expected.encode("utf-8")
