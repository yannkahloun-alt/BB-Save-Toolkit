"""Versioned Target UI presentation metadata and coherence validation."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict
import re
from typing import Any

from ..build_identity import build_definition_hash, build_identity
from ..company_planning import build_intrinsic_company_coverage
from ..incremental.dependencies import ArtifactKind, ENGINE_VERSIONS, stable_hash
from ..incremental.fingerprint import (
    advisor_fingerprint,
    brother_projection_fingerprint,
    brother_summary_fingerprint,
    role_fingerprint,
)
from ..models import BrotherIdentity, CampaignIdentity
from ..perk_gear import perk_gear_facts
from ..recruitment_prior import (
    load_background_potential_reference,
    recruit_candidate_estimate,
)


SCHEMA = "bbtool.target_presentation.v1"
DATASET_SCHEMA = "bbtool.reference_analysis.v3"
LEGACY_DATASET_SCHEMAS = frozenset({"bbtool.reference_analysis.v2"})
BOUND_ARTIFACTS = frozenset({
    "roster", "recruits", "role_fit", "classification", "archetypes",
    "classification_config", "analysis_health",
})
SHA256_PATTERN = re.compile(r"sha256:[0-9a-f]{64}\Z")
BROTHER_IDENTITY_PATTERN = re.compile(r"campaign:(\d+)/entity:(\d+)\Z")
CAMPAIGN_ID_MAX = 2_147_483_647
ENTITY_TOKEN_MAX = 4_294_967_295
PRIOR_ASSUMPTIONS = {
    "starting_stats": "lower integer midpoint of each vanilla level-1 range",
    "talents": "vanilla three-distinct-stat 60/30/10 star lottery",
    "traits_and_injuries": "none; recruit-specific evidence is excluded",
    "projection": "existing blind natural level-11 Fit trajectory",
}
PUBLIC_RECRUIT_FIELDS = ["BackgroundSaveHash", "RevealedTraitEvidence"]
EXCLUDED_RECRUIT_FIELDS = [
    "level", "settlement", "name", "title", "hire_cost", "daily_wage",
    "roster_need", "assigned_build", "hidden_stats", "talent_stars", "future_rolls",
]


def build_recruitment_presentation(recruits, roles, reference_path) -> list[dict]:
    """Build the established #110/#111 state without inventing recruit identity."""
    reference = None
    rows = []
    for index, recruit in enumerate(recruits):
        analyses = []
        for role in roles:
            identity = build_identity(role)
            if identity is None:
                analyses.append({"build_identity": None, "state": "unavailable",
                                 "reason": "build_identity_unavailable", "result": None})
                continue
            if not recruit.get("BackgroundSaveHash"):
                analyses.append({"build_identity": identity, "state": "unavailable",
                                 "reason": "background_identity_unavailable", "result": None})
                continue
            try:
                if reference is None:
                    reference = load_background_potential_reference(reference_path)
                result = recruit_candidate_estimate(recruit, role, reference)
            except (KeyError, ValueError, OSError) as exc:
                analyses.append({"build_identity": identity, "state": "unavailable",
                                 "reason": type(exc).__name__, "result": None})
            else:
                analyses.append({"build_identity": identity, "state": result["state"],
                                 "reason": None, "result": result})
        rows.append({
            "recruit_index": index,
            "background_save_hash": recruit.get("BackgroundSaveHash"),
            "analyses": analyses,
        })
    return rows


def _identity_payload(identity: CampaignIdentity | BrotherIdentity | None) -> dict:
    if identity is None:
        return {"value": None, "basis": None, "confidence": "unavailable",
                "reason": "not_provided"}
    data = asdict(identity)
    return {
        "value": getattr(identity, "value", None),
        "basis": data["basis"],
        "confidence": data["confidence"],
        "reason": data.get("reason"),
    }


