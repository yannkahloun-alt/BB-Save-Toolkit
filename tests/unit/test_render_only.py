import hashlib
import json
from pathlib import Path
import shutil

import pytest

from bbtool.app.cli import CliOptions, parse_args
import bbtool.app.main as app_main
import bbtool.app.render_only as render_only
from bbtool.app.render_only import RenderDatasetError, load_render_dataset, run_render_only
from bbtool.app.report_server import render_served_report
from bbtool.app.health import build_public_analysis_health, build_run_health
from bbtool.app.target_presentation import (
    DATASET_SCHEMA as TARGET_DATASET_SCHEMA,
    _validate_recruitment_analysis,
    build_recruitment_presentation,
    build_target_presentation,
)
from bbtool.app.config import _normalize_role
from bbtool.build_identity import build_definition_hash
from bbtool.company_planning import build_intrinsic_company_coverage
from bbtool.incremental.dependencies import ArtifactKind, ENGINE_VERSIONS, stable_hash
from bbtool.incremental.fingerprint import (
    advisor_fingerprint,
    brother_projection_fingerprint,
    brother_summary_fingerprint,
    role_fingerprint,
)
from bbtool.html_report import render_report_launcher
from bbtool.models import BrotherIdentity, CampaignIdentity
from bbtool.recruitment_prior import (
    load_background_potential_reference,
    recruit_candidate_estimate,
)


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "fixtures" / "reference_analysis"


def _options(source: Path, out: Path) -> CliOptions:
    return CliOptions(
        save=None, targets=Path("unused"), classification=Path("unused"),
        out=out, no_projection=False, open_report=False,
        render_only=source,
    )


def _copy_fixture(tmp_path: Path) -> Path:
    target = tmp_path / "dataset"
    shutil.copytree(FIXTURE, target)
    return target


def _rewrite_payload_and_hash(source: Path, label: str, mutate) -> None:
    manifest_path = source / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload_path = source / manifest["files"][label]["path"]
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    mutate(payload)
    if manifest.get("schema") == TARGET_DATASET_SCHEMA and label == "presentation":
        payload["publication"]["provenance"]["content_hashes"] = {
            key: stable_hash(payload[key]) for key in (
                "brothers", "builds", "campaign_identity", "company", "pending",
                "recruitment", "run_health", "validity",
            )
        }
        payload["publication"]["coherence_signature"] = stable_hash(
            payload["publication"]["provenance"]
        )
    payload_path.write_text(json.dumps(payload), encoding="utf-8")
    manifest["files"][label]["sha256"] = hashlib.sha256(
        payload_path.read_bytes()
    ).hexdigest()
    if manifest.get("schema") == TARGET_DATASET_SCHEMA and label != "presentation":
        presentation_path = source / manifest["files"]["presentation"]["path"]
        presentation = json.loads(presentation_path.read_text(encoding="utf-8"))
        presentation["publication"]["provenance"]["artifact_hashes"][label] = \
            manifest["files"][label]["sha256"]
        if label == "analysis_health":
            presentation["run_health"] = payload
        presentation["publication"]["provenance"]["content_hashes"] = {
            key: stable_hash(presentation[key]) for key in (
                "brothers", "builds", "campaign_identity", "company", "pending",
                "recruitment", "run_health", "validity",
            )
        }
        presentation["publication"]["coherence_signature"] = stable_hash(
            presentation["publication"]["provenance"]
        )
        presentation_path.write_text(json.dumps(presentation), encoding="utf-8")
        manifest["files"]["presentation"]["sha256"] = hashlib.sha256(
            presentation_path.read_bytes()
        ).hexdigest()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")


