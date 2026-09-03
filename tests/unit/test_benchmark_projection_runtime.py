import pytest

from tools.benchmark_projection_runtime import _representative_brothers


pytestmark = pytest.mark.unit


def test_representative_issue_131_shapes_are_sanitized_and_deterministic():
    first = _representative_brothers()
    second = _representative_brothers()

    assert first == second
    assert [(bro.Level, bro.RAtk, bro.MDef) for bro in first] == [
        (1, 48, 5),
        (3, 63, 1),
    ]
    assert all(bro.Name.startswith("Representative ") for bro in first)
    assert all(not bro.TraitIDs and not bro.InjuryIDs for bro in first)
