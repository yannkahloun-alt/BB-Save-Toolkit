"""Artifact dependency/currentness signatures for local-app publication."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..incremental.dependencies import InputKind, input_signature
from ..incremental.fingerprint import role_signature_list
from ..models import CampaignIdentity
from ..save_parser import parse_campaign_identity_bytes


DEPENDENCY_SIGNATURES_SCHEMA = "bbtool.analysis_dependency_signatures.v1"
_ASSIGNMENT_FIELDS = (
    "status",
    "build_identity",
    "assigned_definition_hash",
    "current_definition_hash",
)


def _campaign_value(content: bytes) -> int | None:
    campaign = parse_campaign_identity_bytes(content)
    if (
        campaign.confidence == "exact"
        and not isinstance(campaign.value, bool)
        and isinstance(campaign.value, int)
    ):
        return campaign.value
    return None


def _assignment_evidence(assignments: Mapping[str, Any] | None) -> Any:
    if assignments is None:
        return None
    evidence = {}
    for brother_identity, assignment in sorted(assignments.items()):
        if not isinstance(assignment, Mapping):
            raise ValueError("AssignedBuild dependency evidence must be mappings")
        evidence[str(brother_identity)] = {
            field: assignment.get(field) for field in _ASSIGNMENT_FIELDS
        }
    return evidence


def _input_signatures(roles, classification, assignments) -> dict[str, str]:
    return {
        InputKind.BUILD_DEFINITION.value: input_signature(
            InputKind.BUILD_DEFINITION, role_signature_list(roles)
        ),
        InputKind.CLASSIFICATION_CONFIG.value: input_signature(
            InputKind.CLASSIFICATION_CONFIG, classification
        ),
        InputKind.ASSIGNED_BUILD.value: input_signature(
            InputKind.ASSIGNED_BUILD, _assignment_evidence(assignments)
        ),
    }


def build_desired_dependency_signatures(
    content: bytes, roles, classification, assigned_builds
) -> dict[str, Any]:
    """Snapshot mutable semantic inputs that can outlive the worker request."""
    campaign_value = _campaign_value(content)
    assignments = None
    if campaign_value is not None:
        assignments = assigned_builds.read_campaign(
            CampaignIdentity(campaign_value, confidence="exact")
        )["assignments"]
    return {
        "schema": DEPENDENCY_SIGNATURES_SCHEMA,
        "scope": {"campaign_identity": campaign_value},
        "inputs": _input_signatures(roles, classification, assignments),
    }


def dependency_signatures_are_current(
    snapshot: Mapping[str, Any], *, catalog, classification, assigned_builds
) -> bool:
    """Recompute the scoped semantic snapshot; malformed/missing evidence fails closed."""
    if not isinstance(snapshot, Mapping) or set(snapshot) != {"schema", "scope", "inputs"}:
        return False
    if snapshot.get("schema") != DEPENDENCY_SIGNATURES_SCHEMA:
        return False
    scope = snapshot.get("scope")
    inputs = snapshot.get("inputs")
    if not isinstance(scope, Mapping) or set(scope) != {"campaign_identity"}:
        return False
    if not isinstance(inputs, Mapping) or set(inputs) != {
        InputKind.BUILD_DEFINITION.value,
        InputKind.CLASSIFICATION_CONFIG.value,
        InputKind.ASSIGNED_BUILD.value,
    }:
        return False
    campaign_value = scope.get("campaign_identity")
    if campaign_value is not None and (
        isinstance(campaign_value, bool) or not isinstance(campaign_value, int)
    ):
        return False
    config = catalog.analyzer_config(classification)
    assignments = None
    if campaign_value is not None:
        assignments = assigned_builds.read_campaign(
            CampaignIdentity(campaign_value, confidence="exact")
        )["assignments"]
    expected = _input_signatures(config.roles, config.classification, assignments)
    return dict(inputs) == expected


__all__ = [
    "DEPENDENCY_SIGNATURES_SCHEMA",
    "build_desired_dependency_signatures",
    "dependency_signatures_are_current",
]