def _upgrade_to_target_v3(source: Path) -> Path:
    dataset = load_render_dataset(source)
    manifest_path = source / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    hashes = {key: value["sha256"] for key, value in manifest["files"].items()}
    identities = {
        bro.BrotherID: BrotherIdentity(77, index + 1, confidence="exact")
        for index, bro in enumerate(dataset.bros)
    }
    recruitment = build_recruitment_presentation(
        dataset.recruits, dataset.roles, source / "unused-backgrounds.json"
    )
    presentation = build_target_presentation(
        bros=dataset.bros, recruits=dataset.recruits, roles=dataset.roles,
        analysis_health=dataset.analysis_health,
        campaign_identity=CampaignIdentity(77, confidence="exact"),
        brother_identities=identities,
        source_fingerprint=stable_hash({"save": "fixture"}),
        configuration_fingerprints={
            "archetypes": stable_hash(dataset.roles),
            "classification": stable_hash(dataset.classification),
        },
        recruitment_analysis=recruitment, artifact_hashes=hashes,
        result_signatures={
            "role_projection": [
                {
                    "brother_id": bro.BrotherID,
                    "build_key": role["id"],
                    "dependency_signature": stable_hash({
                        "artifact": "role_projection",
                        "brother_state": brother_projection_fingerprint(bro),
                        "build_definition": role_fingerprint(role),
                        "engine_version": ENGINE_VERSIONS[
                            ArtifactKind.ROLE_PROJECTION
                        ],
                    }),
                }
                for bro in dataset.bros
                for role in dataset.roles
            ],
            "strategic_classification": [
                {
                    "brother_id": bro.BrotherID,
                    "dependency_signature": brother_summary_fingerprint(
                        bro, dataset.roles, dataset.classification
                    ),
                }
                for bro in dataset.bros
            ],
            "level_advisor": [
                {
                    "brother_id": bro.BrotherID,
                    "dependency_signature": advisor_fingerprint(bro, dataset.roles),
                }
                for bro in dataset.bros
            ],
        },
        company_intrinsic_coverage=build_intrinsic_company_coverage(
            dataset.bros, dataset.roles, dataset.fits, dataset.classification,
            identities,
        ),
    )
    path = source / "reference-target-presentation.json"
    path.write_text(json.dumps(presentation), encoding="utf-8")
    manifest["schema"] = TARGET_DATASET_SCHEMA
    manifest["files"]["presentation"] = {
        "path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return source


def test_cli_accepts_render_only_without_save():
    options = parse_args(["--render-only", str(FIXTURE)])
    assert options.save is None
    assert options.render_only == FIXTURE


def test_cli_accepts_serve_report_without_save():
    options = parse_args(["--serve-report", str(FIXTURE)])
    assert options.save is None
    assert options.serve_report == FIXTURE


def test_cli_rejects_analysis_flags_in_render_only(capsys):
    with pytest.raises(SystemExit):
        parse_args(["--render-only", str(FIXTURE), "--verify-cache"])
    assert "cannot be used with --render-only" in capsys.readouterr().err


def test_main_dispatches_render_only_without_loading_analysis_runner(monkeypatch):
    calls = []
    monkeypatch.setattr(render_only, "run_render_only", lambda options: calls.append(options))
    app_main.main(["--render-only", str(FIXTURE)])
    assert len(calls) == 1
    assert calls[0].render_only == FIXTURE


def test_main_dispatches_serve_report(monkeypatch):
    calls = []
    from bbtool.app import report_server
    monkeypatch.setattr(
        report_server,
        "serve_report",
        lambda source, open_browser=False: calls.append((source, open_browser)),
    )
    app_main.main(["--serve-report", str(FIXTURE), "--open-report"])
    assert calls == [(FIXTURE, True)]


def test_load_render_dataset_validates_relations_and_builds_brothers():
    dataset = load_render_dataset(FIXTURE)
    assert len(dataset.bros) == 5
    assert dataset.bros[0].BrotherID.startswith("human:")
    assert dataset.roles
    assert dataset.fits
    assert dataset.analysis_health["status"] == "healthy"
    assert dataset.presentation["schema"] == "bbtool.target_presentation.v1"


def test_target_v3_exposes_authoritative_foundation_and_loads_for_all_consumers(tmp_path):
    source = _upgrade_to_target_v3(_copy_fixture(tmp_path))
    dataset = load_render_dataset(source)
    assert dataset.manifest["schema"] == TARGET_DATASET_SCHEMA
    assert dataset.presentation["campaign_identity"]["value"] == 77
    assert dataset.presentation["brothers"][0]["brother_identity"]["value"].startswith(
        "campaign:77/entity:"
    )
    assert all(item["build_identity"] for item in dataset.presentation["builds"])
    assert dataset.presentation["run_health"] == dataset.analysis_health
    assert dataset.presentation["pending"] == {
        "assigned_build": 107, "intent_aware_advisor": 108,
        "intent_aware_company_planning": 166, "relevant_roster_need": 112,
    }
    assert render_served_report(source)[1]


def test_target_v3_rejects_mixed_generation_even_when_manifest_hash_is_updated(tmp_path):
    source = _upgrade_to_target_v3(_copy_fixture(tmp_path))
    manifest_path = source / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    path = source / manifest["files"]["classification_config"]["path"]
    value = json.loads(path.read_text(encoding="utf-8"))
    value["invest"] = 999
    path.write_text(json.dumps(value), encoding="utf-8")
    manifest["files"]["classification_config"]["sha256"] = hashlib.sha256(
        path.read_bytes()
    ).hexdigest()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(RenderDatasetError, match="artifact generation mismatch"):
        load_render_dataset(source)


def test_target_v3_rejects_mismatched_build_definition(tmp_path):
    source = _upgrade_to_target_v3(_copy_fixture(tmp_path))
    _rewrite_payload_and_hash(
        source, "presentation",
        lambda value: value["builds"][0].update(
            build_definition_hash="sha256:" + "0" * 64
        ),
    )
    with pytest.raises(RenderDatasetError, match="build identity mismatch"):
        load_render_dataset(source)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value["validity"]["artifacts"]["role_projection"].pop(),
        lambda value: value["validity"]["artifacts"]["strategic_classification"].append(
            dict(value["validity"]["artifacts"]["strategic_classification"][0])
        ),
        lambda value: value["validity"]["artifacts"]["level_advisor"][0].update(
            dependency_signature="sha256:not-a-digest"
        ),
        lambda value: value["validity"]["artifacts"]["role_projection"][0].update(
            unexpected="private-evidence"
        ),
    ],
    ids=("missing", "duplicate", "bad-digest", "extra-field"),
)
def test_target_v3_rejects_incomplete_or_malformed_dependency_evidence(
    tmp_path, mutate,
):
    source = _upgrade_to_target_v3(_copy_fixture(tmp_path))
    _rewrite_payload_and_hash(source, "presentation", mutate)
    with pytest.raises(RenderDatasetError, match="dependency evidence"):
        load_render_dataset(source)


