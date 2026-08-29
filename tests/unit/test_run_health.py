from types import SimpleNamespace

from bbtool.app.health import build_run_health, print_run_health


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
    assert "No result-affecting warnings." in capsys.readouterr().out


def test_run_health_counts_plain_unknown_parser_fallback():
    health = build_run_health(
        [],
        [{"Background": "Unknown"}],
        {},
    )

    assert health["unresolved_references_relevant_to_save"] == 1
    assert health["result_affecting_warnings"] == 1


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
