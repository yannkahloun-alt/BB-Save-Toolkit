from __future__ import annotations

import html
import re
from pathlib import Path

from .classification import classify_bro
from .projection.perks import effective_stat_profile

CLASS_ICONS = {"Invest":"💎","Use":"🛡️","Fodder":"⚔️","Trash":"☠️"}
CLASS_CSS = {"Invest":"class-invest","Use":"class-use","Fodder":"class-fodder","Trash":"class-trash"}

STAT_ORDER = ["HP", "Fatigue", "Resolve", "Initiative", "MAtk", "RAtk", "MDef", "RDef"]
STAT_SHORT = {
    "HP": "HP", "Fatigue": "FAT", "Resolve": "RES", "Initiative": "INI",
    "MAtk": "MATK", "RAtk": "RATK", "MDef": "MDEF", "RDef": "RDEF",
}

def esc(v):
    return html.escape(str(v), quote=True)

def class_icon(category):
    return CLASS_ICONS.get(str(category), "•")

def class_css(category):
    return CLASS_CSS.get(str(category), "")



def classification_path_html(path: dict) -> str:
    """Render one strategic-classification path cell."""
    label = path.get("Label", "Base")
    role = path.get("Role", "")
    category = path.get("Category", "")
    enabler = "Natural" if label == "Base" else f"via {label}"
    return (
        f'<div class="classification-path-row {class_css(category)}" title="{esc(role)} · {esc(category)} · {esc(enabler)}">'
        f'<div class="classification-path-primary">'
        f'<strong class="classification-path-role">{esc(role)}</strong>'
        f'<span class="classification-path-class"><span class="class-icon">{class_icon(category)}</span><strong>{esc(category)}</strong></span>'
        f'</div>'
        f'<span class="classification-path-enabler">{esc(enabler)}</span>'
        f'</div>'
    )


def classification_path_metric_html(path: dict, metric: str) -> str:
    """Render one strategic-classification metric cell with the path category style."""
    value = float(path.get(metric, 0.0))
    return (
        f'<div class="path-metric-row {class_css(path.get("Category", ""))}">'
        f'<span class="path-metric-label">{esc(path.get("Label", "Base"))}</span>'
        f'<strong>{value:.1f}%</strong>'
        f'</div>'
    )


def classification_path_fit_range_html(path: dict) -> str:
    """Render Expected + likely/full Fit ranges for one classification path."""
    exp = path.get("ProjectedFitPct")
    lmin = path.get("ProjectedFitLikelyMinPct")
    lmax = path.get("ProjectedFitLikelyMaxPct")
    fmin = path.get("ProjectedFitFullMinPct")
    fmax = path.get("ProjectedFitFullMaxPct")
    title = (
        "Expected Fit: average final Fit across simulated development paths. "
        "Likely range: 5th–95th percentile (about 90% of simulated outcomes). "
        "Full range: explicit worst/best simulated extremes; endpoints may be very unlikely."
    )
    if None in (exp, lmin, lmax, fmin, fmax):
        body = '<strong>N/A</strong>'
    else:
        body = (
            f'<strong>{float(exp):.1f}%</strong>'
            f'<small class="path-fit-likely">Likely {float(lmin):.1f}–{float(lmax):.1f}</small>'
            f'<small class="path-fit-full">Full {float(fmin):.1f}–{float(fmax):.1f}</small>'
        )
    return (
        f'<div class="path-fit-range-row {class_css(path.get("Category", ""))}" title="{esc(title)}">'
        f'<span class="path-metric-label">{esc(path.get("Label", "Base"))}</span>'
        f'<span class="path-fit-range-values">{body}</span>'
        '</div>'
    )


def fit_measure_help_html(row: dict) -> str:
    """Explain the point Fit estimate and its distinct threshold probability."""
    fit = float(row["ProjectedFitPct"])
    probability = float(row["FitFeasibilityPct"])
    if fit < 100.0:
        relationship = "The expected Fit is below 100%."
    elif fit > 100.0:
        relationship = (
            "The expected Fit is above 100%; displayed Fit is not capped when "
            "the projected stat profile exceeds the archetype targets."
        )
    else:
        relationship = "The expected Fit is exactly 100%."
    return (
        '<details class="fit-measure-help">'
        '<summary>How Fit and P(Fit≥100) differ</summary>'
        '<div>'
        '<p><strong>Fit</strong> is the average level-11 archetype score across simulated development outcomes. '
        'It is a score, not a probability, and may exceed 100%.</p>'
        '<p><strong>P(Fit≥100)</strong> is the percentage of those simulated outcomes whose final Fit reaches '
        'or exceeds 100%. It can differ from the average because outcomes vary around that average.</p>'
        f'<p class="fit-measure-current">{esc(relationship)} Current values: Fit {fit:.1f}%; '
        f'P(Fit≥100) {probability:.1f}%.</p>'
        '</div></details>'
    )

def optimized_allocation_help_html() -> str:
    """Explain the normal level-11 allocation policy without engine jargon."""
    return (
        '<details class="optimized-allocation-help">'
        '<summary>How stat allocation is optimized</summary>'
        '<div>'
        '<p>At every future level-up through level 11, the projection chooses exactly '
        'three of the eight core stats. All eight are eligible; the choice favors the '
        'combination expected to produce the highest final Fit for this archetype.</p>'
        '<p>Talent stars shape each stat\'s possible roll range. Archetype baselines, '
        'targets, weights, and any Fit-only ceilings determine how valuable each gain is. '
        'Exact permanent trait and permanent-injury effects are included in the projected profile. '
        'Owned or hypothetical perks do not alter this natural-stat projection; supported structural '
        'perk paths are evaluated separately.</p>'
        '<p>This is an optimized development policy, not a guaranteed outcome or a claim that '
        'every roll will be maximal. Temporary injuries and quarantined FutureRolls do not '
        'drive normal projection choices.</p>'
        '</div></details>'
    )


