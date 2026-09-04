"""Versioned Target UI presentation metadata and coherence validation."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict
from typing import Any

from ..build_identity import build_definition_hash, build_identity
from ..incremental.dependencies import stable_hash
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
    bound = {key: artifact_hashes[key] for key in sorted(BOUND_ARTIFACTS)}
    provenance = {
        "source_fingerprint": source_fingerprint,
        "configuration_fingerprints": dict(sorted(configuration_fingerprints.items())),
        "artifact_hashes": bound,
    }
    return {
        "schema": SCHEMA,
        "publication": {
            "coherence_signature": stable_hash(provenance),
            "provenance": provenance,
        },
        "campaign_identity": _identity_payload(campaign_identity),
        "brothers": [{
            "brother_id": bro.BrotherID,
            "brother_identity": _identity_payload(identities.get(bro.BrotherID)),
            "mechanical_facts": list(
                getattr(bro, "PerkGearFacts", None) or perk_gear_facts(bro)
            ),
        } for bro in bros],
        "builds": builds,
        "run_health": analysis_health,
        "recruitment": recruitment_analysis,
        "validity": {
            "basis": "result_local_dependency_signature",
            "artifacts": dict(result_signatures),
        },
        "company": {
            "intrinsic_coverage": company_intrinsic_coverage,
        },
        "pending": {
            "assigned_build": 107,
            "intent_aware_advisor": 108,
            "intended_company_planning": 128,
            "relevant_roster_need": 112,
        },
    }


def validate_target_presentation(
    payload: Any, *, payloads: Mapping[str, Any], artifact_hashes: Mapping[str, str],
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
    }:
        raise ValueError("target presentation provenance fields mismatch")
    if provenance["artifact_hashes"] != {
        key: artifact_hashes[key] for key in sorted(BOUND_ARTIFACTS)
    }:
        raise ValueError("target presentation artifact generation mismatch")
    if publication["coherence_signature"] != stable_hash(provenance):
        raise ValueError("target presentation coherence signature mismatch")
    if not isinstance(provenance["source_fingerprint"], str) or not \
            provenance["source_fingerprint"].startswith("sha256:"):
        raise ValueError("target presentation source fingerprint is malformed")
    config = provenance["configuration_fingerprints"]
    if not isinstance(config, dict) or set(config) != {"archetypes", "classification"} \
            or any(not isinstance(value, str) or not value.startswith("sha256:")
                   for value in config.values()):
        raise ValueError("target presentation configuration fingerprints are malformed")
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
    if not isinstance(brothers, list) or {row.get("brother_id") for row in brothers} != set(roster):
        raise ValueError("target presentation brother joins do not match roster")
    for row in brothers:
        if not isinstance(row, dict) or set(row) != {
            "brother_id", "brother_identity", "mechanical_facts",
        } or row["mechanical_facts"] != roster[row["brother_id"]].get("PerkGearFacts", []):
            raise ValueError("target presentation mechanical facts mismatch")
        _validate_identity(row["brother_identity"], brother=True)
    _validate_identity(payload["campaign_identity"], brother=False)
    if not isinstance(payload["recruitment"], list):
        raise ValueError("target presentation recruitment must be an array")
    if [row.get("recruit_index") for row in payload["recruitment"]] != \
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
        if {item.get("build_identity") for item in row["analyses"]} != \
                {item["build_identity"] for item in builds}:
            raise ValueError("target presentation recruitment build joins mismatch")
        for item in row["analyses"]:
            if not isinstance(item, dict) or set(item) != {
                "build_identity", "state", "reason", "result",
            } or item["state"] not in {
                "prior_only", "known_evidence_estimate", "unavailable",
            }:
                raise ValueError("target presentation recruitment analysis is malformed")
    validity = payload["validity"]
    if not isinstance(validity, dict) or set(validity) != {"basis", "artifacts"} \
            or validity["basis"] != "result_local_dependency_signature":
        raise ValueError("target presentation validity fields mismatch")
    artifacts = validity["artifacts"]
    if not isinstance(artifacts, dict) or set(artifacts) != {
        "role_projection", "strategic_classification", "level_advisor",
    } or any(not isinstance(rows, list) for rows in artifacts.values()):
        raise ValueError("target presentation validity artifacts are malformed")
    for rows in artifacts.values():
        for item in rows:
            if not isinstance(item, dict) or item.get("brother_id") not in roster \
                    or not isinstance(item.get("dependency_signature"), str) \
                    or not item["dependency_signature"].startswith("sha256:"):
                raise ValueError("target presentation dependency signature is malformed")
    company = payload["company"]
    if not isinstance(company, dict) or set(company) != {"intrinsic_coverage"} \
            or not isinstance(company["intrinsic_coverage"], list):
        raise ValueError("target presentation company fields mismatch")
    company_builds = {row.get("BuildIdentity") for row in company["intrinsic_coverage"]}
    if None in company_builds or not company_builds.issubset(build_ids):
        raise ValueError("target presentation company build joins mismatch")
    if any(not isinstance(row.get("ArtifactSignature"), str)
           or not row["ArtifactSignature"].startswith("sha256:")
           for row in company["intrinsic_coverage"]):
        raise ValueError("target presentation company validity is malformed")
    if payload["pending"] != {
        "assigned_build": 107, "intent_aware_advisor": 108,
        "intended_company_planning": 128, "relevant_roster_need": 112,
    }:
        raise ValueError("target presentation pending fields mismatch")


def _validate_identity(value: Any, *, brother: bool) -> None:
    if not isinstance(value, dict) or set(value) != {
        "value", "basis", "confidence", "reason",
    } or value["confidence"] not in {"exact", "unavailable", "invalid"}:
        raise ValueError("target presentation identity is malformed")
    if value["confidence"] == "exact":
        expected = "native_campaign_entity_token" if brother else "native_campaign_id"
        if value["basis"] != expected or value["value"] is None:
            raise ValueError("target presentation exact identity is malformed")
    elif value["value"] is not None:
        raise ValueError("target presentation non-exact identity exposes a value")