def test_target_v3_rejects_well_formed_but_incorrect_dependency_signature(tmp_path):
    source = _upgrade_to_target_v3(_copy_fixture(tmp_path))
    _rewrite_payload_and_hash(
        source, "presentation",
        lambda value: value["validity"]["artifacts"]["role_projection"][0].update(
            dependency_signature="sha256:" + "0" * 64
        ),
    )
    with pytest.raises(RenderDatasetError, match="dependency evidence is mismatched"):
        load_render_dataset(source)


@pytest.mark.parametrize("field", ["archetypes", "classification"])
def test_target_v3_rejects_well_formed_but_incorrect_config_fingerprint(
    tmp_path, field,
):
    source = _upgrade_to_target_v3(_copy_fixture(tmp_path))
    _rewrite_payload_and_hash(
        source, "presentation",
        lambda value: value["publication"]["provenance"][
            "configuration_fingerprints"
        ].update({field: "sha256:" + "0" * 64}),
    )
    with pytest.raises(RenderDatasetError, match="configuration fingerprints mismatch"):
        load_render_dataset(source)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value["campaign_identity"].update(value="not-an-integer"),
        lambda value: value["brothers"][0]["brother_identity"].update(
            value="campaign:77/entity:0"
        ),
        lambda value: value["brothers"][0]["brother_identity"].update(
            value="campaign:78/entity:1"
        ),
    ],
    ids=("campaign-shape", "brother-shape", "campaign-namespace"),
)
def test_target_v3_rejects_malformed_or_mismatched_exact_identity(
    tmp_path, mutate,
):
    source = _upgrade_to_target_v3(_copy_fixture(tmp_path))
    _rewrite_payload_and_hash(source, "presentation", mutate)
    with pytest.raises(RenderDatasetError, match="identity"):
        load_render_dataset(source)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value["campaign_identity"].update(
            value=None, confidence="unavailable", basis={"not": "a string"},
            reason=["not", "a string"],
        ),
        lambda value: value["brothers"][0]["brother_identity"].update(
            value=None, confidence="invalid", basis=123, reason=None,
        ),
    ],
    ids=("campaign-unavailable", "brother-invalid"),
)
def test_target_v3_rejects_malformed_nonexact_identity_metadata(tmp_path, mutate):
    source = _upgrade_to_target_v3(_copy_fixture(tmp_path))
    _rewrite_payload_and_hash(source, "presentation", mutate)
    with pytest.raises(RenderDatasetError, match="identity"):
        load_render_dataset(source)