def bro_anchor(brother_id):
    import hashlib
    return "bro-" + hashlib.sha1(str(brother_id).encode("utf-8")).hexdigest()[:12]

def heat(v, inverse=False):
    v = float(v)
    if inverse:
        v = 100.0 - v
    if v >= 85: return "heat5"
    if v >= 70: return "heat4"
    if v >= 55: return "heat3"
    if v >= 40: return "heat2"
    return "heat1"

def range_text(rng):
    lo, hi = rng["min"], rng["max"]
    if lo == hi:
        return f"{lo:g}"
    return f"{lo:g}–{hi:g}"


def _axis_position(value: float, axis_min: float, axis_max: float) -> float:
    """Return an uncluttered, numerically accurate percentage on one stat axis."""
    if axis_max <= axis_min:
        return 50.0
    return 100.0 * (float(value) - axis_min) / (axis_max - axis_min)


def _fit_stat_rows(row: dict):
    for stat in STAT_ORDER:
        rng = row.get("ProjectedRanges", {}).get(stat)
        if rng:
            yield stat, rng


def target_profile_html(row: dict) -> str:
    stats = ''.join(
        '<div class="target-profile-stat">'
        f'<span class="stat-icon" aria-hidden="true">{STAT_SHORT[stat]}</span>'
        f'<strong>{esc(stat)}</strong>'
        f'<span><small>Target</small><b>{float(rng["target"]):g}</b></span>'
        f'<span><small>Baseline</small><b>{float(rng["baseline"]):g}</b></span>'
        '</div>'
        for stat, rng in _fit_stat_rows(row)
    )
    explanations = (
        ("EXPECTED", "Average projected value at level 11 under the optimized stat allocation."),
        ("TARGET", "The desired end value for this archetype to be maximally effective in this role."),
        ("BASELINE", "The minimum useful value for this stat in this role."),
        ("RANGE", "Possible level 11 values under the optimized stat allocation (min → max)."),
        ("WEIGHT", "The importance of this stat in the Fit calculation. Higher weight = higher impact."),
    )
    explanation_html = ''.join(
        f'<div><strong>{heading}</strong><span>{esc(copy)}</span></div>'
        for heading, copy in explanations
    )
    return (
        '<details class="target-profile-explainer">'
        '<summary><span class="target-profile-label">TARGET PROFILE</span>'
        f'<div class="target-profile-stats">{stats}</div>'
        '<span class="target-profile-chevron" aria-hidden="true"></span></summary>'
        f'<div class="projection-explanations">{explanation_html}</div>'
        '</details>'
    )


def development_focus_html(b, row: dict, effective=None) -> str:
    """Render pipeline-provided level-11 ranges and references on one axis."""
    effective=effective or {}
    chips=[]
    for stat, rng in _fit_stat_rows(row):
        comp=row.get("ProjectedComponents",{}).get(stat, {})
        current=float(effective.get(stat,getattr(b,stat)))
        values = [float(rng[key]) for key in ("min", "max", "ev", "baseline", "target")]
        data_min, data_max = min(values), max(values)
        span = data_max - data_min
        padding = max(span * 0.08, 1.0)
        axis_min, axis_max = data_min - padding, data_max + padding
        range_left = _axis_position(float(rng["min"]), axis_min, axis_max)
        range_right = _axis_position(float(rng["max"]), axis_min, axis_max)
        marker_data = [
            (kind, key, label, _axis_position(float(rng[key]), axis_min, axis_max))
            for kind, key, label in (
                ("baseline", "baseline", "Baseline"),
                ("target", "target", "Target"),
                ("expected", "ev", "Expected"),
            )
        ]
        label_rows = {}
        previous_position = None
        previous_row = 0
        for kind, _key, _label, position in sorted(marker_data, key=lambda item: item[3]):
            row_index = previous_row + 1 if previous_position is not None and position - previous_position < 12 else 0
            label_rows[kind] = row_index
            previous_position, previous_row = position, row_index
        markers = ''.join(
            f'<span class="projection-marker marker-{kind}" style="left:{position:.4f}%;--label-top:{27 + 13 * label_rows[kind]}px" '
            f'title="{label} {float(rng[key]):g}" aria-label="{label} {float(rng[key]):g}">'
            f'<i></i><b>{float(rng[key]):g}</b></span>'
            for kind, key, label, position in marker_data
        )
        cap_note = ""
        if comp.get("ceiling") is not None:
            cap_note = (
                f'<small class="focus-ceiling">Fit ceiling {float(comp["ceiling"]):g}'
                + (
                    f' · using {float(comp["fit_value"]):g}'
                    if comp.get("capped")
                    else ''
                )
                + '</small>'
            )
        chips.append(
            '<div class="development-focus-chip">'
            '<div class="development-card-head">'
            f'<span class="stat-icon" aria-hidden="true">{STAT_SHORT[stat]}</span><strong>{esc(stat)}</strong>'
            f'<small>Weight <b>{float(rng["weight"]):g}</b></small></div>'
            f'<div class="development-values">{current:g} <em>→</em> {esc(range_text(rng))}</div>'
            '<div class="projection-axis">'
            f'<span class="projected-range" style="left:{range_left:.4f}%;width:{range_right-range_left:.4f}%"></span>'
            f'{markers}</div>'
            f'{cap_note}</div>'
        )
    return '<div class="development-focus-grid">'+''.join(chips)+'</div>' if chips else '<span class="muted">No Fit stat configured.</span>'


def role_important_stats(role: dict | None) -> set[str]:
    if not role: return set()
    return {stat for stat,cfg in role.get("stats",{}).items() if cfg.get("fit") or "target" in cfg}


