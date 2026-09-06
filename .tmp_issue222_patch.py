from pathlib import Path


def replace_once(path, old, new):
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"expected patch block not found in {path}: {old[:120]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


# Backend-owned candidate-level availability and truthful Relevant Need reasons.
path = "bbtool/app/recruitment_view.py"
replace_once(
    path,
    '''    return {
        "build_identity": build_identity,
        "role": build_names.get(build_identity, build_identity),
        "state": state,
        "background_prior_pct": prior,
        "candidate_estimate_pct": estimate,
        "evidence": sorted(set(evidence)),
    }


def _top_potential(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
''',
    '''    return {
        "build_identity": build_identity,
        "role": build_names.get(build_identity, build_identity),
        "state": state,
        "reason": analysis.get("reason"),
        "background_prior_pct": prior,
        "candidate_estimate_pct": estimate,
        "evidence": sorted(set(evidence)),
    }


def _potential_availability(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Collapse only a coherent candidate-wide unavailable analytical layer."""
    if not rows:
        return {"state": "unavailable", "reason": "candidate_potential_unavailable"}
    unavailable = [row for row in rows if row.get("state") == "unavailable"]
    if len(unavailable) == len(rows):
        reasons = sorted({
            row.get("reason") for row in unavailable
            if isinstance(row.get("reason"), str) and row.get("reason")
        })
        return {
            "state": "unavailable",
            "reason": reasons[0] if len(reasons) == 1 else "candidate_potential_unavailable",
        }
    if unavailable:
        return {
            "state": "partial",
            "reason": "candidate_potential_partially_unavailable",
        }
    return {"state": "available", "reason": None}


def _top_potential(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
''',
)

old_need = '''def _unavailable_need() -> dict[str, Any]:
    return {
        "state": "unavailable",
        "relevant": None,
        "matches": [],
        "other_company_gaps": [],
    }


def _relevant_need(value: Any, build_names: Mapping[str, str]) -> dict[str, Any]:
    if not isinstance(value, Mapping) or value.get("state") != "available":
        return _unavailable_need()
    result = value.get("result")
    if not isinstance(result, Mapping):
        return _unavailable_need()
    matches = [
        row
        for row in (
            _need_row(item, build_names)
            for item in result.get("relevant_need_matches") or []
        )
        if row is not None
    ]
    others = [
        row
        for row in (
            _need_row(item, build_names)
            for item in result.get("other_company_gaps") or []
        )
        if row is not None
    ]
    return {
        "state": "available",
        "relevant": _need_row(result.get("relevant_need"), build_names),
        "matches": matches,
        "other_company_gaps": others,
    }
'''
new_need = '''def _unavailable_need(reason: str, *, upstream_reason: str | None = None) -> dict[str, Any]:
    return {
        "state": "unavailable",
        "reason": reason,
        "upstream_reason": upstream_reason,
        "relevant": None,
        "matches": [],
        "other_company_gaps": [],
    }


def _relevant_need(
    value: Any,
    build_names: Mapping[str, str],
    *,
    potential_availability: Mapping[str, Any],
    company_intent_available: bool,
) -> dict[str, Any]:
    if not isinstance(value, Mapping) or value.get("state") != "available":
        potential_state = potential_availability.get("state")
        upstream_reason = potential_availability.get("reason")
        if not company_intent_available and potential_state != "available":
            return _unavailable_need(
                "candidate_potential_and_company_intent_unavailable",
                upstream_reason=upstream_reason if isinstance(upstream_reason, str) else None,
            )
        if not company_intent_available:
            return _unavailable_need("company_intent_coverage_unavailable")
        if potential_state == "unavailable":
            return _unavailable_need(
                "candidate_potential_unavailable",
                upstream_reason=upstream_reason if isinstance(upstream_reason, str) else None,
            )
        if potential_state == "partial":
            return _unavailable_need(
                "candidate_potential_incomplete",
                upstream_reason=upstream_reason if isinstance(upstream_reason, str) else None,
            )
        return _unavailable_need("relevant_need_unavailable")
    result = value.get("result")
    if not isinstance(result, Mapping):
        return _unavailable_need("relevant_need_result_unavailable")
    matches = [
        row
        for row in (
            _need_row(item, build_names)
            for item in result.get("relevant_need_matches") or []
        )
        if row is not None
    ]
    others = [
        row
        for row in (
            _need_row(item, build_names)
            for item in result.get("other_company_gaps") or []
        )
        if row is not None
    ]
    return {
        "state": "available",
        "reason": None,
        "upstream_reason": None,
        "relevant": _need_row(result.get("relevant_need"), build_names),
        "matches": matches,
        "other_company_gaps": others,
    }
'''
replace_once(path, old_need, new_need)
replace_once(
    path,
    '''        need_by_index = {
            row.get("recruit_index"): row
            for row in presentation.get("relevant_roster_need", [])
            if isinstance(row, Mapping)
        }
        candidates = []
''',
    '''        need_by_index = {
            row.get("recruit_index"): row
            for row in presentation.get("relevant_roster_need", [])
            if isinstance(row, Mapping)
        }
        company = presentation.get("company")
        company_intent_available = (
            isinstance(company, Mapping) and company.get("intent_available") is True
        )
        candidates = []
''',
)
replace_once(
    path,
    '''            candidates.append({
                "recruit_index": index,
                "facts": facts,
                "top_potential": _top_potential(potentials),
                "potential": potentials,
                "relevant_need": _relevant_need(need_by_index.get(index), builds),
            })
''',
    '''            potential_availability = _potential_availability(potentials)
            candidates.append({
                "recruit_index": index,
                "facts": facts,
                "top_potential": _top_potential(potentials),
                "potential_availability": potential_availability,
                "potential": potentials,
                "relevant_need": _relevant_need(
                    need_by_index.get(index),
                    builds,
                    potential_availability=potential_availability,
                    company_intent_available=company_intent_available,
                ),
            })
''',
)