def test_target_v3_rejects_stale_company_coverage(tmp_path):
    source = _upgrade_to_target_v3(_copy_fixture(tmp_path))
    _rewrite_payload_and_hash(
        source, "presentation",
        lambda value: value["company"]["intrinsic_coverage"][0].update(
            ViableCount=999
        ),
    )
    with pytest.raises(RenderDatasetError, match="company generation mismatch"):
        load_render_dataset(source)


def test_target_v3_rejects_bogus_recruitment_result(tmp_path):
    source = _upgrade_to_target_v3(_copy_fixture(tmp_path))

    def replace_result(value):
        analysis = value["recruitment"][0]["analyses"][0]
        analysis.update(
            state="prior_only", reason=None,
            result={"schema": "bogus", "model_version": 999},
        )

    _rewrite_payload_and_hash(source, "presentation", replace_result)
    with pytest.raises(RenderDatasetError, match="recruitment result is malformed"):
        load_render_dataset(source)


def test_target_v3_rejects_duplicate_recruitment_build_analysis(tmp_path):
    source = _upgrade_to_target_v3(_copy_fixture(tmp_path))
    _rewrite_payload_and_hash(
        source, "presentation",
        lambda value: value["recruitment"][0]["analyses"].append(
            dict(value["recruitment"][0]["analyses"][0])
        ),
    )
    with pytest.raises(RenderDatasetError, match="recruitment build joins mismatch"):
        load_render_dataset(source)


def test_target_v3_rejects_duplicate_presentation_brother_row(tmp_path):
    source = _upgrade_to_target_v3(_copy_fixture(tmp_path))
    _rewrite_payload_and_hash(
        source, "presentation",
        lambda value: value["brothers"].append(dict(value["brothers"][0])),
    )
    with pytest.raises(RenderDatasetError, match="brother joins do not match roster"):
        load_render_dataset(source)


def test_target_v3_rejects_duplicate_exact_brother_identity(tmp_path):
    source = _upgrade_to_target_v3(_copy_fixture(tmp_path))
    _rewrite_payload_and_hash(
        source, "presentation",
        lambda value: value["brothers"][1].update(
            brother_identity=dict(value["brothers"][0]["brother_identity"])
        ),
    )
    with pytest.raises(RenderDatasetError, match="duplicate BrotherIdentity"):
        load_render_dataset(source)