_DESCRIPTION_CACHE = None


def _descriptions():
    global _DESCRIPTION_CACHE
    if _DESCRIPTION_CACHE is not None:
        return _DESCRIPTION_CACHE
    path = Path(__file__).resolve().parents[1] / "references" / "descriptions.json"
    try:
        import json
        raw = json.loads(path.read_text(encoding="utf-8"))
        _DESCRIPTION_CACHE = raw.get("entries", {})
    except Exception:
        _DESCRIPTION_CACHE = {}
    return _DESCRIPTION_CACHE


def described_items(names, *, exclude=()):
    exclude = set(exclude or ())
    entries = _descriptions()
    parts = []
    for name in names or []:
        if name in exclude:
            continue
        desc = entries.get(name)
        if desc:
            parts.append(
                f'<span class="hover-info" title="{esc(desc)}">{esc(name)}</span>'
            )
        else:
            parts.append(f'<span>{esc(name)}</span>')
    return ", ".join(parts) if parts else "—"




def fit_uncertainty_track(row):
    raw_expected=float(row["ProjectedFitPct"]); raw_min=float(row["ProjectedFitLikelyMinPct"]); raw_max=float(row["ProjectedFitLikelyMaxPct"])
    scale_max=120.0
    def pos(v): return 100.0*max(0.0,min(scale_max,float(v)))/scale_max
    left=pos(min(raw_min,raw_max)); right=pos(max(raw_min,raw_max)); width=max(1.0,right-left); dot=pos(raw_expected)
    return (f'<span class="uncertainty-track" title="Likely {raw_min:.1f}–{raw_max:.1f}% · expected {raw_expected:.1f}%">'
            f'<span class="track-row raw-track"><span class="track-line" style="left:{left:.2f}%;width:{width:.2f}%"></span>'
            f'<span class="track-dot" style="left:{dot:.2f}%"></span></span></span>')


def classification_ceiling_html(row: dict, category: str, class_cfg: dict) -> str:
    """Explain the full-range ceiling that separates Fodder from Trash."""
    if category not in {"Fodder", "Trash"}:
        return ""
    full_max = float(
        row["ProjectedFitFullMaxPct"]
        if row.get("ProjectedFitFullMaxPct") is not None
        else row["ProjectedFitPct"]
    )
    use_threshold = 100.0 * float(
        class_cfg["thresholds"]["Fodder"]["min_full_max_fit"]
    )
    outcome = "can reach Use" if category == "Fodder" else "below Use"
    return (
        '<small class="classification-ceiling">'
        f'Full ceiling <b>{full_max:.1f}%</b> · {outcome} ({use_threshold:.1f}%)'
        '</small>'
    )


def current_stat_chips(b, effective=None, important_stats=None):
    effective = effective or {}
    important_stats = set(important_stats or [])
    vals = [
        ("HP", "HP", b.HP, b.HPStars),
        ("FAT", "Fatigue", b.Fatigue, b.FatigueStars),
        ("RES", "Resolve", b.Resolve, b.ResolveStars),
        ("INI", "Initiative", b.Initiative, b.InitiativeStars),
        ("MATK", "MAtk", b.MAtk, b.MAtkStars),
        ("RATK", "RAtk", b.RAtk, b.RAtkStars),
        ("MDEF", "MDef", b.MDef, b.MDefStars),
        ("RDEF", "RDef", b.RDef, b.RDefStars),
    ]
    out = []
    for label, stat, raw, stars in vals:
        star_txt = "★" * int(stars)
        eff = float(effective.get(stat, raw))
        changed = abs(eff - float(raw)) > 0.01
        if changed:
            eff_txt = f"{eff:g}"
            value_html = (
                f'<strong class="effective-stat">{eff_txt}</strong>'
                f'<small class="raw-stat">raw {raw}</small>'
            )
        else:
            value_html = f'<strong>{raw}</strong>'
        important_cls = " important" if stat in important_stats else ""
        out.append(
            f'<div class="stat-chip{important_cls}"><span>{label}</span>{value_html}'
            f'<small>{star_txt or "—"}</small></div>'
        )
    return "".join(out)


_VOID_TAGS = {"meta", "link", "br", "hr", "img", "input", "source", "area", "base", "col", "embed", "param", "track", "wbr"}

def pretty_html(source: str) -> str:
    """
    Lightweight dependency-free HTML formatter for generated reports.
    It only inserts whitespace between tags; report semantics are unchanged.
    """
    source = re.sub(r">\s*<", ">\n<", source.strip())
    lines = [line.strip() for line in source.splitlines() if line.strip()]
    out = []
    indent = 0

    tag_re = re.compile(r"<(/?)([A-Za-z0-9]+)(?:\s[^>]*)?>")
    for line in lines:
        stripped = line.strip()

        # Dedent when the line begins with a closing tag.
        if stripped.startswith("</"):
            indent = max(0, indent - 1)

        out.append("  " * indent + stripped)

        # Work out net nesting change on this line.
        opens = 0
        closes = 0
        for match in tag_re.finditer(stripped):
            slash, tag = match.group(1), match.group(2).lower()
            full = match.group(0)
            if tag in _VOID_TAGS or full.endswith("/>"):
                continue
            if slash:
                closes += 1
            else:
                opens += 1

        # If we already dedented for a leading closing tag, don't count that
        # close a second time in the net change.
        if stripped.startswith("</") and closes:
            closes -= 1

        indent = max(0, indent + opens - closes)

    return "\n".join(out) + "\n"


def public_value(value, fallback="—"):
    if value is None or value == "":
        return fallback
    return esc(value)