def build_target_presentation(
    *, bros, recruits: list[dict], roles: list[dict], analysis_health: dict,
    campaign_identity: CampaignIdentity | None,
    brother_identities: Mapping[str, BrotherIdentity] | None,
    source_fingerprint: str, configuration_fingerprints: Mapping[str, str],
    recruitment_analysis: list[dict], artifact_hashes: Mapping[str, str],
    result_signatures: Mapping[str, list[dict]],
    company_intrinsic_coverage: list[dict],
) -> dict:
    """Build only established Target UI semantics; unresolved domains are explicit."""
    identities = brother_identities or {}
    builds = []
    for role in roles:
        builds.append({
            "build_identity": build_identity(role),
            "build_definition_hash": build_definition_hash(role),
            "display_name": role["name"],
        })
    brothers = [{
        "brother_id": bro.BrotherID,
        "brother_identity": _identity_payload(identities.get(bro.BrotherID)),
        "mechanical_facts": list(
            getattr(bro, "PerkGearFacts", None) or perk_gear_facts(bro)
        ),
    } for bro in bros]
    validity = {
        "basis": "result_local_dependency_signature",
        "artifacts": dict(result_signatures),
    }
    company = {"intrinsic_coverage": company_intrinsic_coverage}
    pending = {
        "assigned_build": 107,
        "intent_aware_advisor": 108,
        "intent_aware_company_planning": 166,
        "relevant_roster_need": 112,
    }
    content = {
        "campaign_identity": _identity_payload(campaign_identity),
        "brothers": brothers,
        "builds": builds,
        "run_health": analysis_health,
        "recruitment": recruitment_analysis,
        "validity": validity,
        "company": company,
        "pending": pending,
    }
    provenance = {
        "source_fingerprint": source_fingerprint,
        "configuration_fingerprints": dict(sorted(configuration_fingerprints.items())),
        "artifact_hashes": {
            key: artifact_hashes[key] for key in sorted(BOUND_ARTIFACTS)
        },
        "content_hashes": {
            key: stable_hash(value) for key, value in sorted(content.items())
        },
    }
    return {
        "schema": SCHEMA,
        "publication": {
            "coherence_signature": stable_hash(provenance),
            "provenance": provenance,
        },
        **content,
    }


