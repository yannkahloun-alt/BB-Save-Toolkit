"""Strategic analysis pipeline: Brother -> Fit role matrix + summary."""
from __future__ import annotations
from dataclasses import dataclass
import time
from ..classification import classify_bro, fit_label, perk_compatibility, role_sort_key
from ..levelup_advisor import advise_levelup
from ..projection import effective_stat_profile, project_role, project_role_fast
from ..projection.runtime import PROFILE

@dataclass
class AnalysisResult:
    fits: list[dict]
    summaries: list[dict]

def _role_row(bro, role: dict, *, fast: bool=False) -> dict:
    projection = project_role_fast(bro, role) if fast else project_role(bro, role)
    compat, compat_score, compat_signals = perk_compatibility(bro, role)
    return {"BrotherID":bro.BrotherID,"Name":bro.Name,"Level":bro.Level,"Background":bro.Background,**projection,
            "PerkCompatibility":compat,"PerkCompatibilityScore":compat_score,"PerkSignals":compat_signals}

def _best(rows): return max(rows, key=role_sort_key)

def _summary(bro,best,class_cfg,effective_stats,levelup_advice):
    category,reason=classify_bro(best,class_cfg)
    return {
        "BrotherID":bro.BrotherID,"Name":bro.Name,"Level":bro.Level,"Background":bro.Background,
        "Perks":"; ".join(bro.Perks),"Traits":"; ".join(bro.Traits),"Injuries":"; ".join(bro.Injuries),
        "Category":category,"CategoryReason":reason,"BestRole":best['Role'],
        "ProjectedFit":best['ProjectedFit'],"ProjectedFitPct":best['ProjectedFitPct'],
        "FitFeasibilityPct":best['FitFeasibilityPct'],
        "ProjectedFitLikelyMinPct":best['ProjectedFitLikelyMinPct'],"ProjectedFitLikelyMaxPct":best['ProjectedFitLikelyMaxPct'],
        "ProjectedFitFullMinPct":best['ProjectedFitFullMinPct'],"ProjectedFitFullMaxPct":best['ProjectedFitFullMaxPct'],
        "ProjectedFitLabel":fit_label(best['ProjectedFit'],class_cfg),
        "PerkCompatibility":best['PerkCompatibility'],
        "ProjectedMAtk":best['MAtk'],"ProjectedMDef":best['MDef'],"ProjectedRAtk":best['RAtk'],
        "ProjectedHP":best['HP'],"ProjectedFatigue":best['Fatigue'],"ProjectedResolve":best['Resolve'],
        "EffectiveStats":{k:round(v,1) for k,v in effective_stats.items()},
        "LevelUpAdvice":levelup_advice,
    }

def analyze_brothers(bros,roles,class_cfg,incremental_cache=None):
    fits=[]; summaries=[]
    for bro in bros:
        t=time.perf_counter(); rows=[]
        for role in roles:
            row = incremental_cache.get_role_row(bro, role) if incremental_cache is not None else None
            if row is None:
                row=_role_row(bro,role)
                if incremental_cache is not None:
                    incremental_cache.mark_computed()
            if incremental_cache is not None:
                incremental_cache.store_role_row(bro, role, row)
            rows.append(row)
        PROFILE['base_matrix_s']+=time.perf_counter()-t
        fits.extend(rows); best=_best(rows); effective,_=effective_stat_profile(bro)
        cached_summary = incremental_cache.get_summary(bro, roles, class_cfg) if incremental_cache is not None else None
        if cached_summary is not None:
            summaries.append(cached_summary)
            continue

        advice = incremental_cache.get_advisor(bro, roles) if incremental_cache is not None else None
        if advice is None:
            t=time.perf_counter(); advice=advise_levelup(bro,roles,rows); PROFILE['advisor_s']+=time.perf_counter()-t
            if incremental_cache is not None:
                incremental_cache.mark_advisor_computed()
                incremental_cache.store_advisor(bro, roles, advice)

        t=time.perf_counter(); summary=_summary(bro,best,class_cfg,effective,advice); summaries.append(summary); PROFILE['summary_s']+=time.perf_counter()-t
        if incremental_cache is not None:
            incremental_cache.mark_summary_computed()
            incremental_cache.store_summary(bro, roles, class_cfg, summary)
    return AnalysisResult(fits=fits,summaries=summaries)