# Shared UI percentage formatting must preserve null/unavailable evidence.
replace_once(
    "bbtool/app/static/app.js",
    '''function formatPct(value, fallback = '—') {
  const number = Number(value);
  return Number.isFinite(number) ? `${number.toFixed(1)}%` : fallback;
}
''',
    '''function formatPct(value, fallback = '—') {
  if (value === null || value === undefined || value === '') return fallback;
  const number = Number(value);
  return Number.isFinite(number) ? `${number.toFixed(1)}%` : fallback;
}
''',
)

# Recruitment presentation consumes only backend-owned state/reason fields.
path = "bbtool/app/static/recruitment.js"
replace_once(
    path,
    '''  function potentialLabel(top) {
    if (!top) return 'Unavailable';
    return `${top.role || 'Unknown role'} · ${formatPct(top.score_pct)}`;
  }

  function needLabel(candidate) {
''',
    '''  function potentialLabel(top) {
    if (!top) return 'Unavailable';
    return `${top.role || 'Unknown role'} · ${formatPct(top.score_pct)}`;
  }

  function potentialUnavailableMessage(candidate) {
    const reason = candidate?.potential_availability?.reason;
    const messages = {
      background_archetype_prior_disabled_pending_validation: 'Unavailable — the Background × Archetype model is disabled pending validation.',
      background_identity_unavailable: 'Unavailable — candidate background identity is unavailable.',
      build_identity_unavailable: 'Unavailable — build identity is unavailable.',
      candidate_potential_unavailable: 'Unavailable — candidate-potential analysis is unavailable.',
    };
    return messages[reason] || 'Unavailable — candidate-potential analysis is unavailable.';
  }

  function relevantNeedUnavailableMessage(candidate) {
    const need = candidate?.relevant_need || {};
    if (need.reason === 'candidate_potential_unavailable') {
      if (need.upstream_reason === 'background_archetype_prior_disabled_pending_validation') {
        return 'Relevant Need is unavailable because candidate potential is disabled pending validation.';
      }
      return 'Relevant Need is unavailable because candidate-potential evidence is unavailable.';
    }
    if (need.reason === 'candidate_potential_incomplete') {
      return 'Relevant Need is unavailable because candidate-potential evidence is incomplete.';
    }
    if (need.reason === 'company_intent_coverage_unavailable') {
      return 'Relevant Need is unavailable because intent-aware Company coverage is unavailable.';
    }
    if (need.reason === 'candidate_potential_and_company_intent_unavailable') {
      return 'Relevant Need is unavailable because candidate potential and intent-aware Company coverage are unavailable.';
    }
    return 'Relevant Need is unavailable from the current analytical evidence.';
  }

  function mobileCandidateLabel(settlement, candidate) {
    const facts = candidate?.facts || {};
    const name = facts.Name || `Candidate ${candidate.recruit_index + 1}`;
    const context = candidate?.potential_availability?.state === 'unavailable'
      ? (facts.Background || 'Unknown background')
      : potentialLabel(candidate.top_potential);
    return `${settlement} · ${name} · ${context} · ${money(facts.HireCost)}`;
  }

  function needLabel(candidate) {
''',
)
replace_once(
    path,
    '''  function evidenceLabel(candidate) {
    const names = evidenceNames(candidate);
    if (names.length) return names.join(', ');
    const known = (candidate?.potential || []).some((row) => row.state === 'known_evidence_estimate');
    return known ? 'Known evidence applied' : 'Prior-only evidence';
  }
''',
    '''  function evidenceLabel(candidate) {
    if (candidate?.potential_availability?.state === 'unavailable') return 'Analysis unavailable';
    const names = evidenceNames(candidate);
    if (names.length) return names.join(', ');
    const potential = candidate?.potential || [];
    if (potential.some((row) => row.state === 'known_evidence_estimate')) return 'Known evidence applied';
    if (potential.some((row) => row.state === 'prior_only')) return 'Prior-only evidence';
    if (candidate?.potential_availability?.state === 'partial') return 'Analysis partially unavailable';
    return 'Analysis unavailable';
  }
''',
)
replace_once(
    path,
    '''        const option = node('option', '', `${settlement.settlement} · ${facts.Name || `Candidate ${candidate.recruit_index + 1}`} · ${potentialLabel(candidate.top_potential)} · ${money(facts.HireCost)}`);
''',
    '''        const option = node('option', '', mobileCandidateLabel(settlement.settlement, candidate));
''',
)
replace_once(
    path,
    '''  function renderPotential(candidate) {
    const host = document.getElementById('recruit-potential');
    clear(host);
    const topIdentity = candidate.top_potential?.build_identity;
''',
    '''  function renderPotential(candidate) {
    const host = document.getElementById('recruit-potential');
    clear(host);
    if (candidate?.potential_availability?.state === 'unavailable') {
      host.append(node('p', 'subtle', potentialUnavailableMessage(candidate)));
      return;
    }
    const topIdentity = candidate.top_potential?.build_identity;
''',
)
replace_once(
    path,
    '''    if (need.state !== 'available') {
      host.append(node('p', 'subtle', 'Relevant Need is unavailable until intent-aware Company coverage is available.'));
      return;
    }
''',
    '''    if (need.state !== 'available') {
      host.append(node('p', 'subtle', relevantNeedUnavailableMessage(candidate)));
      return;
    }
''',
)

