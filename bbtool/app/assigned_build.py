"""Authoritative campaign-scoped AssignedBuild intent."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from ..build_identity import validate_build_identity
from ..models import BrotherIdentity, CampaignIdentity
from .archetype_catalog import ArchetypeCatalogStore, EffectiveCatalog
from .user_state import (
    AssignedBuildCampaign,
    AssignedBuildRecord,
    AssignedBuildState,
    UserStateStore,
)


class AssignedBuildValidationError(ValueError):
    """Identity or catalog evidence cannot authorize the requested operation."""


@dataclass(frozen=True)
class ResolvedAssignedBuild:
    status: str
    build_identity: str | None = None
    assigned_definition_hash: str | None = None
    current_definition_hash: str | None = None
    display_name: str | None = None

    def payload(self) -> dict[str, Any]:
        return asdict(self)


def _exact_identity(
    campaign: CampaignIdentity, brother: BrotherIdentity
) -> tuple[int, str]:
    if (
        campaign.confidence != "exact"
        or isinstance(campaign.value, bool)
        or not isinstance(campaign.value, int)
    ):
        raise AssignedBuildValidationError("CampaignIdentity must be exact")
    if not 0 <= campaign.value <= 2_147_483_647:
        raise AssignedBuildValidationError("CampaignIdentity value is invalid")
    if (
        brother.confidence != "exact"
        or brother.campaign_value is None
        or brother.native_token is None
        or brother.value is None
    ):
        raise AssignedBuildValidationError("BrotherIdentity must be exact")
    if brother.campaign_value != campaign.value:
        raise AssignedBuildValidationError(
            "BrotherIdentity is outside the requested campaign namespace"
        )
    if not 1 <= brother.native_token <= 0xFFFFFFFF:
        raise AssignedBuildValidationError("BrotherIdentity native token is invalid")
    return campaign.value, brother.value


class AssignedBuildStore:
    """Bounded domain operations over the shared durable-state substrate."""

    def __init__(self, store: UserStateStore, catalog: ArchetypeCatalogStore) -> None:
        self.store = store
        self.catalog = catalog

    @staticmethod
    def _record(
        state: AssignedBuildState, campaign_value: int, brother_value: str
    ) -> AssignedBuildRecord | None:
        for campaign in state.campaigns:
            if campaign.campaign_identity == campaign_value:
                return next(
                    (item for item in campaign.assignments if item.brother_identity == brother_value),
                    None,
                )
        return None

    @staticmethod
    def _resolve(
        record: AssignedBuildRecord | None, catalog: EffectiveCatalog
    ) -> ResolvedAssignedBuild:
        if record is None:
            return ResolvedAssignedBuild("unassigned")
        role = next(
            (role for role in catalog.roles if role["id"] == record.build_identity), None
        )
        if role is not None:
            current_hash = catalog.definition_hashes[record.build_identity]
            return ResolvedAssignedBuild(
                "current" if current_hash == record.assigned_definition_hash else "definition_changed",
                record.build_identity,
                record.assigned_definition_hash,
                current_hash,
                role["name"],
            )
        retired = {
            entry.get("id")
            for entry in catalog.state.entries
            if entry.get("kind") == "retired"
        }
        return ResolvedAssignedBuild(
            "deprecated" if record.build_identity in retired else "missing",
            record.build_identity,
            record.assigned_definition_hash,
        )

    def read(
        self, campaign: CampaignIdentity, brother: BrotherIdentity
    ) -> dict[str, Any]:
        campaign_value, brother_value = _exact_identity(campaign, brother)
        state = self.store.load("assigned_builds")
        resolved = self._resolve(
            self._record(state, campaign_value, brother_value), self.catalog.load()
        )
        return {"revision": state.revision, "assignment": resolved.payload()}

    def assign(
        self,
        campaign: CampaignIdentity,
        brother: BrotherIdentity,
        build_identity: str,
        *,
        expected_revision: int,
    ) -> dict[str, Any]:
        campaign_value, brother_value = _exact_identity(campaign, brother)
        build_identity = validate_build_identity(build_identity)
        catalog = self.catalog.load()
        role = next((role for role in catalog.roles if role["id"] == build_identity), None)
        if role is None:
            raise AssignedBuildValidationError(
                f"BuildIdentity {build_identity!r} is not in the current effective catalog"
            )
        current_hash = catalog.definition_hashes[build_identity]
        current = self.store.load("assigned_builds")
        old_record = self._record(current, campaign_value, brother_value)
        replacement = AssignedBuildRecord(brother_value, build_identity, current_hash)
        campaigns = []
        found_campaign = False
        for item in current.campaigns:
            if item.campaign_identity != campaign_value:
                campaigns.append(item)
                continue
            found_campaign = True
            assignments = [
                existing for existing in item.assignments
                if existing.brother_identity != brother_value
            ] + [replacement]
            campaigns.append(AssignedBuildCampaign(campaign_value, tuple(assignments)))
        if not found_campaign:
            campaigns.append(AssignedBuildCampaign(campaign_value, (replacement,)))
        saved = self.store.save(
            "assigned_builds",
            AssignedBuildState(campaigns=tuple(campaigns)),
            expected_revision=expected_revision,
        )
        return self._mutation_result(
            campaign_value, brother_value, old_record, replacement, saved, catalog
        )

    change = assign
    acknowledge = assign

    def clear(
        self,
        campaign: CampaignIdentity,
        brother: BrotherIdentity,
        *,
        expected_revision: int,
    ) -> dict[str, Any]:
        campaign_value, brother_value = _exact_identity(campaign, brother)
        current = self.store.load("assigned_builds")
        old_record = self._record(current, campaign_value, brother_value)
        catalog = self.catalog.load()
        if old_record is None:
            current = self.store.assert_revision(
                "assigned_builds", expected_revision=expected_revision
            )
            return {
                "revision": current.revision,
                "assignment": ResolvedAssignedBuild("unassigned").payload(),
                "change": None,
            }
        campaigns = []
        for item in current.campaigns:
            if item.campaign_identity != campaign_value:
                campaigns.append(item)
                continue
            assignments = tuple(
                existing for existing in item.assignments
                if existing.brother_identity != brother_value
            )
            if assignments:
                campaigns.append(AssignedBuildCampaign(campaign_value, assignments))
        saved = self.store.save(
            "assigned_builds", AssignedBuildState(campaigns=tuple(campaigns)),
            expected_revision=expected_revision,
        )
        return self._mutation_result(
            campaign_value, brother_value, old_record, None, saved, catalog
        )

    def clear_campaign(
        self, campaign: CampaignIdentity, *, expected_revision: int
    ) -> dict[str, Any]:
        if (
            campaign.confidence != "exact"
            or isinstance(campaign.value, bool)
            or not isinstance(campaign.value, int)
            or not 0 <= campaign.value <= 2_147_483_647
        ):
            raise AssignedBuildValidationError("CampaignIdentity must be exact")
        current = self.store.load("assigned_builds")
        target = next(
            (item for item in current.campaigns if item.campaign_identity == campaign.value), None
        )
        if target is None or not target.assignments:
            current = self.store.assert_revision(
                "assigned_builds", expected_revision=expected_revision
            )
            return {"revision": current.revision, "changes": []}
        saved = self.store.save(
            "assigned_builds",
            AssignedBuildState(campaigns=tuple(
                item for item in current.campaigns
                if item.campaign_identity != campaign.value
            )),
            expected_revision=expected_revision,
        )
        catalog = self.catalog.load()
        changes = [
            self._change(campaign.value, record.brother_identity, record, None, saved.revision, catalog)
            for record in target.assignments
        ]
        return {"revision": saved.revision, "changes": changes}

    def _mutation_result(
        self, campaign_value: int, brother_value: str,
        old: AssignedBuildRecord | None, new: AssignedBuildRecord | None,
        saved: AssignedBuildState, catalog: EffectiveCatalog,
    ) -> dict[str, Any]:
        return {
            "revision": saved.revision,
            "assignment": self._resolve(new, catalog).payload(),
            "change": self._change(
                campaign_value, brother_value, old, new, saved.revision, catalog
            ),
        }

    def _change(
        self, campaign_value: int, brother_value: str,
        old: AssignedBuildRecord | None, new: AssignedBuildRecord | None,
        revision: int, catalog: EffectiveCatalog,
    ) -> dict[str, Any]:
        return {
            "input_kind": "assigned_build",
            "campaign_identity": campaign_value,
            "brother_identity": brother_value,
            "old": self._resolve(old, catalog).payload(),
            "new": self._resolve(new, catalog).payload(),
            "authoritative_revision": revision,
        }


__all__ = [
    "AssignedBuildStore", "AssignedBuildValidationError", "ResolvedAssignedBuild",
]