def test_recruitment_analysis_must_match_bound_recruit_evidence():
    role = _normalize_role({
        "id": "melee_test", "name": "Melee test",
        "stats": {"MAtk": {"baseline": 70, "target": 90, "weight": 1}},
    })
    reference = load_background_potential_reference(
        ROOT / "tests" / "fixtures" / "background_prior_reference.json"
    )
    result = recruit_candidate_estimate(
        {"BackgroundSaveHash": "AAAABBBB", "TryoutDone": False}, role, reference
    )
    with pytest.raises(ValueError, match="evidence generation mismatch"):
        _validate_recruitment_analysis(
            {
                "build_identity": role["id"], "state": result["state"],
                "reason": None, "result": result,
            },
            background_save_hash="AAAABBBB",
            build_definition_hash_value=build_definition_hash(role),
            recruit={
                "BackgroundSaveHash": "AAAABBBB", "TryoutDone": True,
                "RevealedTraitEvidence": [
                    {"save_hash": "1234ABCD", "name": "Sure Footing"}
                ],
            },
        )


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value["company"]["intrinsic_coverage"][0].update(
            ViableCount=999
        ),
        lambda value: value["recruitment"][0]["analyses"][0].update(
            state="prior_only", reason=None,
            result={"schema": "bogus", "model_version": 999},
        ),
    ],
    ids=("company", "recruitment"),
)
def test_target_v3_content_hashes_reject_sidecar_tampering(tmp_path, mutate):
    source = _upgrade_to_target_v3(_copy_fixture(tmp_path))
    manifest_path = source / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    path = source / manifest["files"]["presentation"]["path"]
    presentation = json.loads(path.read_text(encoding="utf-8"))
    mutate(presentation)
    path.write_text(json.dumps(presentation), encoding="utf-8")
    manifest["files"]["presentation"]["sha256"] = hashlib.sha256(
        path.read_bytes()
    ).hexdigest()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(RenderDatasetError, match="content generation mismatch"):
        load_render_dataset(source)


def test_v2_compatibility_is_preserved_and_v1_remains_explicitly_unsupported(tmp_path):
    source = _copy_fixture(tmp_path)
    manifest_path = source / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    presentation = manifest["files"].pop("presentation")
    manifest["schema"] = "bbtool.reference_analysis.v2"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    (source / presentation["path"]).unlink()
    assert load_render_dataset(source).presentation is None

    manifest["schema"] = "bbtool.reference_analysis.v1"
    manifest["files"].pop("analysis_health")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(RenderDatasetError, match="unsupported schema"):
        load_render_dataset(source)


def test_served_report_renders_healthy_analysis_health():
    _root, html = render_served_report(FIXTURE)
    assert "Analysis health: Healthy" in html
    assert "No result-affecting warnings" in html


def test_served_report_renders_degraded_health_with_projection_pass(tmp_path):
    source = _copy_fixture(tmp_path)
    _rewrite_payload_and_hash(
        source,
        "analysis_health",
        lambda value: value.update(
            status="degraded",
            counts={
                **value["counts"],
                "result_affecting_warnings": 1,
                "unresolved_references_relevant_to_save": 1,
            },
            warning_categories=[{"code": "unresolved_references", "count": 1}],
        ),
    )

    _root, html = render_served_report(source)

    assert "Analysis health: Degraded" in html
    assert "Unresolved references: 1" in html
    assert "Projection validation: <strong>PASS</strong>" in html
    assert "separate from overall analysis health" in html


def test_served_report_renders_recoverable_parsing_failure_category(tmp_path):
    source = _copy_fixture(tmp_path)
    _rewrite_payload_and_hash(
        source,
        "analysis_health",
        lambda value: value.update(
            status="degraded",
            counts={
                **value["counts"],
                "result_affecting_warnings": 1,
                "recoverable_parsing_failures": 1,
            },
            warning_categories=[{
                "code": "recoverable_parsing_failures", "count": 1
            }],
        ),
    )

    _root, html = render_served_report(source)

    assert "Analysis health: Degraded" in html
    assert "Recoverable parsing failures: 1" in html
    assert "offset" not in html


def test_health_with_unresolved_recruit_equipment_round_trips(tmp_path):
    source = _copy_fixture(tmp_path)
    health = build_run_health(
        [], [], {},
        parse_diagnostics={"recoverable_failures": [{
            "kind": "unresolved_recruit_equipment",
            "reference_hash": "AABBCCDD",
        }]},
    )
    public = build_public_analysis_health(health)
    _rewrite_payload_and_hash(
        source, "analysis_health", lambda value: value.update(public)
    )

    dataset = load_render_dataset(source)

    assert dataset.analysis_health["counts"] == {
        "result_affecting_warnings": 1,
        "recoverable_parsing_failures": 1,
        "unresolved_references_relevant_to_save": 1,
        "unresolved_backgrounds_relevant_to_save": 0,
        "unresolved_recruit_equipment_relevant_to_save": 1,
    }
    assert dataset.analysis_health["warning_categories"] == [
        {"code": "recoverable_parsing_failures", "count": 1},
        {"code": "unresolved_references", "count": 1},
    ]