def validate_target_presentation(
    payload: Any, *, payloads: Mapping[str, Any], artifact_hashes: Mapping[str, str],
    bros,
) -> None:
    """Reject malformed or mixed-generation presentation datasets."""
    if not isinstance(payload, dict) or set(payload) != {
        "schema", "publication", "campaign_identity", "brothers", "builds",
        "run_health", "recruitment", "validity", "company", "pending",
    }:
        raise ValueError("target presentation fields mismatch")
    if payload["schema"] != SCHEMA:
        raise ValueError("unsupported target presentation schema")
    publication = payload["publication"]
    if not isinstance(publication, dict) or set(publication) != {
        "coherence_signature", "provenance",
    }:
        raise ValueError("target presentation publication fields mismatch")
    provenance = publication["provenance"]
    if not isinstance(provenance, dict) or set(provenance) != {
        "source_fingerprint", "configuration_fingerprints", "artifact_hashes",
        "content_hashes",
    }:
        raise ValueError("target presentation provenance fields mismatch")
    if provenance["artifact_hashes"] != {
        key: artifact_hashes[key] for key in sorted(BOUND_ARTIFACTS)
    }:
        raise ValueError("target presentation artifact generation mismatch")
    if publication["coherence_signature"] != stable_hash(provenance):
        raise ValueError("target presentation coherence signature mismatch")
    expected_content_hashes = {
        key: stable_hash(payload[key]) for key in (
            "brothers", "builds", "campaign_identity", "company", "pending",
            "recruitment", "run_health", "validity",
        )
    }
    if provenance["content_hashes"] != expected_content_hashes:
        raise ValueError("target presentation content generation mismatch")
    if not isinstance(provenance["source_fingerprint"], str) or \
            SHA256_PATTERN.fullmatch(provenance["source_fingerprint"]) is None:
        raise ValueError("target presentation source fingerprint is malformed")
    config = provenance["configuration_fingerprints"]
    if not isinstance(config, dict) or config != {
        "archetypes": stable_hash(payloads["archetypes"]["roles"]),
        "classification": stable_hash(payloads["classification_config"]),
    }:
        raise ValueError("target presentation configuration fingerprints mismatch")
    if payload["run_health"] != payloads["analysis_health"]:
        raise ValueError("target presentation run health generation mismatch")

    role_by_name = {role["name"]: role for role in payloads["archetypes"]["roles"]}
    builds = payload["builds"]
    if not isinstance(builds, list) or len(builds) != len(role_by_name):
        raise ValueError("target presentation build catalog mismatch")
    build_ids = set()
    for item in builds:
        if not isinstance(item, dict) or set(item) != {
            "build_identity", "build_definition_hash", "display_name",
        } or item["display_name"] not in role_by_name:
            raise ValueError("target presentation build entry is malformed")
        role = role_by_name[item["display_name"]]
        if item["build_identity"] != build_identity(role) or \
                item["build_definition_hash"] != build_definition_hash(role):
            raise ValueError("target presentation build identity mismatch")
        if item["build_identity"] is not None:
            if item["build_identity"] in build_ids:
                raise ValueError("target presentation contains duplicate BuildIdentity")
            build_ids.add(item["build_identity"])

    roster = {row["BrotherID"]: row for row in payloads["roster"]}
    brothers = payload["brothers"]
    if not isinstance(brothers, list) or any(
        not isinstance(row, dict) for row in brothers
    ) or [row.get("brother_id") for row in brothers] != list(roster):
        raise ValueError("target presentation brother joins do not match roster")
    campaign_value = _validate_identity(payload["campaign_identity"], brother=False)
    exact_brother_identities = set()
    for row in brothers:
        if not isinstance(row, dict) or set(row) != {
            "brother_id", "brother_identity", "mechanical_facts",
        } or row["mechanical_facts"] != roster[row["brother_id"]].get("PerkGearFacts", []):
            raise ValueError("target presentation mechanical facts mismatch")
        brother_campaign = _validate_identity(row["brother_identity"], brother=True)
        if brother_campaign is not None and brother_campaign != campaign_value:
            raise ValueError("target presentation brother campaign identity mismatch")
        identity_value = row["brother_identity"]["value"]
        if identity_value is not None:
            if identity_value in exact_brother_identities:
                raise ValueError("target presentation contains duplicate BrotherIdentity")
            exact_brother_identities.add(identity_value)
    if not isinstance(payload["recruitment"], list):
        raise ValueError("target presentation recruitment must be an array")
    if any(not isinstance(row, dict) for row in payload["recruitment"]) or \
            [row.get("recruit_index") for row in payload["recruitment"]] != \
            list(range(len(payloads["recruits"]))):
        raise ValueError("target presentation recruit joins do not match recruits")
    for row in payload["recruitment"]:
        if not isinstance(row, dict) or set(row) != {
            "recruit_index", "background_save_hash", "analyses",
        } or not isinstance(row["analyses"], list):
            raise ValueError("target presentation recruitment entry is malformed")
        if row["background_save_hash"] != payloads["recruits"][
                row["recruit_index"]].get("BackgroundSaveHash"):
            raise ValueError("target presentation recruitment background mismatch")
        if any(not isinstance(item, dict) for item in row["analyses"]) or \
                [item.get("build_identity") for item in row["analyses"]] != \
                [item["build_identity"] for item in builds]:
            raise ValueError("target presentation recruitment build joins mismatch")
        recruit = payloads["recruits"][row["recruit_index"]]
        for item, build in zip(row["analyses"], builds, strict=True):
            if not isinstance(item, dict) or set(item) != {
                "build_identity", "state", "reason", "result",
            } or item["state"] not in {
                "prior_only", "known_evidence_estimate", "unavailable",
            }:
                raise ValueError("target presentation recruitment analysis is malformed")
            _validate_recruitment_analysis(
                item, background_save_hash=row["background_save_hash"],
                build_definition_hash_value=build["build_definition_hash"],
                recruit=recruit,
            )
    validity = payload["validity"]
    if not isinstance(validity, dict) or set(validity) != {"basis", "artifacts"} \
            or validity["basis"] != "result_local_dependency_signature":
        raise ValueError("target presentation validity fields mismatch")
    artifacts = validity["artifacts"]
    if not isinstance(artifacts, dict) or set(artifacts) != {
        "role_projection", "strategic_classification", "level_advisor",
    } or any(not isinstance(rows, list) for rows in artifacts.values()):
        raise ValueError("target presentation validity artifacts are malformed")
    role_keys = {
        role["name"]: role.get("id", role["name"])
        for role in payloads["archetypes"]["roles"]
    }
    role_by_key = {role_keys[role["name"]]: role for role in payloads["archetypes"]["roles"]}
    expected_role_evidence = {}
    for bro in bros:
        state = brother_projection_fingerprint(bro)
        for build_key, role in role_by_key.items():
            expected_role_evidence[(bro.BrotherID, build_key)] = stable_hash({
                "artifact": "role_projection",
                "brother_state": state,
                "build_definition": role_fingerprint(role),
                "engine_version": ENGINE_VERSIONS[ArtifactKind.ROLE_PROJECTION],
            })
    _validate_signature_evidence(
        artifacts["role_projection"], expected=expected_role_evidence,
        key_fields=("brother_id", "build_key"), roster=roster,
    )
    roles = payloads["archetypes"]["roles"]
    _validate_signature_evidence(
        artifacts["strategic_classification"],
        expected={(bro.BrotherID,): brother_summary_fingerprint(
            bro, roles, payloads["classification_config"]
        ) for bro in bros},
        key_fields=("brother_id",), roster=roster,
    )
    _validate_signature_evidence(
        artifacts["level_advisor"],
        expected={(bro.BrotherID,): advisor_fingerprint(bro, roles) for bro in bros},
        key_fields=("brother_id",), roster=roster,
    )
    company = payload["company"]
    if not isinstance(company, dict) or set(company) != {"intrinsic_coverage"} \
            or not isinstance(company["intrinsic_coverage"], list):
        raise ValueError("target presentation company fields mismatch")
    identity_by_brother = {
        row["brother_id"]: row["brother_identity"]["value"] for row in brothers
    }
    expected_company = build_intrinsic_company_coverage(
        bros, payloads["archetypes"]["roles"], payloads["role_fit"],
        payloads["classification_config"], identity_by_brother,
    )
    if company["intrinsic_coverage"] != expected_company:
        raise ValueError("target presentation company generation mismatch")
    if payload["pending"] != {
        "assigned_build": 107, "intent_aware_advisor": 108,
        "intent_aware_company_planning": 166, "relevant_roster_need": 112,
    }:
        raise ValueError("target presentation pending fields mismatch")