def recruit_table_rows(recruits):
    rows = []

    for rec in recruits:
        traits = rec.get("Traits") or []
        tryout_done = rec.get("TryoutDone")

        if tryout_done is True:
            traits_text = ", ".join(traits) if traits else "None"
            traits_class = "traits-revealed"
            traits_icon = "✦"
        elif tryout_done is False:
            traits_text = "Hidden"
            traits_class = "traits-hidden"
            traits_icon = "◌"
        else:
            traits_text = "Unknown"
            traits_class = "traits-unknown"
            traits_icon = "?"

        title = rec.get("Title") or "—"
        level = rec.get("Level")
        hire = rec.get("HireCost")
        wage = rec.get("DailyWage")

        rows.append(
            '<tr>'
            f'<td class="sticky recruit-name"><b>{esc(rec.get("Name", "Unknown"))}</b></td>'
            f'<td class="recruit-title">{esc(title)}</td>'
            f'<td class="recruit-level"><span class="level-pill">L{public_value(level)}</span></td>'
            f'<td class="recruit-background">{public_value(rec.get("Background"))}</td>'
            f'<td class="recruit-traits {traits_class}">'
            f'<span class="trait-icon">{traits_icon}</span>{esc(traits_text)}</td>'
            f'<td class="recruit-cost"><span class="money-icon">¤</span>{public_value(hire)}</td>'
            f'<td class="recruit-wage"><span class="wage-icon">↻</span>{public_value(wage)}</td>'
            '</tr>'
        )

    return ''.join(rows)


def recruit_settlement_panels(recruits):
    """
    Render one collapsed recruitment table per settlement.

    Settlement order follows serialized save order. Panels are exclusive in
    report.js, mirroring Brother Details behavior.
    """
    grouped = {}

    for rec in recruits:
        settlement = rec.get("Settlement") or "Unknown settlement"
        grouped.setdefault(settlement, []).append(rec)

    panels = []

    for index, (settlement, settlement_recruits) in enumerate(grouped.items()):
        panel_id = f"settlement-{index}"
        rows = recruit_table_rows(settlement_recruits)
        count = len(settlement_recruits)
        count_text = f"{count} candidate" if count == 1 else f"{count} candidates"

        panels.append(
            f'<details id="{panel_id}" class="settlement-panel">'
            '<summary class="settlement-head">'
            f'<span class="settlement-name">{esc(settlement)}</span>'
            f'<span class="settlement-count">{count_text}</span>'
            '</summary>'
            '<div class="settlement-panel-body">'
            '<div class="tw recruits-table"><table><thead><tr>'
            '<th class="sticky col-name">Name</th><th class="col-title">Title</th>'
            '<th class="col-level">Lvl</th><th class="col-background">Background</th>'
            '<th class="col-traits">Revealed traits</th>'
            '<th class="col-cost">¤ Hire</th><th class="col-wage">↻ /day</th>'
            '</tr></thead><tbody>'
            + rows
            + '</tbody></table></div>'
            '</div>'
            '</details>'
        )

    return ''.join(panels)



def _metric_delta(before: float, after: float, *, lower_is_better: bool = False) -> tuple[str, str]:
    delta = after - before
    good_delta = -delta if lower_is_better else delta
    css = "good" if good_delta > 0.04 else "flat" if abs(good_delta) <= 0.04 else "bad"
    sign = "+" if delta > 0 else ""
    return f"{sign}{delta:.1f}", css


