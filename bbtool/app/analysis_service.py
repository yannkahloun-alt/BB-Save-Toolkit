"""Transport-independent application service for save analysis."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
import hashlib
import time
from typing import Any

from references.update_references import ensure_references

from ..incremental import IncrementalCache, first_difference
from ..incremental.fingerprint import stable_hash
from ..models import BrotherIdentity, CampaignIdentity
from ..projection import configure_engine, get_profile, reset_profile
from ..save_parser import (
    parse_campaign_identity_bytes,
    parse_recruits_bytes,
    parse_roster_bytes,
    resolve_brother_identities,
)
from .analysis import AnalysisResult, analyze_brothers
from .health import build_run_health
from .output import build_projection_validation, public_brother_data
from .recruitment_policy import build_disabled_recruitment_analysis


@dataclass(frozen=True)
class SaveSource:
    """Immutable save content plus a display/provenance label, never identity."""

    content: bytes
    name: str = "supplied-save.sav"


@dataclass(frozen=True)
class AnalysisServiceOptions:
    verify_cache: bool = False


@dataclass(frozen=True)
class CompatibleCacheContext:
    """Optional recomputable cache input supplied by an outer adapter."""

    manifest: dict | None = None
    previous_path: object | None = None
    enabled: bool = True


@dataclass(frozen=True)
class ProgressEvent:
    stage: str
    status: str
    elapsed_seconds: float
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AnalysisServiceRequest:
    source: SaveSource
    roles: list[dict]
    classification: dict
    options: AnalysisServiceOptions = field(default_factory=AnalysisServiceOptions)
    cache: CompatibleCacheContext = field(default_factory=CompatibleCacheContext)
    on_progress: Callable[[ProgressEvent], None] | None = None
    assigned_build_resolver: (
        Callable[[CampaignIdentity], Mapping[str, Mapping[str, Any]]] | None
    ) = None


@dataclass
class AnalysisServiceResult:
    campaign_identity: CampaignIdentity
    brother_identities: dict[str, BrotherIdentity]
    roster: list
    recruits: list[dict]
    analysis: AnalysisResult
    roles: list[dict]
    classification: dict
    source_fingerprint: str
    configuration_fingerprints: dict[str, str]
    warnings: list[dict]
    diagnostics: dict
    timings: dict[str, float]
    progress_events: list[ProgressEvent]
    incremental_cache: IncrementalCache
    projection_validation: dict
    recruitment_analysis: list[dict]
    assigned_builds: Mapping[str, Mapping[str, Any]] | None = None

    @property
    def presentation_context(self) -> dict:
        return {
            "campaign_identity": self.campaign_identity,
            "brother_identities": self.brother_identities,
            "source_fingerprint": self.source_fingerprint,
            "configuration_fingerprints": self.configuration_fingerprints,
            "recruitment_analysis": self.recruitment_analysis,
            "result_signatures": self.incremental_cache.publication_signatures(),
            "company_intrinsic_coverage": self.analysis.company_intrinsic_coverage,
            "company_intended_coverage": self.analysis.company_intended_coverage,
            "summaries": self.analysis.summaries,
            "assigned_builds": self.assigned_builds,
        }

    @property
    def public_data(self) -> dict:
        return {
            "roster": [public_brother_data(bro) for bro in self.roster],
            "recruits": self.recruits,
            "fits": self.analysis.fits,
            "summaries": self.analysis.summaries,
            "company_intrinsic_coverage": self.analysis.company_intrinsic_coverage,
            "company_intended_coverage": self.analysis.company_intended_coverage,
            "roles": self.roles,
            "classification": self.classification,
        }


class AnalysisServiceError(RuntimeError):
    """Structured failure suitable for CLI, HTTP, tests, and workers."""

    def __init__(self, *, code: str, stage: str, message: str):
        self.code = code
        self.stage = stage
        self.message = message
        super().__init__(message)

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "stage": self.stage, "message": self.message}


def _structured_warnings(health: dict) -> list[dict]:
    warnings = [
        {"code": "recoverable_parse_failure", **item}
        for item in health["recoverable_parsing_failure_sample"]
    ]
    if health["unresolved_references_relevant_to_save"]:
        warnings.append({
            "code": "unresolved_references",
            "count": health["unresolved_references_relevant_to_save"],
            "sample": health["unresolved_reference_sample"],
        })
    if health["validation_roll_range_violations"]:
        warnings.append({
            "code": "roll_range_violations",
            "count": health["validation_roll_range_violations"],
        })
    return warnings


def analyze_save(request: AnalysisServiceRequest) -> AnalysisServiceResult:
    """Parse and analyze supplied save bytes without CLI, path, or output coupling."""
    started = time.perf_counter()
    events: list[ProgressEvent] = []
    timings: dict[str, float] = {}
    stage = "request"

    def emit(name: str, status: str, since: float, **details: Any) -> None:
        event = ProgressEvent(name, status, time.perf_counter() - since, details)
        events.append(event)
        if request.on_progress is not None:
            request.on_progress(event)

    try:
        if not isinstance(request.source.content, bytes):
            raise TypeError("source.content must be bytes")
        if not request.roles:
            raise ValueError("at least one effective archetype is required")

        stage = "references"
        tick = time.perf_counter()
        reference_status = ensure_references(verbose=False)
        timings[stage] = time.perf_counter() - tick
        emit(stage, "completed", tick, reference_status=reference_status)

        parse_diagnostics = {"recoverable_failures": []}
        stage = "campaign_identity"
        tick = time.perf_counter()
        campaign_identity = parse_campaign_identity_bytes(request.source.content)
        timings[stage] = time.perf_counter() - tick
        emit(
            stage,
            "completed",
            tick,
            confidence=campaign_identity.confidence,
        )
        assigned_builds = None
        if (
            request.assigned_build_resolver is not None
            and campaign_identity.confidence == "exact"
        ):
            assigned_builds = dict(request.assigned_build_resolver(campaign_identity))

        stage = "roster"
        tick = time.perf_counter()
        roster = parse_roster_bytes(request.source.content, diagnostics=parse_diagnostics)
        brother_identities = resolve_brother_identities(roster, campaign_identity)
        timings[stage] = time.perf_counter() - tick
        emit(stage, "completed", tick, count=len(roster))

        stage = "recruits"
        tick = time.perf_counter()
        recruits = parse_recruits_bytes(request.source.content, diagnostics=parse_diagnostics)
        timings[stage] = time.perf_counter() - tick
        emit(stage, "completed", tick, count=len(recruits))

        stage = "analysis"
        configure_engine()
        reset_profile()
        cache = IncrementalCache(
            request.cache.manifest,
            enabled=request.cache.enabled,
            previous_path=request.cache.previous_path,
        )
        tick = time.perf_counter()
        analysis = analyze_brothers(
            roster, request.roles, request.classification, cache,
            brother_identities, assigned_builds,
        )
        timings[stage] = time.perf_counter() - tick
        emit(
            stage,
            "completed",
            tick,
            brothers=len(roster),
            archetypes=len(request.roles),
            role_reused=cache.stats.role_reused,
            role_computed=cache.stats.role_computed,
        )

        if request.options.verify_cache and request.cache.enabled:
            stage = "cache_verification"
            tick = time.perf_counter()
            clean = analyze_brothers(
                roster, request.roles, request.classification, None,
                brother_identities, assigned_builds,
            )
            difference = first_difference(
                {
                    "fits": analysis.fits,
                    "summaries": analysis.summaries,
                    "company_intrinsic_coverage": analysis.company_intrinsic_coverage,
                    "company_intended_coverage": analysis.company_intended_coverage,
                },
                {
                    "fits": clean.fits,
                    "summaries": clean.summaries,
                    "company_intrinsic_coverage": clean.company_intrinsic_coverage,
                    "company_intended_coverage": clean.company_intended_coverage,
                },
            )
            if difference is not None:
                path, incremental_value, full_value = difference
                raise AnalysisServiceError(
                    code="cache_verification_failed",
                    stage=stage,
                    message=(
                        f"Mismatch at {path}: incremental={incremental_value!r} "
                        f"full={full_value!r}"
                    ),
                )
            timings[stage] = time.perf_counter() - tick
            emit(stage, "completed", tick)

        stage = "validation"
        pre_validation_projection_profile = get_profile()
        tick = time.perf_counter()
        projection_validation = build_projection_validation(
            roster, analysis.fits, request.roles, cache.get_validation_oracle,
            cache.store_validation_oracle,
        )
        timings[stage] = time.perf_counter() - tick
        final_projection_profile = get_profile()
        validation_projection_diagnostics = {
            "seeded_projection_calls": projection_validation["summary"]["comparisons"],
            "blind_cache_lookups": projection_validation["summary"]["comparisons"],
            "trajectory_cache_hits": (
                final_projection_profile.get("trajectory_cache_hits", 0)
                - pre_validation_projection_profile.get("trajectory_cache_hits", 0)
            ),
            "trajectory_cache_misses": (
                final_projection_profile.get("trajectory_cache_misses", 0)
                - pre_validation_projection_profile.get("trajectory_cache_misses", 0)
            ),
            "trajectory_seconds": round(
                final_projection_profile.get("trajectory_s", 0.0)
                - pre_validation_projection_profile.get("trajectory_s", 0.0),
                6,
            ),
            "oracle_reused": projection_validation["summary"].get("oracle_reused", 0),
            "oracle_recomputed": projection_validation["summary"].get("oracle_recomputed", 0),
        }
        emit(
            stage,
            "completed",
            tick,
            comparisons=projection_validation["summary"]["comparisons"],
            roll_range_violations=projection_validation["summary"][
                "roll_range_violations"
            ],
        )

        health = build_run_health(
            roster,
            recruits,
            reference_status,
            parse_diagnostics=parse_diagnostics,
            incremental_cache=cache,
            validation_payload=projection_validation,
        )
        warnings = _structured_warnings(health)
        stage = "recruitment_analysis"
        tick = time.perf_counter()
        recruitment_analysis = build_disabled_recruitment_analysis(
            recruits, request.roles
        )
        timings[stage] = time.perf_counter() - tick
        emit(
            stage,
            "completed",
            tick,
            recruits=len(recruits),
            analytical_potential="disabled_pending_validation",
        )
        timings["total"] = time.perf_counter() - started
        return AnalysisServiceResult(
            campaign_identity=campaign_identity,
            brother_identities=brother_identities,
            roster=roster,
            recruits=recruits,
            analysis=analysis,
            roles=request.roles,
            classification=request.classification,
            source_fingerprint="sha256:"
            + hashlib.sha256(request.source.content).hexdigest(),
            configuration_fingerprints={
                "archetypes": stable_hash(request.roles),
                "classification": stable_hash(request.classification),
            },
            warnings=warnings,
            diagnostics={
                "parse": parse_diagnostics,
                "references": reference_status,
                "run_health": health,
                "projection_profile": pre_validation_projection_profile,
                "validation_projection": validation_projection_diagnostics,
                "cache_miss_reasons": dict(sorted(cache.miss_reasons.items())),
            },
            timings=timings,
            progress_events=events,
            incremental_cache=cache,
            projection_validation=projection_validation,
            recruitment_analysis=recruitment_analysis,
            assigned_builds=assigned_builds,
        )
    except AnalysisServiceError:
        raise
    except Exception as exc:
        raise AnalysisServiceError(
            code=f"{stage}_failed",
            stage=stage,
            message=str(exc),
        ) from exc
