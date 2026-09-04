from __future__ import annotations
from collections import Counter
from dataclasses import dataclass

from ..build_identity import build_identity, build_result_key
from .manifest import SCHEMA, campaign_identity_payload
from .dependencies import stable_hash

from .fingerprint import (
    ADVISOR_ENGINE_VERSION,
    BROTHER_SUMMARY_ENGINE_VERSION,
    ROLE_PROJECTION_ENGINE_VERSION,
    VALIDATION_ORACLE_ENGINE_VERSION,
    advisor_fingerprint,
    brother_projection_fingerprint,
    brother_summary_fingerprint,
    role_fingerprint,
    validation_oracle_fingerprint,
)


@dataclass
class IncrementalStats:
    previous_found: bool = False
    role_reused: int = 0
    role_computed: int = 0
    ambiguous_states: int = 0
    summary_reused: int = 0
    summary_computed: int = 0
    advisor_reused: int = 0
    advisor_computed: int = 0
    previous_manifest: str | None = None


class IncrementalCache:
    def __init__(self, previous=None, *, enabled=True, previous_path=None):
        self.enabled = bool(enabled)
        self.previous = previous if isinstance(previous, dict) else None
        self.stats = IncrementalStats(
            previous_found=bool(self.previous) and self.enabled,
            previous_manifest=str(previous_path) if previous_path else None,
        )
        self.miss_reasons = Counter()
        self._previous_by_state = {}
        self._current = {}
        if self.previous and self.enabled:
            for entry in (self.previous.get("brothers") or {}).values():
                state = entry.get("projection_state_hash")
                if state:
                    self._previous_by_state.setdefault(state, []).append(entry)

    def _entry_for_bro(self, bro):
        if not self.enabled:
            self.miss_reasons["cache_disabled"] += 1
            return None
        if not self.previous:
            self.miss_reasons["no_previous_manifest"] += 1
            return None
        state = brother_projection_fingerprint(bro)
        matches = self._previous_by_state.get(state, [])
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            self.stats.ambiguous_states += 1
            self.miss_reasons["ambiguous_brother_state"] += 1
        else:
            self.miss_reasons["brother_state_changed_or_new"] += 1
        return None

    def _current_entry(self, bro):
        state = brother_projection_fingerprint(bro)
        storage_key = str(getattr(bro, "BrotherID", state))
        return self._current.setdefault(
            storage_key,
            {
                "projection_state_hash": state,
                "display_name": str(getattr(bro, "Name", "")),
                "roles": {},
            },
        )

    @staticmethod
    def _role_storage_key(role):
        return build_result_key(role)

    def get_role_row(self, bro, role):
        entry = self._entry_for_bro(bro)
        if entry is None:
            return None
        prior = (entry.get("roles") or {}).get(self._role_storage_key(role))
        if not prior:
            self.miss_reasons["role_artifact_missing"] += 1
            return None
        if prior.get("engine_version") != ROLE_PROJECTION_ENGINE_VERSION:
            self.miss_reasons["role_engine_changed"] += 1
            return None
        if prior.get("role_hash") != role_fingerprint(role):
            self.miss_reasons["archetype_changed"] += 1
            return None
        result = prior.get("result")
        if not isinstance(result, dict):
            self.miss_reasons["role_artifact_invalid"] += 1
            return None
        self.stats.role_reused += 1
        self._current_entry(bro)["roles"][self._role_storage_key(role)] = dict(prior)
        row = dict(result)
        row["BrotherID"] = bro.BrotherID
        row["Name"] = bro.Name
        row["Level"] = bro.Level
        row["Background"] = bro.Background
        row["Role"] = role["name"]
        return row

    def store_role_row(self, bro, role, row, validation_oracle=None):
        entry = self._current_entry(bro)
        role_key = self._role_storage_key(role)
        existing = (entry.get("roles") or {}).get(role_key)
        artifact = {
            "role_hash": role_fingerprint(role),
            "engine_version": ROLE_PROJECTION_ENGINE_VERSION,
            "result": dict(row),
        }
        if isinstance(validation_oracle, dict):
            artifact["validation_oracle"] = dict(validation_oracle)
            artifact["validation_oracle"]["engine_version"] = VALIDATION_ORACLE_ENGINE_VERSION
            artifact["validation_oracle"]["input_hash"] = validation_oracle_fingerprint(bro, role)
        elif isinstance(existing, dict) and "validation_oracle" in existing:
            artifact["validation_oracle"] = existing["validation_oracle"]
        entry["roles"][role_key] = artifact

    def get_validation_oracle(self, bro, role):
        entry = self._current_entry(bro)
        artifact = (entry.get("roles") or {}).get(self._role_storage_key(role))
        oracle = artifact.get("validation_oracle") if isinstance(artifact, dict) else None
        if not isinstance(oracle, dict):
            self.miss_reasons["validation_oracle_missing"] += 1
            return None
        if oracle.get("engine_version") != VALIDATION_ORACLE_ENGINE_VERSION:
            self.miss_reasons["validation_oracle_engine_changed"] += 1
            return None
        if oracle.get("input_hash") != validation_oracle_fingerprint(bro, role):
            self.miss_reasons["validation_oracle_inputs_changed"] += 1
            return None
        outcomes = oracle.get("outcomes_pct")
        sample_count = oracle.get("sample_count")
        if (
            not isinstance(outcomes, list)
            or not isinstance(sample_count, int)
            or isinstance(sample_count, bool)
            or sample_count <= 0
            or len(outcomes) != sample_count
            or any(
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not 0 <= value <= 100
                for value in outcomes
            )
        ):
            self.miss_reasons["validation_oracle_corrupt"] += 1
            return None
        return {"_outcomes_pct": tuple(float(value) for value in outcomes)}

    def store_validation_oracle(self, bro, role, trajectory):
        outcomes = list(trajectory.get("_outcomes_pct", ()))
        entry = self._current_entry(bro)
        artifact = (entry.get("roles") or {}).get(self._role_storage_key(role))
        if not isinstance(artifact, dict) or not outcomes:
            return
        artifact["validation_oracle"] = {
            "engine_version": VALIDATION_ORACLE_ENGINE_VERSION,
            "input_hash": validation_oracle_fingerprint(bro, role),
            "outcomes_pct": outcomes,
            "sample_count": len(outcomes),
        }

    def mark_computed(self):
        self.stats.role_computed += 1

    def get_advisor(self, bro, roles, assigned_build=None):
        entry = self._entry_for_bro(bro)
        if entry is None:
            return None
        prior = entry.get("advisor")
        if not isinstance(prior, dict):
            self.miss_reasons["advisor_artifact_missing"] += 1
            return None
        if prior.get("engine_version") != ADVISOR_ENGINE_VERSION:
            self.miss_reasons["advisor_engine_changed"] += 1
            return None
        if prior.get("input_hash") != advisor_fingerprint(bro, roles, assigned_build):
            self.miss_reasons["advisor_inputs_changed"] += 1
            return None
        result = prior.get("result")
        old_labels = prior.get("role_labels")
        if not isinstance(old_labels, list) or any(
            not isinstance(item, dict)
            or set(item) != {"identity", "signature", "name"}
            or item["identity"] is not None and not isinstance(item["identity"], str)
            or not isinstance(item["signature"], str)
            or not isinstance(item["name"], str)
            for item in old_labels
        ):
            self.miss_reasons["advisor_artifact_invalid"] += 1
            return None
        current_labels = [{
            "identity": build_identity(role),
            "signature": role_fingerprint(role),
            "name": role["name"],
        } for role in roles]
        rename = {}
        for old in old_labels:
            matches = [current for current in current_labels if (
                old["identity"] is not None
                and current["identity"] == old["identity"]
                and current["signature"] == old["signature"]
            )]
            if not matches and old["identity"] is not None:
                matches = [current for current in current_labels if (
                    current["signature"] == old["signature"]
                )]
            if old["identity"] is None:
                matches = [current for current in current_labels if (
                    current["identity"] is None
                    and current["name"] == old["name"]
                    and current["signature"] == old["signature"]
                )]
            if len(matches) != 1:
                self.miss_reasons["advisor_role_association_ambiguous"] += 1
                return None
            rename[old["name"]] = matches[0]["name"]

        def refresh(value):
            if isinstance(value, dict):
                return {
                    key: rename.get(item, item)
                    if key in {"AnchorRole", "Role", "RoleBefore", "RoleAfter"}
                    else refresh(item)
                    for key, item in value.items()
                }
            if isinstance(value, list):
                return [refresh(item) for item in value]
            return value

        refreshed = refresh(result)
        self.stats.advisor_reused += 1
        self._current_entry(bro)["advisor"] = dict(prior)
        return refreshed

    def store_advisor(self, bro, roles, result, assigned_build=None):
        entry = self._current_entry(bro)
        entry["advisor"] = {
            "input_hash": advisor_fingerprint(bro, roles, assigned_build),
            "engine_version": ADVISOR_ENGINE_VERSION,
            "role_labels": [{
                "identity": build_identity(role),
                "signature": role_fingerprint(role),
                "name": role["name"],
            } for role in roles],
            "result": result,
        }

    def mark_advisor_computed(self):
        self.stats.advisor_computed += 1

    def get_summary(self, bro, roles, classification_cfg):
        entry = self._entry_for_bro(bro)
        if entry is None:
            return None
        prior = entry.get("summary")
        if not isinstance(prior, dict):
            self.miss_reasons["summary_artifact_missing"] += 1
            return None
        if prior.get("engine_version") != BROTHER_SUMMARY_ENGINE_VERSION:
            self.miss_reasons["summary_engine_changed"] += 1
            return None
        if prior.get("input_hash") != brother_summary_fingerprint(
            bro, roles, classification_cfg
        ):
            self.miss_reasons["classification_or_summary_inputs_changed"] += 1
            return None
        result = prior.get("result")
        if not isinstance(result, dict):
            self.miss_reasons["summary_artifact_invalid"] += 1
            return None
        self.stats.summary_reused += 1
        current = self._current_entry(bro)
        current["summary"] = dict(prior)
        # A valid summary implies the same brother-state and role inputs as its
        # advisor dependency. Carry it forward so the newest
        # manifest remains a complete cache source.
        artifact = entry.get("advisor")
        if isinstance(artifact, dict):
            current["advisor"] = dict(artifact)
        summary = dict(result)
        summary["BrotherID"] = bro.BrotherID
        summary["Name"] = bro.Name
        summary["Level"] = bro.Level
        summary["Background"] = bro.Background
        # These fields are current-save display data, not long-term projection
        # inputs.  In particular, temporary injuries deliberately do not enter
        # the projection fingerprint, so never carry their old display value
        # forward from a reusable analytical summary.
        summary["Perks"] = "; ".join(getattr(bro, "Perks", []) or [])
        summary["Traits"] = "; ".join(getattr(bro, "Traits", []) or [])
        summary["Injuries"] = "; ".join(getattr(bro, "Injuries", []) or [])
        # Advisor has an independent validity domain. Old manifests may have
        # embedded it in summary; never publish that unvalidated copy.
        summary.pop("LevelUpAdvice", None)
        return summary

    def store_summary(self, bro, roles, classification_cfg, summary):
        entry = self._current_entry(bro)
        intrinsic_summary = dict(summary)
        intrinsic_summary.pop("LevelUpAdvice", None)
        entry["summary"] = {
            "input_hash": brother_summary_fingerprint(
                bro, roles, classification_cfg
            ),
            "engine_version": BROTHER_SUMMARY_ENGINE_VERSION,
            "result": intrinsic_summary,
        }

    def mark_summary_computed(self):
        self.stats.summary_computed += 1

    def manifest_payload(
        self, *, generated_at, source_save, campaign_identity=None,
        source_save_path=None
    ):
        return {
            "schema": SCHEMA,
            "generated_at": generated_at,
            "source_save": source_save,
            "source_save_path": source_save_path,
            "campaign_identity": campaign_identity_payload(campaign_identity),
            "engine": {
                "role_projection": ROLE_PROJECTION_ENGINE_VERSION,
                "advisor": ADVISOR_ENGINE_VERSION,
                "summary": BROTHER_SUMMARY_ENGINE_VERSION,
                "validation_oracle": VALIDATION_ORACLE_ENGINE_VERSION,
            },
            "brothers": self._current,
            "stats": {
                "previous_found": self.stats.previous_found,
                "role_reused": self.stats.role_reused,
                "role_computed": self.stats.role_computed,
                "advisor_reused": self.stats.advisor_reused,
                "advisor_computed": self.stats.advisor_computed,
                "summary_reused": self.stats.summary_reused,
                "summary_computed": self.stats.summary_computed,
                "ambiguous_states": self.stats.ambiguous_states,
                "previous_manifest": self.stats.previous_manifest,
                "miss_reasons": dict(self.miss_reasons),
            },
        }

    def publication_signatures(self) -> dict:
        """Expose result-local input signatures without cached result payloads."""
        role_rows = []
        classifications = []
        advisors = []
        for brother_id, entry in sorted(self._current.items()):
            state = entry["projection_state_hash"]
            for build_key, artifact in sorted(entry.get("roles", {}).items()):
                role_rows.append({
                    "brother_id": brother_id,
                    "build_key": build_key,
                    "dependency_signature": stable_hash({
                        "artifact": "role_projection",
                        "brother_state": state,
                        "build_definition": artifact.get("role_hash"),
                        "engine_version": artifact.get("engine_version"),
                    }),
                })
            summary = entry.get("summary")
            if isinstance(summary, dict):
                classifications.append({
                    "brother_id": brother_id,
                    "dependency_signature": summary.get("input_hash"),
                })
            advisor = entry.get("advisor")
            if isinstance(advisor, dict):
                advisors.append({
                    "brother_id": brother_id,
                    "dependency_signature": advisor.get("input_hash"),
                })
        return {
            "role_projection": role_rows,
            "strategic_classification": classifications,
            "level_advisor": advisors,
        }