def levelup_advice_html(
    advice,
    *,
    label: str = "RECOMMENDATION",
    trajectory_label: str | None = None,
    colossus: bool = False,
) -> str:
    if not advice:
        return ""

    rec = advice["Recommended"]
    alt = advice.get("Alternative")
    reasons = advice.get("PickReasons", {})
    all_rolls = advice.get("AllRolls", {}) or {}

    labels = (
        ("HP", "HP"), ("Fatigue", "FAT"), ("Resolve", "RES"),
        ("Initiative", "INI"), ("MAtk", "MAtk"), ("RAtk", "RAtk"),
        ("MDef", "MDef"), ("RDef", "RDef"),
    )

    def signed(value: float, decimals: int = 1) -> str:
        if abs(value) < 0.05:
            return "0"
        return f'{"+" if value > 0 else ""}{value:.{decimals}f}'

    def roll_board(candidate: dict, *, runner_up: bool = False) -> str:
        selected = set(candidate["Stats"])
        cards = []
        for stat, display in labels:
            meta = all_rolls.get(stat)
            if not meta:
                continue
            is_selected = stat in selected
            band = meta.get("Label", "")
            reason = reasons.get(stat, "") if (is_selected and not runner_up) else ""
            cards.append(
                f'<div class="lu-pick-card{" selected" if is_selected else ""}">'
                '<div class="lu-pick-top">'
                f'<div class="lu-pick-stat">{esc(display)}</div>'
                f'<span class="lu-roll-band band-{band.lower()}">{esc(band)}</span>'
                '</div>'
                f'<div class="lu-pick-roll">+{int(meta["Roll"])}</div>'
                f'<div class="lu-pick-range">range +{int(meta["Min"])}–+{int(meta["Max"])}</div>'
                + (
                    f'<div class="lu-pick-reason">{esc(reason)}</div>'
                    '<div class="lu-pick-badge">PICK</div>'
                    if is_selected else
                    '<div class="lu-pick-reason muted">not selected</div>'
                )
                + '</div>'
            )
        return '<div class="lu-pick-grid">' + "".join(cards) + '</div>'

    def outcomes(candidate: dict) -> str:
        fit_delta, fit_cls = _metric_delta(
            candidate["AnchorFitBeforePct"], candidate["AnchorFitAfterPct"]
        )
        feasibility_delta = (
            candidate["FitFeasibilityAfterPct"] - candidate["FitFeasibilityBeforePct"]
        )
        _, feas_cls = _metric_delta(
            candidate["FitFeasibilityBeforePct"], candidate["FitFeasibilityAfterPct"]
        )
        return (
            '<div class="lu-outcomes">'
            f'<div class="lu-outcome {fit_cls}"><small>EXPECTED FIT</small>'
            f'<strong>{candidate["AnchorFitBeforePct"]:.1f}% → {candidate["AnchorFitAfterPct"]:.1f}% '
            f'({fit_delta})</strong></div>'
            '<div class="lu-outcome flat" title="Likely range: 5th–95th percentile, containing roughly 90% of simulated outcomes."><small>LIKELY FIT RANGE</small>'
            f'<strong>{candidate["FitLikelyMinAfterPct"]:.1f}% – {candidate["FitLikelyMaxAfterPct"]:.1f}%</strong></div>'
            '<div class="lu-outcome flat" title="Full simulated range: explicit worst/best extremes. Endpoints can be very unlikely."><small>FULL FIT RANGE</small>'
            f'<strong>{candidate["FitMinAfterPct"]:.1f}% – {candidate["FitMaxAfterPct"]:.1f}%</strong></div>'
            f'<div class="lu-outcome {feas_cls}"><small>P(FIT ≥ 100%)</small>'
            f'<strong>{candidate["FitFeasibilityBeforePct"]:.0f}% → {candidate["FitFeasibilityAfterPct"]:.0f}% '
            f'({signed(feasibility_delta)})</strong></div>'
            '</div>'
        )

    skipped = advice.get("SkippedImportant", []) or []
    skipped_html = ""
    if skipped:
        skipped_html = (
            '<div class="lu-skip-note"><strong>Notable skips</strong><ul>'
            + ''.join(
                f'<li><b>{esc(row["Stat"])}</b>: {esc(row["Reason"])}</li>'
                for row in skipped
            )
            + '</ul></div>'
        )

    trajectory = trajectory_label or advice["AnchorRole"]
    variant = " colossus" if colossus else ""
    path_name = "Colossus path" if colossus else "Base path"

    runner_html = ""
    if alt:
        gamble = alt.get("Gamble") or {}
        gamble_badge = ''
        gamble_panel = ''
        if gamble.get("IsGamble"):
            gamble_badge = '<span class="lu-gamble-badge" title="Lower Expected Fit than Primary, but wins in some paired future-roll scenarios.">🎲 GAMBLE</span>'
            gamble_panel = (
                '<div class="lu-gamble-panel" title="Both choices are tested against the same future roll scenarios, so this measures the effect of the decision itself.">'
                f'<strong>{float(gamble.get("ChanceToBeatPrimaryPct", 0.0)):.1f}% chance to beat Primary</strong>'
                f'<span>avg upside when it wins +{float(gamble.get("AvgUpsideWhenWinsPct", 0.0)):.2f} Fit · max +{float(gamble.get("MaxUpsidePct", 0.0)):.2f}</span>'
                f'<span>expected difference {float(gamble.get("MeanDeltaPct", 0.0)):+.2f} Fit · {int(gamble.get("Samples", 0))} paired scenarios</span>'
                '</div>'
            )
        runner_html = (
            '<div class="lu-candidate lu-runner">'
            '<div class="lu-candidate-head">'
            '<div><small>RUNNER-UP</small><strong>Alternative line</strong></div>'
            f'{gamble_badge}<span class="lu-score">Expected Fit {alt["AnchorFitAfterPct"]:.1f}%</span>'
            '</div>'
            f'{roll_board(alt, runner_up=True)}'
            f'{gamble_panel}'
            f'{outcomes(alt)}'
            '</div>'
        )

    return (
        f'<section class="lu-trajectory{variant}">'
        '<div class="lu-trajectory-banner">'
        '<div>'
        f'<small>{esc(label)}</small>'
        f'<strong>{esc(path_name)}</strong>'
        '</div>'
        f'<span>Optimized for <b>{esc(trajectory)}</b></span>'
        '</div>'
        '<div class="lu-candidate lu-primary">'
        '<div class="lu-candidate-head">'
        '<div><small>PRIMARY</small><strong>Recommended line</strong></div>'
        f'<span class="lu-score">Expected Fit {rec["AnchorFitAfterPct"]:.1f}%</span>'
        '</div>'
        f'{roll_board(rec)}'
        f'{skipped_html}'
        f'{outcomes(rec)}'
        '</div>'
        f'{runner_html}'
        '</section>'
    )



def levelup_bro_panel(b, summary: dict, *, open_panel: bool = False) -> str:
    """Decision-focused card for one brother with a pending level-up."""
    advice = summary.get("LevelUpAdvice")
    if not getattr(b, "LevelPoints", 0) or not getattr(b, "CurrentRolls", None):
        return ""

    open_attr = " open" if open_panel else ""
    points = int(b.LevelPoints)
    structural_alts = summary.get("StructuralPerkAlternatives", [])
    structural_html = ''.join(
        '<span class="lu-structural-note">'
        f'{esc(alt["Label"])} → {esc(alt["Role"])}'
        '</span>'
        for alt in structural_alts
    )

    return (
        f'<details class="levelup-bro-panel"{open_attr}>'
        '<summary class="levelup-bro-head">'
        '<div class="lu-bro-identity">'
        f'<span class="lu-level-badge">L{b.Level}</span>'
        '<div>'
        f'<h3>{esc(b.Name)}</h3>'
        f'<p>{esc(b.Background)}</p>'
        '</div>'
        '</div>'
        '<div class="lu-role-chip">'
        '<small>BEST ROLE</small>'
        f'<strong>{esc(summary["BestRole"])}</strong>'
        f'{structural_html}'
        '</div>'
        '<div class="lu-head-metrics">'
        f'<span><small>Fit</small><b>{summary["ProjectedFitPct"]:.1f}%</b></span>'
        f'<span><small>P(Fit≥100)</small><b>{summary["FitFeasibilityPct"]:.1f}%</b></span>'
        '</div>'
        f'<span class="lu-pending">{points} pending</span>'
        '</summary>'
        '<div class="levelup-bro-body">'
        + levelup_advice_html(advice)
        + ''.join(
            levelup_advice_html(
                alt.get("LevelUpAdvice"),
                label=f'{alt["Label"].upper()} PATH',
                trajectory_label=alt["Role"],
                colossus=("Colossus" in alt["Perks"]),
            )
            for alt in structural_alts
            if alt.get("LevelUpAdvice")
        )
        + '</div>'
        '</details>'
    )


