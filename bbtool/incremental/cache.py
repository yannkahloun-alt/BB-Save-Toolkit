from __future__ import annotations
from collections import Counter
from dataclasses import dataclass

from .fingerprint import (
    ADVISOR_ENGINE_VERSION,
    BROTHER_SUMMARY_ENGINE_VERSION,
    ROLE_PROJECTION_ENGINE_VERSION,
    STRUCTURAL_PATH_ENGINE_VERSION,
    advisor_fingerprint,
    brother_projection_fingerprint,
    brother_summary_fingerprint,
    role_fingerprint,
    structural_path_fingerprint,
)


@dataclass
class IncrementalStats:
    previous_found: bool = False
    role_reused: int = 0
    role_computed: int = 0
    ambiguous_states: int = 0
    summary_reused: int = 0
    summary_computed: int = 0
    structural_reused: int = 0
    structural_computed: int = 0
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

    def get_role_row(self, bro, role):
        entry = self._entry_for_bro(bro)
        if entry is None:
            return None
        prior = (entry.get("roles") or {}).get(role["name"])
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
        row = dict(result)
        row["BrotherID"] = bro.BrotherID
        row["Name"] = bro.Name
        row["Level"] = bro.Level
        row["Background"] = bro.Background
        return row

    def store_role_row(self, bro, role, row):
        entry = self._current_entry(bro)
        entry["roles"][role["name"]] = {
            "role_hash": role_fingerprint(role),
            "engine_version": ROLE_PROJECTION_ENGINE_VERSION,
            "result": dict(row),
        }

    def mark_computed(self):
        self.stats.role_computed += 1

    def get_structural_paths(self, bro, roles):
        entry = self._entry_for_bro(bro)
        if entry is None:
            return None
        prior = entry.get("structural_paths")
        if not isinstance(prior, dict):
            self.miss_reasons["structural_artifact_missing"] += 1
            return None
        if prior.get("engine_version") != STRUCTURAL_PATH_ENGINE_VERSION:
            self.miss_reasons["structural_engine_changed"] += 1
            return None
        if prior.get("input_hash") != structural_path_fingerprint(bro, roles):
            self.miss_reasons["structural_inputs_changed"] += 1
            return None
        result = prior.get("result")
        if not isinstance(result, list):
            self.miss_reasons["structural_artifact_invalid"] += 1
            return None
        self.stats.structural_reused += 1
        self._current_entry(bro)["structural_paths"] = dict(prior)
        return list(result)

    def store_structural_paths(self, bro, roles, result):
        entry = self._current_entry(bro)
        entry["structural_paths"] = {
            "input_hash": structural_path_fingerprint(bro, roles),
            "engine_version": STRUCTURAL_PATH_ENGINE_VERSION,
            "result": list(result),
        }

    def mark_structural_computed(self):
        self.stats.structural_computed += 1

    def get_advisor(self, bro, roles):
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
        if prior.get("input_hash") != advisor_fingerprint(bro, roles):
            self.miss_reasons["advisor_inputs_changed"] += 1
            return None
        self.stats.advisor_reused += 1
        self._current_entry(bro)["advisor"] = dict(prior)
        return prior.get("result")

    def store_advisor(self, bro, roles, result):
        entry = self._current_entry(bro)
        entry["advisor"] = {
            "input_hash": advisor_fingerprint(bro, roles),
            "engine_version": ADVISOR_ENGINE_VERSION,
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
        # structural/advisor dependencies. Carry them forward so the newest
        # manifest remains a complete cache source.
        for key in ("structural_paths", "advisor"):
            artifact = entry.get(key)
            if isinstance(artifact, dict):
                current[key] = dict(artifact)
        summary = dict(result)
        summary["BrotherID"] = bro.BrotherID
        summary["Name"] = bro.Name
        summary["Level"] = bro.Level
        summary["Background"] = bro.Background
        return summary

    def store_summary(self, bro, roles, classification_cfg, summary):
        entry = self._current_entry(bro)
        entry["summary"] = {
            "input_hash": brother_summary_fingerprint(
                bro, roles, classification_cfg
            ),
            "engine_version": BROTHER_SUMMARY_ENGINE_VERSION,
            "result": dict(summary),
        }

    def mark_summary_computed(self):
        self.stats.summary_computed += 1

    def manifest_payload(
        self, *, generated_at, source_save, source_save_path=None
    ):
        return {
            "schema": "bb-incremental-v1",
            "generated_at": generated_at,
            "source_save": source_save,
            "source_save_path": source_save_path,
            "engine": {
                "role_projection": ROLE_PROJECTION_ENGINE_VERSION,
                "structural_paths": STRUCTURAL_PATH_ENGINE_VERSION,
                "advisor": ADVISOR_ENGINE_VERSION,
                "summary": BROTHER_SUMMARY_ENGINE_VERSION,
            },
            "brothers": self._current,
            "stats": {
                "previous_found": self.stats.previous_found,
                "role_reused": self.stats.role_reused,
                "role_computed": self.stats.role_computed,
                "structural_reused": self.stats.structural_reused,
                "structural_computed": self.stats.structural_computed,
                "advisor_reused": self.stats.advisor_reused,
                "advisor_computed": self.stats.advisor_computed,
                "summary_reused": self.stats.summary_reused,
                "summary_computed": self.stats.summary_computed,
                "ambiguous_states": self.stats.ambiguous_states,
                "previous_manifest": self.stats.previous_manifest,
                "miss_reasons": dict(self.miss_reasons),
            },
        }