def _validate_identity(value: Any, *, brother: bool) -> int | None:
    if not isinstance(value, dict) or set(value) != {
        "value", "basis", "confidence", "reason",
    } or value["confidence"] not in {"exact", "unavailable", "invalid"}:
        raise ValueError("target presentation identity is malformed")
    expected = "native_campaign_entity_token" if brother else "native_campaign_id"
    if value["confidence"] == "unavailable" and value["basis"] is None:
        if value["reason"] != "not_provided":
            raise ValueError("target presentation unavailable identity is malformed")
    elif value["basis"] != expected:
        raise ValueError("target presentation identity basis is malformed")
    if value["confidence"] == "exact":
        if value["reason"] is not None or value["value"] is None:
            raise ValueError("target presentation exact identity is malformed")
        if brother:
            if not isinstance(value["value"], str):
                raise ValueError("target presentation exact identity is malformed")
            match = BROTHER_IDENTITY_PATTERN.fullmatch(value["value"])
            if match is None:
                raise ValueError("target presentation exact identity is malformed")
            campaign_value, native_token = map(int, match.groups())
            if campaign_value > CAMPAIGN_ID_MAX or not 0 < native_token <= ENTITY_TOKEN_MAX:
                raise ValueError("target presentation exact identity is malformed")
            return campaign_value
        if isinstance(value["value"], bool) or not isinstance(value["value"], int) \
                or not 0 <= value["value"] <= CAMPAIGN_ID_MAX:
            raise ValueError("target presentation exact identity is malformed")
        return value["value"]
    elif value["value"] is not None or not isinstance(value["reason"], str) \
            or not value["reason"]:
        raise ValueError("target presentation non-exact identity is malformed")
    return None