def archetype_detail_body_html(b, row: dict, role_cfg: dict | None, effective=None) -> str:
    """Shared rich archetype body for base and structural trajectories."""
    effective = effective or {}
    return (
        '<div class="role-detail-body">'
        f'{fit_measure_help_html(row)}'
        f'{target_profile_html(row)}'
        '<div class="detail-block"><h4>EFFECTIVE CURRENT STATS</h4>'
        f'<div class="stat-grid structural-stats">{current_stat_chips(b,effective,role_important_stats(role_cfg))}</div></div>'
        '<div class="detail-block development-focus-block"><h4>FIT DEVELOPMENT — LEVEL 11 <span>(optimized stat allocation)</span></h4>'
        f'{optimized_allocation_help_html()}'
        f'{development_focus_html(b,row,effective)}</div>'
        '<div class="projection-legend">'
        '<span class="legend-baseline">Baseline (minimum useful)</span>'
        '<span class="legend-target">Target (desired)</span>'
        '<span class="legend-expected">Expected (projection)</span>'
        '</div></div>'
    )


def structural_detail_html(b, alt: dict, roles: list[dict], class_cfg: dict) -> str:
    r=alt.get("BestRoleDetail")
    if not r: return ""
    role_cfg=next((role for role in roles if role["name"]==alt["Role"]),None)
    return (
        '<details class="role-card structural-detail-card retained-role"><summary>'
        '<div class="role-name">'
        f'<small class="role-path-label">{esc(alt["Label"].upper())}</small><span class="role-title-line"><span>{esc(alt["Role"])}</span><span class="class-badge {class_css(alt["Category"])}"><span class="class-icon">{class_icon(alt["Category"])}</span>{esc(alt["Category"])}</span></span></div>'
        '<div class="role-kpis">'
        f'<span class="kpi {heat(r["ProjectedFitPct"])} kpi-track">Fit <b>{r["ProjectedFitPct"]:.1f}%</b>{fit_uncertainty_track(r)}</span>'
        f'<span class="kpi">P(Fit≥100) <b>{r["FitFeasibilityPct"]:.1f}%</b></span>'
        f'{classification_ceiling_html(r, alt["Category"], class_cfg)}</div></summary>'
        f'{archetype_detail_body_html(b, r, role_cfg, alt.get("EffectiveStats"))}'
        '</details>'
    )