# Backend/read-model regressions.
path = "tests/unit/test_recruitment_ui.py"
replace_once(path, "def _application(monkeypatch):\n", "def _application(monkeypatch, presentation_mutator=None):\n")
replace_once(
    path,
    '''    presentation = {
        "builds": [
''',
    '''    presentation = {
        "company": {"intent_available": True},
        "builds": [
''',
)
replace_once(
    path,
    '''    monkeypatch.setattr(recruitment_view, "build_target_presentation", lambda **_kwargs: presentation)
''',
    '''    if presentation_mutator is not None:
        presentation_mutator(presentation)
    monkeypatch.setattr(recruitment_view, "build_target_presentation", lambda **_kwargs: presentation)
''',
)
replace_once(
    path,
    '''    assert all(row["candidate_estimate_pct"] is None for row in horic["potential"])
''',
    '''    assert horic["potential_availability"] == {"state": "available", "reason": None}
    assert all(row["candidate_estimate_pct"] is None for row in horic["potential"])
''',
)
append = r'''


def _unavailable_analysis(build_identity, reason="background_archetype_prior_disabled_pending_validation"):
    return {
        "build_identity": build_identity,
        "state": "unavailable",
        "reason": reason,
        "result": None,
    }


def test_recruitment_compacts_uniform_unavailability_and_preserves_backend_reason(monkeypatch):
    def mutate(presentation):
        presentation["recruitment"][0]["analyses"] = [
            _unavailable_analysis("bf_tank"),
            _unavailable_analysis("reach_dps"),
            _unavailable_analysis("banner"),
        ]
        presentation["relevant_roster_need"][0] = {
            "recruit_index": 0,
            "state": "unavailable",
            "result": None,
        }

    api = LocalApplicationApi(
        _application(monkeypatch, presentation_mutator=mutate),
        origin=ORIGIN,
        token="capability",
    )
    payload = decode(api.handle("GET", "/api/v1/recruitment", {"Host": HOST}))["data"]
    candidate = payload["settlements"][0]["candidates"][0]

    assert candidate["top_potential"] is None
    assert candidate["potential_availability"] == {
        "state": "unavailable",
        "reason": "background_archetype_prior_disabled_pending_validation",
    }
    assert {row["reason"] for row in candidate["potential"]} == {
        "background_archetype_prior_disabled_pending_validation"
    }
    assert candidate["relevant_need"] == {
        "state": "unavailable",
        "reason": "candidate_potential_unavailable",
        "upstream_reason": "background_archetype_prior_disabled_pending_validation",
        "relevant": None,
        "matches": [],
        "other_company_gaps": [],
    }


def test_recruitment_distinguishes_company_coverage_unavailability(monkeypatch):
    def mutate(presentation):
        presentation["company"]["intent_available"] = False
        presentation["relevant_roster_need"][0] = {
            "recruit_index": 0,
            "state": "unavailable",
            "result": None,
        }

    api = LocalApplicationApi(
        _application(monkeypatch, presentation_mutator=mutate),
        origin=ORIGIN,
        token="capability",
    )
    payload = decode(api.handle("GET", "/api/v1/recruitment", {"Host": HOST}))["data"]
    candidate = payload["settlements"][0]["candidates"][0]

    assert candidate["potential_availability"]["state"] == "available"
    assert candidate["relevant_need"]["reason"] == "company_intent_coverage_unavailable"
    assert candidate["relevant_need"]["upstream_reason"] is None


def test_recruitment_preserves_partial_per_build_evidence(monkeypatch):
    def mutate(presentation):
        presentation["recruitment"][0]["analyses"][1] = _unavailable_analysis(
            "reach_dps", reason="background_identity_unavailable"
        )
        presentation["relevant_roster_need"][0] = {
            "recruit_index": 0,
            "state": "unavailable",
            "result": None,
        }

    api = LocalApplicationApi(
        _application(monkeypatch, presentation_mutator=mutate),
        origin=ORIGIN,
        token="capability",
    )
    payload = decode(api.handle("GET", "/api/v1/recruitment", {"Host": HOST}))["data"]
    candidate = payload["settlements"][0]["candidates"][0]

    assert candidate["potential_availability"] == {
        "state": "partial",
        "reason": "candidate_potential_partially_unavailable",
    }
    assert len(candidate["potential"]) == 3
    assert next(row for row in candidate["potential"] if row["role"] == "Reach DPS")["reason"] == "background_identity_unavailable"
    assert candidate["top_potential"]["role"] == "BF Tank"
    assert candidate["relevant_need"]["reason"] == "candidate_potential_incomplete"
'''
Path(path).write_text(Path(path).read_text(encoding="utf-8") + append, encoding="utf-8")
replace_once(
    path,
    '''    js = (ROOT / "bbtool" / "app" / "static" / "recruitment.js").read_text(encoding="utf-8")
    css = (ROOT / "bbtool" / "app" / "static" / "recruitment.css").read_text(encoding="utf-8")
''',
    '''    js = (ROOT / "bbtool" / "app" / "static" / "recruitment.js").read_text(encoding="utf-8")
    app_js = (ROOT / "bbtool" / "app" / "static" / "app.js").read_text(encoding="utf-8")
    css = (ROOT / "bbtool" / "app" / "static" / "recruitment.css").read_text(encoding="utf-8")
''',
)
replace_once(
    path,
    '''    assert "top_potential" in js
    assert "innerHTML" not in js
''',
    '''    assert "top_potential" in js
    assert "potential_availability" in js
    assert "candidate_potential_unavailable" in js
    assert "candidate_potential_incomplete" in js
    assert "value === null || value === undefined || value === ''" in app_js
    assert "innerHTML" not in js
''',
)