@pytest.mark.parametrize(
    "counts,validation,categories,message",
    [
        (
            {"unresolved_backgrounds_relevant_to_save": 1},
            None,
            [{"code": "unresolved_backgrounds", "count": 1}],
            "unresolved background count is inconsistent",
        ),
        (
            {
                "recoverable_parsing_failures": 1,
                "result_affecting_warnings": 1,
            },
            {"status": "fail", "roll_range_violations": 1},
            [
                {"code": "recoverable_parsing_failures", "count": 1},
                {"code": "projection_validation_violations", "count": 1},
            ],
            "result-affecting warning count is inconsistent",
        ),
    ],
)
def test_render_dataset_rejects_contradictory_health_counts(
    tmp_path, counts, validation, categories, message
):
    source = _copy_fixture(tmp_path)

    def mutate(value):
        value["counts"].update(counts)
        value["status"] = (
            "degraded"
            if value["counts"]["result_affecting_warnings"]
            else "healthy"
        )
        value["warning_categories"] = categories
        if validation is not None:
            value["projection_validation"] = validation

    _rewrite_payload_and_hash(source, "analysis_health", mutate)

    with pytest.raises(RenderDatasetError, match=message):
        load_render_dataset(source)


@pytest.mark.parametrize(
    "mutation,message",
    [
        (lambda value: value.update(status="unknown"), "status contradicts"),
        (
            lambda value: value["counts"].update(
                recoverable_parsing_failures="one"
            ),
            "counts must be non-negative integers",
        ),
        (
            lambda value: value.update(
                warning_categories=[{"code": "private_parser_detail", "count": 1}]
            ),
            "warning_categories are malformed",
        ),
    ],
)
def test_render_dataset_rejects_malformed_health_contract(
    tmp_path, mutation, message
):
    source = _copy_fixture(tmp_path)
    _rewrite_payload_and_hash(source, "analysis_health", mutation)
    with pytest.raises(RenderDatasetError, match=message):
        load_render_dataset(source)


@pytest.mark.parametrize("mutation, message", [
    (lambda manifest: manifest.update(schema="unknown.v9"), "unsupported schema"),
    (lambda manifest: manifest["files"].pop("roster"), "manifest files mismatch"),
])
def test_load_render_dataset_rejects_incompatible_manifest(tmp_path, mutation, message):
    source = _copy_fixture(tmp_path)
    manifest_path = source / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    mutation(manifest)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(RenderDatasetError, match=message):
        load_render_dataset(source)


def test_load_render_dataset_rejects_corrupt_file_before_render(tmp_path):
    source = _copy_fixture(tmp_path)
    (source / "reference-roster.json").write_text("{broken", encoding="utf-8")
    with pytest.raises(RenderDatasetError, match="SHA-256 mismatch for roster"):
        load_render_dataset(source)

    out = tmp_path / "out"
    with pytest.raises(RenderDatasetError, match="SHA-256 mismatch for roster"):
        run_render_only(_options(source, out))
    assert not out.exists()


def test_load_render_dataset_reports_malformed_json_with_matching_hash(tmp_path):
    source = _copy_fixture(tmp_path)
    roster = source / "reference-roster.json"
    roster.write_text("{broken", encoding="utf-8")
    manifest_path = source / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"]["roster"]["sha256"] = hashlib.sha256(roster.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(RenderDatasetError, match="malformed JSON in roster"):
        load_render_dataset(source)