def render_html_report(save_path: Path, bros, fits, summaries, roles, class_cfg, generated_at="", recruits=None):
    recruits = recruits or []

    ids_by_name = {}
    for bro in bros:
        ids_by_name.setdefault(bro.Name, []).append(bro.BrotherID)

    def resolved_brother_id(row):
        brother_id = row.get("BrotherID")
        if brother_id is not None:
            return brother_id
        legacy_ids = ids_by_name.get(row.get("Name"), [])
        return legacy_ids[0] if len(legacy_ids) == 1 else None

    by_id = {}
    for r in fits:
        brother_id = resolved_brother_id(r)
        if brother_id is not None:
            by_id.setdefault(brother_id, []).append(r)

    sm = {
        brother_id: x
        for x in summaries
        for brother_id in [resolved_brother_id(x)]
        if brother_id is not None
    }
    role_names = [r["name"] for r in roles]
    order = {"Invest": 0, "Use": 1, "Fodder": 2, "Trash": 3}

    bros = sorted(
        bros,
        key=lambda b: (
            order.get(sm[b.BrotherID]["Category"], 9),
            -sm[b.BrotherID]["ProjectedFitPct"],
            b.Name,
        ),
    )

    class_rows, matrix_rows, details = [], [], []

    for b in bros:
        x = sm[b.BrotherID]

        paths = x.get("ClassificationPaths") or []
        selected = x.get("SelectedClassificationPath") or {}
        if not paths:
            paths = [{
                "Label": "Base",
                "Role": x.get("BestRole", ""),
                "Category": x.get("Category", ""),
                "ProjectedFitPct": x.get("ProjectedFitPct", 0.0),
                "ProjectedFitLikelyMinPct": x.get("ProjectedFitLikelyMinPct"),
                "ProjectedFitLikelyMaxPct": x.get("ProjectedFitLikelyMaxPct"),
                "ProjectedFitFullMinPct": x.get("ProjectedFitFullMinPct"),
                "ProjectedFitFullMaxPct": x.get("ProjectedFitFullMaxPct"),
                "FitFeasibilityPct": x.get("FitFeasibilityPct", 0.0),
            }]
        rowspan = len(paths)
        for path_index, path in enumerate(paths):
            is_selected = (
                path.get("Label", "Base") == selected.get("Label", "Base")
                and path.get("Role") == selected.get("Role")
                and path.get("Category") == selected.get("Category")
            )
            lead_cells = ""
            if path_index == 0:
                lead_cells = (
                    f'<td class="sticky strategic-brother" rowspan="{rowspan}"><a class="bro-link" href="#{bro_anchor(b.BrotherID)}">{esc(b.Name)}</a></td>'
                    f'<td class="strategy-bg" rowspan="{rowspan}">{esc(b.Background)}</td>'
                )
            class_rows.append(
                f'<tr class="strategic-path-tr{" selected-path-row" if is_selected else ""}" data-category="{esc(x["Category"])}">'
                f'{lead_cells}'
                f'<td class="strategy-paths">{classification_path_html(path)}</td>'
                f'<td class="strategy-metric strategy-fit-range">{classification_path_fit_range_html(path)}</td>'
                f'<td class="strategy-metric">{classification_path_metric_html(path, "FitFeasibilityPct")}</td>'
                '</tr>'
            )

        role_map = {r["Role"]: r for r in by_id[b.BrotherID]}
        cells = []
        for role in role_names:
            r = role_map[role]
            best = " best" if x["BestRole"] == role else ""
            cells.append(
                f'<td class="cell{best}">'
                f'<div class="m {heat(r["ProjectedFitPct"])}"><b>F</b><span>{r["ProjectedFitPct"]:.0f}</span></div>'
                f'<div class="m {heat(r["FitFeasibilityPct"])}"><b>P</b><span>{r["FitFeasibilityPct"]:.0f}</span></div>'
                +
                '</td>'
            )

        matrix_rows.append(
            f'<tr data-category="{esc(x["Category"])}">'
            f'<td class="sticky"><b>{esc(b.Name)}</b><br>'
            f'<small><span class="class-badge {class_css(x["Category"])}"><span class="class-icon">{class_icon(x["Category"])}</span>{esc(x["Category"])}</span> · L{b.Level}</small></td>'
            + ''.join(cells) + '</tr>'
        )

        role_cards = []
        base_effective_stats, _ = effective_stat_profile(b)
        sorted_roles = sorted(
            by_id[b.BrotherID],
            key=lambda z: (z["ProjectedFit"], z.get("FitFeasibilityPct",0.0), z.get("ProjectedFitLikelyMinPct",0.0)),
            reverse=True,
        )

        for r in sorted_roles:
            open_attr = ""
            role_category = classify_bro(r, class_cfg)[0]
            role_cards.append((
                float(r["ProjectedFitPct"]),
                f'<details class="role-card{" retained-role" if r["Role"] == x["BestRole"] else ""}"{open_attr}>'
                '<summary>'
                f'<div class="role-name"><span class="role-title-line"><span>{esc(r["Role"])}</span><span class="class-badge {class_css(role_category)}"><span class="class-icon">{class_icon(role_category)}</span>{esc(role_category)}</span></span></div>'
                f'<div class="role-kpis">'
                f'<span class="kpi {heat(r["ProjectedFitPct"])} kpi-track">Fit <b>{r["ProjectedFitPct"]:.1f}%</b>{fit_uncertainty_track(r)}</span>'
                f'<span class="kpi">P(Fit≥100) <b>{r["FitFeasibilityPct"]:.1f}%</b></span>'
                f'{classification_ceiling_html(r, role_category, class_cfg)}'
                '</div></summary>'
                f'{archetype_detail_body_html(b, r, next((role for role in roles if role["name"] == r["Role"]), None), base_effective_stats)}'
                '</details>'
            ))

        # Alternate structural trajectories are archetype projections too. Put
        # them in the same list and sort the whole set by Fit, regardless of path.
        for alt in x.get("StructuralPerkAlternatives", []):
            role_cards.append((
                float(alt["ProjectedFitPct"]),
                structural_detail_html(b, alt, roles, class_cfg),
            ))

        role_cards.sort(key=lambda item: item[0], reverse=True)
        rendered_cards = []
        for index, (_, card) in enumerate(role_cards):
            if index == 0:
                card = card.replace(
                    'class="role-card',
                    'class="role-card default-open',
                    1,
                )
            rendered_cards.append(card)
        rendered_role_cards = ''.join(rendered_cards)

        header_trajectories = [{
            "Label": "DEFAULT",
            "Role": x["BestRole"],
            "ProjectedFitPct": x["ProjectedFitPct"],
            "FitFeasibilityPct": x["FitFeasibilityPct"],
            "Current": True,
        }] + [
            {**alt, "Current": False}
            for alt in x.get("StructuralPerkAlternatives", [])
        ]
        header_trajectories.sort(
            key=lambda row: row["ProjectedFitPct"],
            reverse=True,
        )

        details.append(
            f'<details id="{bro_anchor(b.BrotherID)}" class="bro-card bro-panel" data-category="{esc(x["Category"])}">'
            '<summary class="bro-head">'
            '<div>'
            f'<h3>{esc(b.Name)} <span class="class-badge {class_css(x["Category"])}"><span class="class-icon">{class_icon(x["Category"])}</span>{esc(x["Category"])}</span></h3>'
            f'<div class="muted">{esc(b.Background)} · Level {b.Level}</div>'
            '</div>'
            '<div class="best-box">'
            + ''.join(
                f'<div class="bro-role-option {"current" if traj["Current"] else "alternate"}">'
                f'<small class="bro-role-path">{esc(traj["Label"].upper())}</small>'
                f'<strong>{esc(traj["Role"])}</strong>'
                '<div class="bro-role-metrics">'
                f'<span><small>FIT</small><b>{traj["ProjectedFitPct"]:.1f}%</b></span>'
                f'<span><small>P≥100</small><b>{traj["FitFeasibilityPct"]:.1f}%</b></span>'
                '</div>'
                '</div>'
                for traj in header_trajectories
            )
            + '</div>' 
            '</summary>'
            '<div class="bro-panel-body">'
            + '<div class="baseline-detail-block">'
            + '<div class="detail-section-label">CURRENT BROTHER DETAILS</div>'
            + f'<div class="stat-grid">{current_stat_chips(b, x.get("EffectiveStats"))}</div>'
            + '<div class="meta-grid">'
            f'<div><span>Perks</span><strong>{described_items(b.Perks)}</strong></div>'
            f'<div><span>Traits</span><strong>{described_items(b.Traits, exclude=b.Injuries)}</strong></div>'
            f'<div><span>Injuries</span><strong>{described_items(b.Injuries)}</strong></div>'
            + '</div>'
            + '</div>'
            + '<div class="roles">'
            + '<div class="detail-section-label">ARCHETYPE DETAILS</div>'
            + rendered_role_cards
            + '</div>'
            '</div>'
            '</details>'
        )

    headers = ''.join(f'<th>{esc(r)}</th>' for r in role_names)
    stamp = f' · generated {esc(generated_at)}' if generated_at else ''

    recruit_panels = recruit_settlement_panels(recruits)

    roster_tab = (
        '<section id="tab-roster" class="tab-panel active" data-tab-panel="roster">'
        + '<div class="bar"><button class="active" onclick="filterCategory(\'All\', this)">All</button>'
        + '<button onclick="filterCategory(\'Invest\', this)">💎 Invest</button>'
        + '<button onclick="filterCategory(\'Use\', this)">🛡️ Use</button>'
        + '<button onclick="filterCategory(\'Fodder\', this)">⚔️ Fodder</button>'
        + '<button onclick="filterCategory(\'Trash\', this)">☠️ Trash</button>'
        + ' <span class="muted">F↑=Expected Fit · P↑=P(Fit≥100%)</span></div>'
        + '<h2>Strategic Classification</h2><div class="tw strategic-table-wrap"><table class="strategic-table">'
        + '<colgroup><col class="col-brother"><col class="col-background"><col class="col-paths"><col class="col-fit-range"><col class="col-prob"></colgroup>'
        + '<thead><tr><th class="sticky">Brother</th><th>Background</th><th class="paths-head">Paths</th><th title="Expected Fit plus likely (P5–P95) and full simulated Fit ranges.">Fit / ranges</th><th title="Probability that simulated level-11 Fit reaches 100%.">P(Fit≥100)</th>'
        + '</tr></thead><tbody>' + ''.join(class_rows) + '</tbody></table></div>'
        + '<h2>Brother Details</h2>' + ''.join(details)
        + '</section>'
    )

    levelup_bros = [
        b for b in bros
        if getattr(b, "LevelPoints", 0) and getattr(b, "CurrentRolls", None)
    ]
    levelup_count = len(levelup_bros)
    levelup_panels = ''.join(
        levelup_bro_panel(
            b,
            sm[b.BrotherID],
            open_panel=False,
        )
        for b in levelup_bros
    )

    levelup_tab = (
        '<section id="tab-levelup" class="tab-panel" data-tab-panel="levelup">'
        + '<div class="tab-heading">'
        + '<div><h2>Level Up</h2>'
        + f'<p class="muted">{levelup_count} decision'
        + ('' if levelup_count == 1 else 's')
        + ' waiting · recommendation first, rolls second</p></div>'
        + '</div>'
        + (
            levelup_panels
            if levelup_panels
            else '<div class="empty-state">No level-ups are currently available.</div>'
        )
        + '</section>'
    )

    roster_management_tab = (
        '<section id="tab-management" class="tab-panel" data-tab-panel="management">'
        + '<div class="tab-heading">'
        + '<div><h2>Roster Management</h2>'
        + '<p class="muted">Brother × Archetype overview · static comparison</p></div>'
        + '</div>'
        + '<div class="tw matrix"><table><thead><tr><th class="sticky">Brother</th>'
        + headers + '</tr></thead><tbody>' + ''.join(matrix_rows) + '</tbody></table></div>'
        + '</section>'
    )

    recruits_tab = (
        '<section id="tab-recruits" class="tab-panel" data-tab-panel="recruits">'
        + '<div class="tab-heading">'
        + '<div><h2>Recruitment Candidates</h2>'
        + f'<p class="muted">{len(recruits)} candidates · public information only</p></div>'
        + '</div>'
        + (
            recruit_panels
            if recruit_panels
            else '<div class="empty-state">No recruitment candidates detected.</div>'
        )
        + '<p class="hint">Only recruitment-screen information is shown here. Hidden stats, talent stars and analytical scores are intentionally excluded.</p>'
        + '</section>'
    )

    html_doc = (
        '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>{esc(save_path.stem)} roster</title><link rel="stylesheet" href="report.css"></head>'
        '<body><div class="wrap">'
        f'<h1>{esc(save_path.stem)} — Battle Brothers Report</h1>'
        f'<p class="muted">{len(bros)} brothers · {len(recruits)} recruits · read-only{stamp}</p>'
        '<nav class="tabs" aria-label="Report sections">'
        f'<button class="tab-button active" data-tab-button="roster" onclick="showTab(\'roster\', this)">Roster <span class="tab-count">{len(bros)}</span></button>'
        + (
            f'<button class="tab-button levelup-tab-button has-levelups" data-tab-button="levelup" '
            f'onclick="showTab(\'levelup\', this)">Level Up <span class="tab-count">{levelup_count}</span></button>'
            if levelup_count
            else '<button class="tab-button levelup-tab-button" data-tab-button="levelup" disabled '
                 'aria-disabled="true">Level Up <span class="tab-count">0</span></button>'
        )
        + f'<button class="tab-button" data-tab-button="management" onclick="showTab(\'management\', this)">Roster Management <span class="tab-count">{len(bros)}</span></button>'
        + f'<button class="tab-button" data-tab-button="recruits" onclick="showTab(\'recruits\', this)">Recruits <span class="tab-count">{len(recruits)}</span></button>'
        + '</nav>'
        + roster_tab
        + levelup_tab
        + roster_management_tab
        + recruits_tab
        + '</div><script src="report.js"></script></body></html>'
    )
    return pretty_html(html_doc)
