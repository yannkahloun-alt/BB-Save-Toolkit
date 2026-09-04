from dataclasses import replace
import json
from pathlib import Path

from bbtool.models import CampaignIdentity
from bbtool.app.output import public_brother_data
from bbtool.save_parser import (
    BROTHER_SIGNATURE,
    native_brother_token_at,
    parse_roster,
    resolve_brother_identities,
)


def test_container_token_is_read_immediately_before_signature():
    signature_offset = 32
    data = bytearray(signature_offset + len(BROTHER_SIGNATURE))
    data[signature_offset - 17:signature_offset - 13] = (123456).to_bytes(4, "little")
    data[signature_offset:] = BROTHER_SIGNATURE

    assert native_brother_token_at(bytes(data), signature_offset) == 123456
    assert native_brother_token_at(bytes(data), 16) is None


def test_zero_is_parsed_but_wrong_signature_has_no_native_token():
    signature_offset = 32
    data = bytearray(signature_offset + len(BROTHER_SIGNATURE))
    data[signature_offset:] = BROTHER_SIGNATURE
    assert native_brother_token_at(bytes(data), signature_offset) == 0
    data[signature_offset - 17:signature_offset - 13] = (7).to_bytes(4, "little")
    data[signature_offset] = 1
    assert native_brother_token_at(bytes(data), signature_offset) is None


def test_reference_save_exposes_unique_native_tokens():
    reference_save = (
        Path(__file__).resolve().parents[1]
        / "fixtures"
        / "full_preview"
        / "reference-save.sav"
    )
    roster = parse_roster(reference_save)
    tokens = [bro.NativeEntityToken for bro in roster]
    assert len(tokens) == 12
    assert all(isinstance(token, int) and token > 0 for token in tokens)
    assert len(set(tokens)) == len(tokens)


def test_sanitized_successive_save_evidence_proves_token_continuity():
    path = (
        Path(__file__).resolve().parents[1]
        / "fixtures"
        / "brother_identity"
        / "successive-save-evidence.json"
    )
    evidence = json.loads(path.read_text(encoding="utf-8"))
    assert evidence["schema"] == "bbtool.brother_identity_evidence.v1"
    assert len(evidence["snapshots"]) == 18
    assert {row["campaign"] for row in evidence["snapshots"]} == {7496, 17110}
    assert len(evidence["tracks"]) == 22

    observations = [
        observation
        for track in evidence["tracks"]
        for observation in track["observations"]
    ]
    assert len(observations) == 150
    for track in evidence["tracks"]:
        assert len({row["token"] for row in track["observations"]}) == 1
        assert all(row["token"] > 0 for row in track["observations"])

    for snapshot in evidence["snapshots"]:
        tokens = [
            row["token"]
            for track in evidence["tracks"]
            if track["campaign"] == snapshot["campaign"]
            for row in track["observations"]
            if row["snapshot"] == snapshot["snapshot"]
        ]
        assert len(tokens) == snapshot["roster_size"]
        assert len(tokens) == len(set(tokens))

    changed_fields = {
        field
        for field in (
            "human_offset",
            "level",
            "xp",
            "stats",
            "perks",
            "traits",
            "permanent_injuries",
            "equipment",
            "future_rolls",
        )
        if any(
            len({row[field] for row in track["observations"]}) > 1
            for track in evidence["tracks"]
        )
    }
    assert changed_fields == {
        "human_offset",
        "level",
        "xp",
        "stats",
        "perks",
        "traits",
        "permanent_injuries",
        "equipment",
        "future_rolls",
    }


def test_exact_identity_is_campaign_namespaced_and_display_independent(bro_factory):
    first = bro_factory(Name="Old", HumanOffset=10, NativeEntityToken=88)
    renamed = replace(first, Name="New", HumanOffset=999, Level=4, XP=1000)

    a = resolve_brother_identities(
        [first], CampaignIdentity(7, confidence="exact")
    )[first.BrotherID]
    b = resolve_brother_identities(
        [renamed], CampaignIdentity(7, confidence="exact")
    )[renamed.BrotherID]
    other = resolve_brother_identities(
        [renamed], CampaignIdentity(8, confidence="exact")
    )[renamed.BrotherID]

    assert a.confidence == b.confidence == other.confidence == "exact"
    assert a.value == b.value == "campaign:7/entity:88"
    assert other.value == "campaign:8/entity:88"
    assert other.value != a.value
    assert "NativeEntityToken" not in public_brother_data(first)


def test_missing_malformed_duplicate_or_nonexact_campaign_disables_identity(bro_factory):
    missing = bro_factory(HumanOffset=1, NativeEntityToken=None)
    malformed = bro_factory(HumanOffset=4, NativeEntityToken=0)
    duplicate_a = bro_factory(HumanOffset=2, NativeEntityToken=44)
    duplicate_b = bro_factory(HumanOffset=3, NativeEntityToken=44)
    resolved = resolve_brother_identities(
        [missing, malformed, duplicate_a, duplicate_b],
        CampaignIdentity(9, confidence="exact"),
    )

    assert resolved[missing.BrotherID].confidence == "unavailable"
    assert resolved[missing.BrotherID].reason == "native_token_missing"
    assert resolved[malformed.BrotherID].confidence == "invalid"
    assert resolved[malformed.BrotherID].reason == "native_token_malformed"
    assert resolved[duplicate_a.BrotherID].confidence == "invalid"
    assert resolved[duplicate_b.BrotherID].reason == "duplicate_native_token"
    assert all(identity.value is None for identity in resolved.values())

    unavailable = resolve_brother_identities(
        [duplicate_a],
        CampaignIdentity(None, confidence="invalid", reason="ambiguous"),
    )[duplicate_a.BrotherID]
    assert unavailable.confidence == "unavailable"
    assert unavailable.reason == "campaign_identity_invalid"
