from types import SimpleNamespace

from bbtool.app.health import (
    build_public_analysis_health,
    build_run_health,
    print_run_health,
)


def test_public_analysis_health_is_healthy_and_projection_passes():
    public = build_public_analysis_health(build_run_health([], [], {}))

    assert public == {
        "schema": "bbtool.analysis_health.v1",
        "status": "healthy",
        "counts": {
            "result_affecting_warnings": 0,
            "recoverable_parsing_failures": 0,
            "unresolved_references_relevant_to_save": 0,
            "unresolved_backgrounds_relevant_to_save": 0,
            "unresolved_recruit_equipment_relevant_to_save": 0,
        },
        "projection_validation": {
            "status": "pass",
            "roll_range_violations": 0,
        },
        "warning_categories": [],
    }


def test_public_health_keeps_projection_pass_distinct_from_degraded_inputs():
    health = build_run_health(
        [{"Background": "Unknown [AABB]", "Traits": []}], [], {},
        validation_payload={"summary": {"roll_range_violations": 0}},
    )

    public = build_public_analysis_health(health)

    assert public["status"] == "degraded"
    assert public["projection_validation"]["status"] == "pass"
    assert public["warning_categories"] == [
        {"code": "unresolved_references", "count": 1},
        {"code": "unresolved_backgrounds", "count": 1},
    ]


def test_public_health_exposes_parsing_failure_count_without_private_sample():
    health = build_run_health(
        [], [], {},
        parse_diagnostics={"recoverable_failures": [{
            "kind": "truncated_record", "offset": "C:/private/save.sav"
        }]},
    )

    public = build_public_analysis_health(health)

    assert public["status"] == "degraded"
    assert public["counts"]["recoverable_parsing_failures"] == 1
    assert public["warning_categories"] == [
        {"code": "recoverable_parsing_failures", "count": 1}
    ]
    assert "private" not in str(public)


def test_run_health_aggregates_result_warnings_and_fallbacks(capsys):
    cache = SimpleNamespace(
        miss_reasons={"archetype_changed": 2, "role_artifact_invalid": 1},
        stats=SimpleNamespace(
            previous_found=True,
            role_computed=2,
            advisor_computed=1,
            summary_computed=1,
        ),
    )
    bro = SimpleNamespace(
        Background="Unknown [AABBCCDD]",
        Perks=[],
        Traits=["Known", "Unknown [11223344]"],
        Injuries=[],
        PermanentInjuries=[],
    )

    health = build_run_health(
        [bro],
        [],
        {"generated_dictionary": True, "generated_traits": False},
        parse_diagnostics={
            "recoverable_failures": [
                {"scope": "roster", "kind": "circle_metadata_unresolved"}
            ]
        },
        incremental_cache=cache,
        validation_payload={"summary": {"roll_range_violations": 1}},
    )

    assert health["result_affecting_warnings"] == 4
    assert health["recoverable_parsing_failures"] == 1
    assert health["unresolved_references_relevant_to_save"] == 2
    assert health["unresolved_backgrounds_relevant_to_save"] == 1
    assert health["validation_roll_range_violations"] == 1
    assert health["cache_fallbacks"] == 3
    assert health["conservative_recomputations"] == 4
    assert health["informational_notices"] == 3
    assert health["cache_fallback_reasons"] == {
        "archetype_changed": 2,
        "role_artifact_invalid": 1,
    }

    print_run_health(health, "run-debug.json")
    output = capsys.readouterr().out
    assert "result-affecting warnings: 4" in output
    assert "No result-affecting warnings." not in output
    assert "run-debug.json $.runtime.run_health" in output
    assert "unresolved backgrounds relevant to save: 1" in output


def test_run_health_prints_explicit_clean_statement(capsys):
    health = build_run_health([], [], {})

    assert health["result_affecting_warnings"] == 0
    assert health["recoverable_parsing_failures"] == 0
    assert health["unresolved_references_relevant_to_save"] == 0
    assert health["unresolved_backgrounds_relevant_to_save"] == 0
    assert health["cache_fallbacks"] == 0
    assert health["conservative_recomputations"] == 0

    print_run_health(health, None)
    output = capsys.readouterr().out
    assert "No result-affecting warnings." in output
    assert "no unresolved references are present in the current save" in output
    assert "analysis results are unaffected" in output


def test_run_health_counts_plain_unknown_parser_fallback():
    health = build_run_health(
        [],
        [{"Background": "Unknown"}],
        {},
    )

    assert health["unresolved_references_relevant_to_save"] == 1
    assert health["result_affecting_warnings"] == 1


def test_upstream_unresolved_references_are_informational_when_save_uses_none():
    health = build_run_health(
        [],
        [],
        {"dictionary_stats": {"unresolved": 67}},
    )

    assert health["unresolved_references_relevant_to_save"] == 0
    assert health["result_affecting_warnings"] == 0


def test_run_health_does_not_double_count_permanent_injury_alias():
    injury = "Unknown [DEADBEEF]"
    bro = SimpleNamespace(
        Background="Known",
        Perks=[],
        Traits=[],
        Injuries=[injury],
        PermanentInjuries=[injury],
    )

    health = build_run_health([bro], [], {})

    assert health["unresolved_references_relevant_to_save"] == 1
    assert health["unresolved_reference_sample"] == [injury]


def test_run_health_warns_for_unresolved_recruit_equipment(capsys):
    equipment_hash = "AABBCCDD"
    health = build_run_health(
        [],
        [{"Background": "Farmhand", "Traits": [], "HireCost": None}],
        {},
        parse_diagnostics={
            "recoverable_failures": [{
                "scope": "recruits",
                "kind": "unresolved_recruit_equipment",
                "reference_hash": equipment_hash,
            }]
        },
    )

    assert health["result_affecting_warnings"] == 1
    assert health["unresolved_references_relevant_to_save"] == 1
    assert health["unresolved_recruit_equipment_relevant_to_save"] == 1
    assert health["unresolved_recruit_equipment_hash_sample"] == [equipment_hash]
    assert health["unresolved_reference_sample"] == [
        f"Unknown equipment [{equipment_hash}]"
    ]

    print_run_health(health, None)
    output = capsys.readouterr().out
    assert "WARNING: unresolved reference data affects the current analysis" in output
    assert "analysis results are unaffected" not in output