def test_load_render_dataset_reports_invalid_utf8_with_matching_hash(tmp_path):
    source = _copy_fixture(tmp_path)
    roster = source / "reference-roster.json"
    roster.write_bytes(b"\xff")
    manifest_path = source / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"]["roster"]["sha256"] = hashlib.sha256(b"\xff").hexdigest()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(RenderDatasetError, match="invalid UTF-8 in roster"):
        load_render_dataset(source)


@pytest.mark.parametrize("label, mutation, missing", [
    ("role_fit", lambda rows: rows[0].pop("ProjectedFitPct"), "ProjectedFitPct"),
    ("classification", lambda rows: rows[0].pop("Category"), "Category"),
])
def test_renderer_fields_are_validated_before_output_creation(
    tmp_path, label, mutation, missing
):
    source = _copy_fixture(tmp_path)
    _rewrite_payload_and_hash(source, label, mutation)
    out = tmp_path / "out"
    with pytest.raises(
        RenderDatasetError,
        match=rf"renderer contract rejected.*{missing}",
    ):
        run_render_only(_options(source, out))
    assert not out.exists()


def test_renderer_field_types_are_validated_before_output_creation(tmp_path):
    source = _copy_fixture(tmp_path)
    _rewrite_payload_and_hash(
        source, "role_fit", lambda rows: rows[0].update(ProjectedFitPct="high")
    )
    out = tmp_path / "out"
    with pytest.raises(RenderDatasetError, match="renderer contract rejected"):
        run_render_only(_options(source, out))
    assert not out.exists()


def test_hidden_future_roll_key_is_rejected_in_every_public_payload(tmp_path):
    source = _copy_fixture(tmp_path)
    _rewrite_payload_and_hash(
        source,
        "archetypes",
        lambda payload: payload.update(FutureRolls={"HP": [4]}),
    )
    with pytest.raises(RenderDatasetError, match="must not contain FutureRolls"):
        load_render_dataset(source)


@pytest.mark.parametrize("field", ["NativeEntityToken", "BrotherIdentity"])
def test_private_brother_identity_fields_are_rejected(tmp_path, field):
    source = _copy_fixture(tmp_path)
    _rewrite_payload_and_hash(
        source,
        "roster",
        lambda rows: rows[0].update({field: 123}),
    )
    with pytest.raises(RenderDatasetError, match="private identity fields"):
        load_render_dataset(source)


def test_future_rolls_text_in_a_display_value_is_allowed(tmp_path):
    source = _copy_fixture(tmp_path)
    _rewrite_payload_and_hash(
        source,
        "recruits",
        lambda rows: rows[0].update(Title="the FutureRolls Historian"),
    )
    dataset = load_render_dataset(source)
    assert dataset.recruits[0]["Title"] == "the FutureRolls Historian"


def test_render_only_packages_public_json_and_report_without_analysis(tmp_path):
    workspace, archive = run_render_only(_options(FIXTURE, tmp_path / "out"))
    assert archive.is_file()
    assert (workspace.root / "manifest.json").is_file()
    assert (workspace.root / "report.css").is_file()
    assert (workspace.root / "report.js").is_file()
    reports = list(workspace.root.glob("*-report.html"))
    assert len(reports) == 1
    html = reports[0].read_text(encoding="utf-8")
    expected = render_report_launcher(workspace.source_save, workspace.generated_at)
    assert html == expected
    assert "Aldric" not in html
    assert "Reference Hamlet" not in html
    assert "--serve-report" in html

    root, served = render_served_report(workspace.root)
    assert root == workspace.root.resolve()
    assert "Aldric" in served
    assert "Reference Hamlet" in served
    report_file = next(workspace.root.glob("*-report.html"))
    assert render_served_report(report_file)[0] == workspace.root.resolve()