# Browser fixtures + regressions for compact unavailable and partial evidence.
path = "tests/ui/test_recruitment_browser.py"
replace_once(
    path,
    '''        "top_potential": {
            "build_identity": "bf_tank",
            "role": "BF Tank",
            "state": state,
            "background_prior_pct": score - 4.0,
            "candidate_estimate_pct": estimate,
            "score_pct": score if tryout else score - 4.0,
        },
        "potential": [
''',
    '''        "top_potential": {
            "build_identity": "bf_tank",
            "role": "BF Tank",
            "state": state,
            "background_prior_pct": score - 4.0,
            "candidate_estimate_pct": estimate,
            "score_pct": score if tryout else score - 4.0,
        },
        "potential_availability": {"state": "available", "reason": None},
        "potential": [
''',
)
replace_once(
    path,
    '''        "relevant_need": {
            "state": "available",
            "relevant": need,
''',
    '''        "relevant_need": {
            "state": "available",
            "reason": None,
            "upstream_reason": None,
            "relevant": need,
''',
)
replace_once(
    path,
    '''function formatPct(value, fallback = '—') {{
  const number = Number(value);
  return Number.isFinite(number) ? `${{number.toFixed(1)}}%` : fallback;
}}
''',
    '''function formatPct(value, fallback = '—') {{
  if (value === null || value === undefined || value === '') return fallback;
  const number = Number(value);
  return Number.isFinite(number) ? `${{number.toFixed(1)}}%` : fallback;
}}
''',
)
append = r'''


def _unavailable_publication(job_id=303):
    payload = _publication(job_id, "Unavailable")
    for settlement in payload["settlements"]:
        for candidate in settlement["candidates"]:
            candidate["top_potential"] = None
            candidate["potential_availability"] = {
                "state": "unavailable",
                "reason": "background_archetype_prior_disabled_pending_validation",
            }
            candidate["potential"] = [
                {
                    "build_identity": "bf_tank",
                    "role": "BF Tank",
                    "state": "unavailable",
                    "reason": "background_archetype_prior_disabled_pending_validation",
                    "background_prior_pct": None,
                    "candidate_estimate_pct": None,
                    "evidence": [],
                },
                {
                    "build_identity": "reach_dps",
                    "role": "Reach DPS",
                    "state": "unavailable",
                    "reason": "background_archetype_prior_disabled_pending_validation",
                    "background_prior_pct": None,
                    "candidate_estimate_pct": None,
                    "evidence": [],
                },
            ]
            candidate["relevant_need"] = {
                "state": "unavailable",
                "reason": "candidate_potential_unavailable",
                "upstream_reason": "background_archetype_prior_disabled_pending_validation",
                "relevant": None,
                "matches": [],
                "other_company_gaps": [],
            }
    first = payload["settlements"][0]["candidates"]
    first[0]["facts"]["Name"] = "Ludolf"
    first[0]["facts"]["Background"] = "Poacher"
    first[1]["facts"]["Name"] = "Ludolf"
    first[1]["facts"]["Background"] = "Hunter"
    return payload


def _partial_publication(job_id=404):
    payload = _publication(job_id, "Partial")
    candidate = payload["settlements"][0]["candidates"][0]
    candidate["top_potential"] = {
        "build_identity": "bf_tank",
        "role": "BF Tank",
        "state": "prior_only",
        "background_prior_pct": 61.0,
        "candidate_estimate_pct": None,
        "score_pct": 61.0,
    }
    candidate["potential_availability"] = {
        "state": "partial",
        "reason": "candidate_potential_partially_unavailable",
    }
    candidate["potential"] = [
        {
            "build_identity": "bf_tank",
            "role": "BF Tank",
            "state": "prior_only",
            "reason": None,
            "background_prior_pct": 61.0,
            "candidate_estimate_pct": None,
            "evidence": [],
        },
        {
            "build_identity": "reach_dps",
            "role": "Reach DPS",
            "state": "unavailable",
            "reason": "background_identity_unavailable",
            "background_prior_pct": None,
            "candidate_estimate_pct": None,
            "evidence": [],
        },
    ]
    candidate["relevant_need"] = {
        "state": "unavailable",
        "reason": "candidate_potential_incomplete",
        "upstream_reason": "candidate_potential_partially_unavailable",
        "relevant": None,
        "matches": [],
        "other_company_gaps": [],
    }
    return payload


def test_globally_unavailable_candidate_potential_is_compact_truthful_and_mobile_useful(browser, surface_server):
    server, base_url = surface_server
    _load_surface(browser, server, base_url, _unavailable_publication(), width=390)

    option_texts = browser.execute_script(
        "return [...document.getElementById('recruit-mobile-select').options].slice(0, 2).map((item) => item.textContent)"
    )
    assert "Poacher" in option_texts[0]
    assert "Hunter" in option_texts[1]
    assert all("Unavailable" not in text for text in option_texts)

    assert browser.execute_script(
        "return document.querySelectorAll('#recruit-potential .recruit-potential-row').length"
    ) == 0
    potential_text = browser.execute_script(
        "return document.getElementById('recruit-potential').textContent"
    )
    assert "Background × Archetype model is disabled pending validation" in potential_text
    assert "0.0%" not in potential_text

    evidence_text = browser.execute_script(
        "return document.getElementById('recruit-evidence').textContent"
    )
    assert "Analysis unavailable" in evidence_text
    assert "Prior-only evidence" not in evidence_text
    need_text = browser.execute_script(
        "return document.getElementById('recruit-needs').textContent"
    )
    assert "candidate potential is disabled pending validation" in need_text
    assert "Company coverage" not in need_text
    assert browser.execute_script(
        "return document.getElementById('recruit-hire-cost').textContent"
    ) == "300g"

    browser.execute_script("document.getElementById('recruit-shortlist-current').click()")
    WebDriverWait(browser, 5).until(
        lambda current: current.execute_script(
            "return document.querySelectorAll('.recruit-shortlist-chip').length"
        ) == 1
    )
    _assert_no_js_errors(browser)


def test_partial_candidate_potential_keeps_per_build_rows_and_null_percent_unknown(browser, surface_server):
    server, base_url = surface_server
    _load_surface(browser, server, base_url, _partial_publication())

    assert browser.execute_script(
        "return document.querySelectorAll('#recruit-potential .recruit-potential-row').length"
    ) == 2
    potential_text = browser.execute_script(
        "return document.getElementById('recruit-potential').textContent"
    )
    assert "61.0%" in potential_text
    assert "Unavailable" in potential_text
    assert "0.0%" not in potential_text
    assert "—" in potential_text
    need_text = browser.execute_script(
        "return document.getElementById('recruit-needs').textContent"
    )
    assert "candidate-potential evidence is incomplete" in need_text
    _assert_no_js_errors(browser)
'''
Path(path).write_text(Path(path).read_text(encoding="utf-8") + append, encoding="utf-8")