def _validate_signature_evidence(
    rows: list[Any], *, expected: Mapping[tuple, str],
    key_fields: tuple[str, ...], roster: dict,
) -> None:
    """Require one exact, well-formed dependency signature per public result."""
    keys = []
    expected_fields = {*key_fields, "dependency_signature"}
    for item in rows:
        if not isinstance(item, dict) or set(item) != expected_fields:
            raise ValueError("target presentation dependency evidence is malformed")
        if any(not isinstance(item[field], str) for field in key_fields):
            raise ValueError("target presentation dependency evidence is malformed")
        key = tuple(item[field] for field in key_fields)
        signature = item["dependency_signature"]
        if item["brother_id"] not in roster or not isinstance(signature, str) \
                or SHA256_PATTERN.fullmatch(signature) is None:
            raise ValueError("target presentation dependency evidence is malformed")
        keys.append(key)
    if len(keys) != len(set(keys)) or set(keys) != set(expected):
        raise ValueError("target presentation dependency evidence is incomplete")
    if any(item["dependency_signature"] != expected[key]
           for item, key in zip(rows, keys, strict=True)):
        raise ValueError("target presentation dependency evidence is mismatched")


def _validate_recruitment_analysis(
    item: dict, *, background_save_hash: Any, build_definition_hash_value: str,
    recruit: Mapping[str, Any],
) -> None:
    state, reason, result = item["state"], item["reason"], item["result"]
    if state == "unavailable":
        if not isinstance(reason, str) or not reason or result is not None:
            raise ValueError("target presentation unavailable recruitment state is malformed")
        return
    if reason is not None or not isinstance(result, dict) or set(result) != {
        "schema", "model_version", "state", "background_prior",
        "candidate_estimate", "evidence_basis",
    } or result["schema"] != "bbtool.recruit_candidate_estimate.v1" \
            or result["model_version"] != 1 or result["state"] != state:
        raise ValueError("target presentation recruitment result is malformed")
    _validate_background_prior(
        result["background_prior"], background_save_hash=background_save_hash,
        build_identity_value=item["build_identity"],
        build_definition_hash_value=build_definition_hash_value,
    )
    evidence = result["evidence_basis"]
    if not isinstance(evidence, dict) or set(evidence) != {
        "public_fields_considered", "items", "excluded",
    } or evidence["public_fields_considered"] != PUBLIC_RECRUIT_FIELDS \
            or evidence["excluded"] != EXCLUDED_RECRUIT_FIELDS \
            or not isinstance(evidence["items"], list):
        raise ValueError("target presentation recruitment evidence is malformed")
    applied = _validate_recruitment_evidence_items(evidence["items"])
    revealed = recruit.get("RevealedTraitEvidence", ()) or () \
        if recruit.get("TryoutDone") is True else ()
    if not isinstance(revealed, (list, tuple)) or any(
        not isinstance(entry, Mapping) for entry in revealed
    ):
        raise ValueError("target presentation recruit evidence input is malformed")
    expected_evidence_identity = [
        (str(entry.get("save_hash", "")).upper() or None, entry.get("name"))
        for entry in revealed
    ]
    actual_evidence_identity = [
        (entry["save_hash"], entry["name"]) for entry in evidence["items"]
    ]
    if actual_evidence_identity != expected_evidence_identity:
        raise ValueError("target presentation recruitment evidence generation mismatch")
    estimate = result["candidate_estimate"]
    complete_evidence = bool(evidence["items"]) and all(
        entry["status"] == "applied_exact_unconditional_fit_effect"
        for entry in evidence["items"]
    )
    if state == "prior_only":
        if estimate is not None or complete_evidence:
            raise ValueError("target presentation prior-only recruitment result is malformed")
    elif not complete_evidence or not isinstance(estimate, dict) or set(estimate) != {
        "distribution", "applied_trait_save_hashes",
    } or estimate["applied_trait_save_hashes"] != applied or not applied:
        raise ValueError("target presentation known-evidence result is malformed")
    else:
        _validate_fit_distribution(estimate["distribution"])


