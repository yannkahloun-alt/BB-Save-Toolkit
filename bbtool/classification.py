from __future__ import annotations
from .models import Brother

def fit_label(score: float, cfg: dict) -> str:
    d=cfg['display']
    if score>=d['premium_fit']: return 'PREMIUM'
    if score>=d['good_fit']: return 'GOOD'
    if score>=d['viable_fit']: return 'VIABLE'
    return 'LOW'

def perk_compatibility(bro: Brother, role: dict) -> tuple[str,int,list[str]]:
    perks=set(bro.Perks); conflicts=sorted(perks.intersection(set(role.get('perk_conflicts',[]))))
    if conflicts: return 'CONFLICT',-100,conflicts
    total=0; signals=[]
    for perk,weight in role.get('perk_affinity',{}).items():
        if perk in perks: total+=int(weight); signals.append(perk)
    if total < 1:
        label = 'NEUTRAL'
    elif total < 2:
        label = 'LOW'
    elif total < 5:
        label = 'MEDIUM'
    else:
        label = 'HIGH'
    return label,total,signals

def role_sort_key(row: dict):
    conflict_penalty=-1.0 if row.get('PerkCompatibility')=='CONFLICT' else 0.0
    return (row['ProjectedFit']+conflict_penalty,
            float(row.get('FitFeasibilityPct',0.0)),
            float(row.get('ProjectedFitLikelyMinPct', row['ProjectedFitPct'])))

def classify_bro(best: dict, cfg: dict) -> tuple[str,str]:
    t=cfg['thresholds']; pf=float(best['ProjectedFit']); full_max=float(best.get('ProjectedFitFullMaxPct',best['ProjectedFitPct']))/100.0
    if pf>=t['Invest']['min_projected_fit']:
        return 'Invest',f'expected Fit {pf:.2f}'
    if pf>=t['Use']['min_projected_fit']:
        return 'Use',f'expected Fit {pf:.2f}'
    if full_max>=t['Fodder']['min_full_max_fit']:
        return 'Fodder',f'expected Fit {pf:.2f}; full-range ceiling {full_max:.2f} still reaches Use threshold'
    return 'Trash',f'expected Fit {pf:.2f}; full-range ceiling {full_max:.2f} stays below Use threshold'
