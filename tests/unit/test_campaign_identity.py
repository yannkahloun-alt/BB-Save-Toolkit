import math
import struct
from pathlib import Path

import pytest

from bbtool.models import CampaignIdentity
from bbtool.save_parser import parse_campaign_identity, parse_campaign_identity_bytes

pytestmark = [pytest.mark.unit, pytest.mark.parser]


def _string(value: str) -> bytes:
    raw = value.encode("utf-8")
    return struct.pack("<H", len(raw)) + raw


def _asset_manager_tail(campaign_id: int, *, seed: str = "ABCDEFGHIJ") -> bytes:
    # asset_manager.onSerialize() source order, beginning after Stash.
    return b"".join((
        struct.pack("<i", campaign_id),
        _string("The Company"),
        _string("banner_06"),
        bytes((6, 1, 2, 2, 0, 1)),
        _string("scenario.early_access"),
        _string(seed),
        struct.pack(
            "<ffffIffHBfBB",
            2000.0, 40.0, 20.0, 10.0, 100, 50.0, 12.5,
            1, 8, 42.0, 0, 1,
        ),
    ))


def test_parses_source_order_and_does_not_use_seed_as_identity():
    first = parse_campaign_identity_bytes(
        b"variable stash" + _asset_manager_tail(123456789)
    )
    second = parse_campaign_identity_bytes(
        b"different stash" + _asset_manager_tail(123456789, seed="ZZZZZZZZZZ")
    )

    assert first == second
    assert first.value == 123456789
    assert first.basis == "native_campaign_id"
    assert first.confidence == "exact"
    assert first.reason is None


def test_same_campaign_id_is_stable_across_other_serialized_changes():
    before = parse_campaign_identity_bytes(
        b"early snapshot" + _asset_manager_tail(314159, seed="CAMPAIGN01")
    )
    after = parse_campaign_identity_bytes(
        b"later snapshot with unrelated serialized state"
        + _asset_manager_tail(314159, seed="CAMPAIGN01")
    )

    assert before == after == CampaignIdentity(314159, confidence="exact")


def test_same_map_seed_independent_campaign_ids_remain_separate():
    first = parse_campaign_identity_bytes(
        _asset_manager_tail(101, seed="SHAREDSEED")
    )
    second = parse_campaign_identity_bytes(
        _asset_manager_tail(202, seed="SHAREDSEED")
    )

    assert first == CampaignIdentity(101, confidence="exact")
    assert second == CampaignIdentity(202, confidence="exact")
    assert first != second


def test_missing_invalid_and_ambiguous_evidence_fail_conservatively():
    assert parse_campaign_identity_bytes(b"no asset manager").confidence == "unavailable"

    negative = parse_campaign_identity_bytes(_asset_manager_tail(-1))
    assert (negative.value, negative.confidence, negative.reason) == (
        None, "invalid", "negative_value"
    )

    ambiguous = parse_campaign_identity_bytes(
        _asset_manager_tail(1) + _asset_manager_tail(2)
    )
    assert (ambiguous.value, ambiguous.confidence, ambiguous.reason) == (
        None, "invalid", "ambiguous"
    )

    corrupt = bytearray(_asset_manager_tail(7))
    corrupt[-6:-2] = struct.pack("<f", math.nan)
    assert parse_campaign_identity_bytes(bytes(corrupt)).confidence == "unavailable"


def test_checked_in_reference_save_and_path_rename_are_deterministic(tmp_path):
    source = (
        Path(__file__).resolve().parents[1]
        / "fixtures" / "full_preview" / "reference-save.sav"
    )
    expected = parse_campaign_identity_bytes(source.read_bytes())
    assert (expected.value, expected.confidence) == (25809, "exact")

    renamed = tmp_path / "renamed-and-copied.sav"
    renamed.write_bytes(source.read_bytes())
    assert parse_campaign_identity(renamed) == expected
