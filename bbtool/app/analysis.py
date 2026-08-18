"""Strategic analysis pipeline: Brother -> Fit role matrix + summary."""
from __future__ import annotations
from dataclasses import dataclass, replace
import itertools
import time
from ..classification import classify_bro, fit_label, perk_compatibility, role_sort_key
from ..levelup_advisor import advise_levelup
from ..projection import effective_stat_profile, project_role, project_role_fast, structural_projection_perks
from ..projection.perks import structural_projection_perk_stats
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

def _structural_perk_paths(bro, roles, class_cfg, base_rows=None):
    available=[name for name in structural_projection_perks() if name not in bro.Perks]
    if not available or (bro.PerkPoints<=0 and bro.Level>=11): return []
    out=[]
    for size in range(1,len(available)+1):
        for combo in itertools.combinations(available,size):
            simulated=replace(bro,Perks=[*bro.Perks,*combo])
            affected_stats = structural_projection_perk_stats(combo)
            base_by_role = {row["Role"]: row for row in (base_rows or ())}
            rows=[]
            for role in roles:
                fit_stats = {stat for stat, cfg in role.get("stats", {}).items() if cfg.get("fit")}
                base_row = base_by_role.get(role["name"])
                if base_row is not None and fit_stats.isdisjoint(affected_stats):
                    # Structural perks cannot alter this role's Fit trajectory. Reuse
                    # the already-computed full base projection, but recompute perk
                    # compatibility for the simulated perk set.
                    row = dict(base_row)
                    compat, compat_score, compat_signals = perk_compatibility(simulated, role)
                    row.update(PerkCompatibility=compat, PerkCompatibilityScore=compat_score, PerkSignals=compat_signals)
                else:
                    row=_role_row(simulated,role,fast=True)
                rows.append(row)
            best=_best(rows)
            winning_role=next(role for role in roles if role['name']==best['Role'])
            # Reused base rows are already full projections. A newly computed
            # structural row is fast, so expand only that winning row; its
            # trajectory itself is a cache hit.
            full = best if "ProjectedRanges" in best else _role_row(simulated,winning_role)
            effective,_=effective_stat_profile(simulated)
            category,reason=classify_bro(full,class_cfg)
            out.append({
                "Perks":list(combo),"Label":" + ".join(combo),"Role":best['Role'],
                "Category":category,"CategoryReason":reason,
                "ProjectedFitPct":full['ProjectedFitPct'],
                "FitFeasibilityPct":full['FitFeasibilityPct'],
                "EffectiveStats":{k:round(v,1) for k,v in effective.items()},
                "BestRoleDetail":full,
                "LevelUpAdvice":advise_levelup(simulated,roles,rows),
            })
    out.sort(key=lambda r:(len(r['Perks']),r['Label'],r['Role']))
    return out

def _category_rank(category): return {'Trash':0,'Fodder':1,'Use':2,'Invest':3}.get(category,-1)

def _select_classification_path(best, structural_paths, class_cfg):
    base_cat,base_reason=classify_bro(best,class_cfg)
    candidates=[{"Perks":[],"Label":"Base","Role":best['Role'],"Category":base_cat,"CategoryReason":base_reason,"BestRoleDetail":best},*structural_paths]
    return max(candidates,key=lambda p:(
        _category_rank(p['Category']),-len(p['Perks']),
        p['BestRoleDetail']['ProjectedFit'],
        float(p['BestRoleDetail'].get('FitFeasibilityPct',0.0)),
        float(p['BestRoleDetail'].get('ProjectedFitLikelyMinPct',p['BestRoleDetail']['ProjectedFitPct']))))