# Document the additive read-model contract and machine reasons.
path = "docs/LOCAL_APPLICATION_API.md"
replace_once(
    path,
    '''| GET | `/api/v1/company-brother` | Company + Brother read model from the latest publication plus current AssignedBuild intent |
| GET | `/api/v1/followed-save` | Inspect selected-save preference and availability |
''',
    '''| GET | `/api/v1/company-brother` | Company + Brother read model from the latest publication plus current AssignedBuild intent |
| GET | `/api/v1/recruitment` | Recruitment read model with factual candidate/economics data plus bounded analytical availability/reasons |
| GET | `/api/v1/followed-save` | Inspect selected-save preference and availability |
''',
)
replace_once(
    path,
    '''Analysis handlers never execute parsing or projection. The application reads
''',
    '''`GET /api/v1/recruitment` keeps factual recruit identity/economics separate from
analytical availability. Each candidate retains raw build-indexed `potential` rows
for partial/future evidence and also publishes `potential_availability` as
`available`, `partial`, or `unavailable` with a bounded backend reason. Uniform
unavailability may therefore be rendered once at candidate level without the
frontend inferring semantics from repeated display rows. `relevant_need` publishes
its own bounded reason (`candidate_potential_unavailable`,
`candidate_potential_incomplete`, `company_intent_coverage_unavailable`, or the
combined/fallback states) and may preserve the upstream candidate-potential reason.
Nullable analytical percentages remain unavailable values rather than numeric zero.

Analysis handlers never execute parsing or projection. The application reads
''',
)

print("issue 222 patch applied")