def _validate_background_prior(
    value: Any, *, background_save_hash: Any, build_identity_value: Any,
    build_definition_hash_value: str,
) -> None:
    if not isinstance(value, dict) or set(value) != {
        "schema", "model_version", "background", "build", "engine_versions",
        "assumptions", "distribution",
    } or value["schema"] != "bbtool.background_archetype_prior.v1" \
            or value["model_version"] != 1 or value["assumptions"] != PRIOR_ASSUMPTIONS:
        raise ValueError("target presentation background prior is malformed")
    background = value["background"]
    if not isinstance(background, dict) or set(background) != {
        "save_hash", "background_id", "source_revision",
    } or background["save_hash"] != str(background_save_hash).upper() \
            or any(field is not None and not isinstance(field, str)
                   for field in (background["background_id"], background["source_revision"])):
        raise ValueError("target presentation background prior identity is malformed")
    build = value["build"]
    if build != {
        "id": build_identity_value, "definition_hash": build_definition_hash_value,
    } or not isinstance(build_identity_value, str):
        raise ValueError("target presentation background prior build is malformed")
    if value["engine_versions"] != {
        "role_projection": ENGINE_VERSIONS[ArtifactKind.ROLE_PROJECTION],
        "validation_oracle": ENGINE_VERSIONS[ArtifactKind.VALIDATION_ORACLE],
    }:
        raise ValueError("target presentation background prior engines are malformed")
    _validate_fit_distribution(value["distribution"])


def _validate_fit_distribution(value: Any) -> None:
    if not isinstance(value, dict) or set(value) != {
        "talent_weight_denominator", "trajectory_sample_denominator",
        "weight_denominator", "unique_talent_profiles", "fit_histogram_weight",
        "mean_fit_pct",
    }:
        raise ValueError("target presentation recruitment distribution is malformed")
    integer_fields = (
        "talent_weight_denominator", "trajectory_sample_denominator",
        "weight_denominator", "unique_talent_profiles",
    )
    if any(isinstance(value[field], bool) or not isinstance(value[field], int)
           or value[field] <= 0 for field in integer_fields):
        raise ValueError("target presentation recruitment distribution is malformed")
    if value["weight_denominator"] != (
        value["talent_weight_denominator"] * value["trajectory_sample_denominator"]
    ):
        raise ValueError("target presentation recruitment distribution is incoherent")
    histogram = value["fit_histogram_weight"]
    bins = {f"{lower:02d}-{lower + 9:02d}" for lower in range(0, 90, 10)} | {"90-100"}
    if not isinstance(histogram, dict) or not histogram or not set(histogram).issubset(bins) \
            or any(isinstance(weight, bool) or not isinstance(weight, int) or weight <= 0
                   for weight in histogram.values()) \
            or sum(histogram.values()) != value["weight_denominator"] \
            or isinstance(value["mean_fit_pct"], bool) \
            or not isinstance(value["mean_fit_pct"], (int, float)) \
            or not 0 <= value["mean_fit_pct"] <= 100:
        raise ValueError("target presentation recruitment distribution is malformed")


def _validate_recruitment_evidence_items(items: list[Any]) -> list[str]:
    applied = []
    for evidence in items:
        if not isinstance(evidence, dict) or set(evidence) != {
            "kind", "save_hash", "name", "status", "effects",
        } or evidence["kind"] != "revealed_trait" \
                or evidence["status"] not in {
                    "applied_exact_unconditional_fit_effect", "insufficient_for_estimate",
                } or not isinstance(evidence["effects"], list):
            raise ValueError("target presentation recruitment evidence item is malformed")
        save_hash = evidence["save_hash"]
        if save_hash is not None and (
            not isinstance(save_hash, str) or re.fullmatch(r"[0-9A-F]{8}", save_hash) is None
        ):
            raise ValueError("target presentation recruitment evidence item is malformed")
        if evidence["name"] is not None and not isinstance(evidence["name"], str):
            raise ValueError("target presentation recruitment evidence item is malformed")
        for effect in evidence["effects"]:
            if not isinstance(effect, dict) or set(effect) != {"stat", "property", "op", "value"}:
                raise ValueError("target presentation recruitment effect is malformed")
        if evidence["status"] == "applied_exact_unconditional_fit_effect":
            if save_hash is None or not evidence["effects"]:
                raise ValueError("target presentation recruitment evidence item is malformed")
            applied.append(save_hash)
        elif evidence["effects"]:
            raise ValueError("target presentation recruitment evidence item is malformed")
    return sorted(set(applied))