def test_generated_manifest_is_self_contained_and_versioned(tmp_path):
    workspace, _archive = run_render_only(_options(FIXTURE, tmp_path / "out"))
    manifest = json.loads((workspace.root / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema"] == TARGET_DATASET_SCHEMA
    assert set(manifest["files"]) == render_only.TARGET_REQUIRED_FILES
    assert all(
        (workspace.root / entry["path"]).is_file()
        for entry in manifest["files"].values()
    )


@pytest.mark.parametrize(
    "label, mutate, message",
    [
        ("roster", lambda value: {"row": value[0]}, "roster root must be an array"),
        ("recruits", lambda value: ["bad"], "recruit rows must be objects"),
        ("role_fit", lambda value: ["bad"], "role_fit and classification rows must be objects"),
        ("classification", lambda value: ["bad"], "role_fit and classification rows must be objects"),
        ("archetypes", lambda value: [], "archetypes root must be an object"),
        ("classification_config", lambda value: [], "classification_config root must be an object"),
    ],
)
def test_render_dataset_rejects_invalid_payload_roots(tmp_path, label, mutate, message):
    source = _copy_fixture(tmp_path)
    _rewrite_payload_and_hash(source, label, lambda value: None)
    manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    payload_path = source / manifest["files"][label]["path"]
    original = json.loads((FIXTURE / manifest["files"][label]["path"]).read_text(encoding="utf-8"))
    payload_path.write_text(json.dumps(mutate(original)), encoding="utf-8")
    manifest["files"][label]["sha256"] = hashlib.sha256(payload_path.read_bytes()).hexdigest()
    (source / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(RenderDatasetError, match=message):
        load_render_dataset(source)


@pytest.mark.parametrize(
    "label, mutate, message",
    [
        ("roster", lambda rows: rows.append(dict(rows[0])), "duplicate BrotherID"),
        ("role_fit", lambda rows: rows.pop(), "exactly one row per brother and role"),
        ("classification", lambda rows: rows.pop(), "BrotherID values do not match"),
        ("classification", lambda rows: rows[0].update(BestRole="missing"), "BestRole values"),
        ("archetypes", lambda value: value["roles"].append(dict(value["roles"][0])), "duplicate role names"),
    ],
)
def test_render_dataset_rejects_inconsistent_relations(tmp_path, label, mutate, message):
    source = _copy_fixture(tmp_path)
    _rewrite_payload_and_hash(source, label, mutate)
    with pytest.raises(RenderDatasetError, match=message):
        load_render_dataset(source)


def test_render_only_reports_browser_launch_failures(monkeypatch, tmp_path, capsys):
    options = _options(FIXTURE, tmp_path / "out")
    options = CliOptions(**{**options.__dict__, "open_report": True})
    monkeypatch.setattr("bbtool.app.report_server.launch_report_server", lambda _root: False)
    run_render_only(options)
    assert "browser did not confirm" in capsys.readouterr().out


@pytest.mark.parametrize(
    "mutate, message",
    [
        (lambda manifest: manifest["files"].__setitem__("roster", "bad"), "must be an object"),
        (lambda manifest: manifest["files"]["roster"].update(path="../escape.json"), "unsafe path"),
        (lambda manifest: manifest["files"]["roster"].update(path="missing.json"), "not found"),
    ],
)
def test_render_dataset_rejects_invalid_manifest_entries(tmp_path, mutate, message):
    source = _copy_fixture(tmp_path)
    manifest_path = source / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    mutate(manifest)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(RenderDatasetError, match=message):
        load_render_dataset(source)


@pytest.mark.parametrize(
    "label, mutate, message",
    [
        ("roster", lambda rows: rows.__setitem__(0, "bad"), r"roster\[0\] must be an object"),
        ("roster", lambda rows: rows[0].update(BrotherID="human:999"), "does not match HumanOffset"),
        ("role_fit", lambda rows: rows[0].update(BrotherID="human:999"), "BrotherID values do not match"),
        ("role_fit", lambda rows: rows[0].update(Role="missing"), "Role values do not match"),
        ("classification", lambda rows: rows.append(dict(rows[0])), "exactly one row per brother"),
        ("archetypes", lambda value: value.update(roles=[]), "non-empty array"),
    ],
)
def test_render_dataset_rejects_additional_contract_violations(tmp_path, label, mutate, message):
    source = _copy_fixture(tmp_path)
    _rewrite_payload_and_hash(source, label, mutate)
    with pytest.raises(RenderDatasetError, match=message):
        load_render_dataset(source)