def _summary(bro,best,class_cfg,effective_stats,structural_paths,levelup_advice):
    selected=_select_classification_path(best,structural_paths,class_cfg)
    sb=selected['BestRoleDetail']; category=selected['Category']; reason=selected['CategoryReason']
    base_cat,base_reason=classify_bro(best,class_cfg)
    all_paths=[{"Perks":[],"Label":"Base","Role":best['Role'],"Category":base_cat,"CategoryReason":base_reason,"BestRoleDetail":best},*structural_paths]
    return {
        "BrotherID":bro.BrotherID,"Name":bro.Name,"Level":bro.Level,"Background":bro.Background,
        "Perks":"; ".join(bro.Perks),"Traits":"; ".join(bro.Traits),"Injuries":"; ".join(bro.Injuries),
        "Category":category,"CategoryReason":reason,"BestRole":sb['Role'],
        "ProjectedFit":sb['ProjectedFit'],"ProjectedFitPct":sb['ProjectedFitPct'],
        "FitFeasibilityPct":sb['FitFeasibilityPct'],
        "ProjectedFitLikelyMinPct":sb['ProjectedFitLikelyMinPct'],"ProjectedFitLikelyMaxPct":sb['ProjectedFitLikelyMaxPct'],
        "ProjectedFitFullMinPct":sb['ProjectedFitFullMinPct'],"ProjectedFitFullMaxPct":sb['ProjectedFitFullMaxPct'],
        "ProjectedFitLabel":fit_label(sb['ProjectedFit'],class_cfg),
        "PerkCompatibility":sb['PerkCompatibility'],
        "ProjectedMAtk":sb['MAtk'],"ProjectedMDef":sb['MDef'],"ProjectedRAtk":sb['RAtk'],
        "ProjectedHP":sb['HP'],"ProjectedFatigue":sb['Fatigue'],"ProjectedResolve":sb['Resolve'],
        "EffectiveStats": selected.get('EffectiveStats') if selected['Perks'] else {k:round(v,1) for k,v in effective_stats.items()},
        "SelectedClassificationPath":{"Perks":selected['Perks'],"Label":selected['Label'],"Role":selected['Role'],"Category":selected['Category']},
        "ClassificationPaths":[{
            "Perks":p['Perks'],"Label":p['Label'],"Role":p['Role'],"Category":p['Category'],"CategoryReason":p['CategoryReason'],
            "ProjectedFitPct":p['BestRoleDetail']['ProjectedFitPct'],
            "ProjectedFitLikelyMinPct":p['BestRoleDetail'].get('ProjectedFitLikelyMinPct'),
            "ProjectedFitLikelyMaxPct":p['BestRoleDetail'].get('ProjectedFitLikelyMaxPct'),
            "ProjectedFitFullMinPct":p['BestRoleDetail'].get('ProjectedFitFullMinPct'),
            "ProjectedFitFullMaxPct":p['BestRoleDetail'].get('ProjectedFitFullMaxPct'),
            "FitFeasibilityPct":p['BestRoleDetail'].get('FitFeasibilityPct'),
        } for p in all_paths],
        "StructuralPerkAlternatives":structural_paths,
        "ColossusBestRole":next((r for r in structural_paths if r['Perks']==['Colossus']),None),
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

        structural = incremental_cache.get_structural_paths(bro, roles) if incremental_cache is not None else None
        if structural is None:
            t=time.perf_counter(); structural=_structural_perk_paths(bro,roles,class_cfg,rows); PROFILE['structural_paths_s']+=time.perf_counter()-t
            if incremental_cache is not None:
                incremental_cache.mark_structural_computed()
                incremental_cache.store_structural_paths(bro, roles, structural)

        advice = incremental_cache.get_advisor(bro, roles) if incremental_cache is not None else None
        if advice is None:
            t=time.perf_counter(); advice=advise_levelup(bro,roles,rows); PROFILE['advisor_s']+=time.perf_counter()-t
            if incremental_cache is not None:
                incremental_cache.mark_advisor_computed()
                incremental_cache.store_advisor(bro, roles, advice)

        t=time.perf_counter(); summary=_summary(bro,best,class_cfg,effective,structural,advice); summaries.append(summary); PROFILE['summary_s']+=time.perf_counter()-t
        if incremental_cache is not None:
            incremental_cache.mark_summary_computed()
            incremental_cache.store_summary(bro, roles, class_cfg, summary)
    return AnalysisResult(fits=fits,summaries=summaries)
