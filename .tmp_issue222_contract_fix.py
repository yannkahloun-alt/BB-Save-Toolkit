from pathlib import Path


def replace_once(path, old, new):
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"expected block not found in {path}: {old[:160]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


path = "bbtool/app/recruitment_view.py"
old = '''def _unavailable_need(reason: str, *, upstream_reason: str | None = None) -> dict[str, Any]:
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
new = '''def _unavailable_need() -> dict[str, Any]:
    return {
        "state": "unavailable",
        "relevant": None,
        "matches": [],
        "other_company_gaps": [],
    }


def _relevant_need(value: Any, build_names: Mapping[str, str]) -> dict[str, Any]:
    """Project the Target-owned Relevant Need state without re-inferring it."""
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


def _relevant_need_availability(
    value: Any,
    *,
    potential_availability: Mapping[str, Any],
    company_intent_available: bool | None,
) -> dict[str, Any]:
    """Explain an unavailable Target state without changing that state."""
    if isinstance(value, Mapping) and value.get("state") == "available":
        return {"state": "available", "reason": None, "upstream_reason": None}

    potential_state = potential_availability.get("state")
    upstream_reason = potential_availability.get("reason")
    upstream = upstream_reason if isinstance(upstream_reason, str) else None
    company_unavailable = company_intent_available is False

    if company_unavailable and potential_state != "available":
        reason = "candidate_potential_and_company_intent_unavailable"
    elif company_unavailable:
        reason = "company_intent_coverage_unavailable"
    elif potential_state == "unavailable":
        reason = "candidate_potential_unavailable"
    elif potential_state == "partial":
        reason = "candidate_potential_incomplete"
    else:
        reason = "relevant_need_unavailable"
    return {"state": "unavailable", "reason": reason, "upstream_reason": upstream}
'''
replace_once(path, old, new)
replace_once(
    path,
    '''        company = presentation.get("company")
        company_intent_available = (
            isinstance(company, Mapping) and company.get("intent_available") is True
        )
''',
    '''        company = presentation.get("company")
        company_intent_available = None
        if isinstance(company, Mapping) and isinstance(company.get("intent_available"), bool):
            company_intent_available = company["intent_available"]
''',
)
replace_once(
    path,
    '''                "relevant_need": _relevant_need(
                    need_by_index.get(index),
                    builds,
                    potential_availability=potential_availability,
                    company_intent_available=company_intent_available,
                ),
''',
    '''                "relevant_need": _relevant_need(need_by_index.get(index), builds),
                "relevant_need_availability": _relevant_need_availability(
                    need_by_index.get(index),
                    potential_availability=potential_availability,
                    company_intent_available=company_intent_available,
                ),
''',
)

# Frontend copy reads additive diagnostic metadata, never reinterprets Target state.
path = "bbtool/app/static/recruitment.js"
replace_once(
    path,
    '''  function relevantNeedUnavailableMessage(candidate) {
    const need = candidate?.relevant_need || {};
    if (need.reason === 'candidate_potential_unavailable') {
      if (need.upstream_reason === 'background_archetype_prior_disabled_pending_validation') {
''',
    '''  function relevantNeedUnavailableMessage(candidate) {
    const availability = candidate?.relevant_need_availability || {};
    if (availability.reason === 'candidate_potential_unavailable') {
      if (availability.upstream_reason === 'background_archetype_prior_disabled_pending_validation') {
''',
)
replace_once(path, "    if (need.reason === 'candidate_potential_incomplete') {", "    if (availability.reason === 'candidate_potential_incomplete') {")
replace_once(path, "    if (need.reason === 'company_intent_coverage_unavailable') {", "    if (availability.reason === 'company_intent_coverage_unavailable') {")
replace_once(path, "    if (need.reason === 'candidate_potential_and_company_intent_unavailable') {", "    if (availability.reason === 'candidate_potential_and_company_intent_unavailable') {")

# New #222 unit tests assert legacy Relevant Need shape plus sibling diagnostics.
path = "tests/unit/test_recruitment_ui.py"
replace_once(
    path,
    '''    assert candidate["relevant_need"] == {
        "state": "unavailable",
        "reason": "candidate_potential_unavailable",
        "upstream_reason": "background_archetype_prior_disabled_pending_validation",
        "relevant": None,
        "matches": [],
        "other_company_gaps": [],
    }
''',
    '''    assert candidate["relevant_need"] == {
        "state": "unavailable",
        "relevant": None,
        "matches": [],
        "other_company_gaps": [],
    }
    assert candidate["relevant_need_availability"] == {
        "state": "unavailable",
        "reason": "candidate_potential_unavailable",
        "upstream_reason": "background_archetype_prior_disabled_pending_validation",
    }
''',
)
replace_once(
    path,
    '''    assert candidate["potential_availability"]["state"] == "available"
    assert candidate["relevant_need"]["reason"] == "company_intent_coverage_unavailable"
    assert candidate["relevant_need"]["upstream_reason"] is None
''',
    '''    assert candidate["potential_availability"]["state"] == "available"
    assert candidate["relevant_need"]["state"] == "unavailable"
    assert candidate["relevant_need_availability"] == {
        "state": "unavailable",
        "reason": "company_intent_coverage_unavailable",
        "upstream_reason": None,
    }
''',
)
replace_once(
    path,
    '''    assert candidate["top_potential"]["role"] == "BF Tank"
    assert candidate["relevant_need"]["reason"] == "candidate_potential_incomplete"
''',
    '''    assert candidate["top_potential"]["role"] == "BF Tank"
    assert candidate["relevant_need"]["state"] == "unavailable"
    assert candidate["relevant_need_availability"] == {
        "state": "unavailable",
        "reason": "candidate_potential_incomplete",
        "upstream_reason": "candidate_potential_partially_unavailable",
    }
''',
)
replace_once(
    path,
    '''    assert "candidate_potential_incomplete" in js
''',
    '''    assert "candidate_potential_incomplete" in js
    assert "relevant_need_availability" in js
''',
)

# Browser fixtures preserve the old need object and carry reasons in sibling metadata.
path = "tests/ui/test_recruitment_browser.py"
text = Path(path).read_text(encoding="utf-8")
text = text.replace(
    '''        "relevant_need": {
            "state": "available",
            "reason": None,
            "upstream_reason": None,
            "relevant": need,
''',
    '''        "relevant_need": {
            "state": "available",
            "relevant": need,
''',
)
# Add available sibling immediately after each candidate's relevant_need block by targeting stable tail.
text = text.replace(
    '''            "other_company_gaps": [],
        },
    }
''',
    '''            "other_company_gaps": [],
        },
        "relevant_need_availability": {"state": "available", "reason": None, "upstream_reason": None},
    }
''',
    1,
)
text = text.replace(
    '''            candidate["relevant_need"] = {
                "state": "unavailable",
                "reason": "candidate_potential_unavailable",
                "upstream_reason": "background_archetype_prior_disabled_pending_validation",
                "relevant": None,
                "matches": [],
                "other_company_gaps": [],
            }
''',
    '''            candidate["relevant_need"] = {
                "state": "unavailable",
                "relevant": None,
                "matches": [],
                "other_company_gaps": [],
            }
            candidate["relevant_need_availability"] = {
                "state": "unavailable",
                "reason": "candidate_potential_unavailable",
                "upstream_reason": "background_archetype_prior_disabled_pending_validation",
            }
''',
)
text = text.replace(
    '''    candidate["relevant_need"] = {
        "state": "unavailable",
        "reason": "candidate_potential_incomplete",
        "upstream_reason": "candidate_potential_partially_unavailable",
        "relevant": None,
        "matches": [],
        "other_company_gaps": [],
    }
''',
    '''    candidate["relevant_need"] = {
        "state": "unavailable",
        "relevant": None,
        "matches": [],
        "other_company_gaps": [],
    }
    candidate["relevant_need_availability"] = {
        "state": "unavailable",
        "reason": "candidate_potential_incomplete",
        "upstream_reason": "candidate_potential_partially_unavailable",
    }
''',
)
Path(path).write_text(text, encoding="utf-8")

# Documentation describes the sibling metadata rather than changing relevant_need's established shape.
path = "docs/LOCAL_APPLICATION_API.md"
replace_once(
    path,
    '''unavailability may therefore be rendered once at candidate level without the
frontend inferring semantics from repeated display rows. `relevant_need` publishes
its own bounded reason (`candidate_potential_unavailable`,
`candidate_potential_incomplete`, `company_intent_coverage_unavailable`, or the
combined/fallback states) and may preserve the upstream candidate-potential reason.
Nullable analytical percentages remain unavailable values rather than numeric zero.
''',
    '''unavailability may therefore be rendered once at candidate level without the
frontend inferring semantics from repeated display rows. The established
`relevant_need` object continues to project the Target-owned availability state
without re-inference. Additive sibling `relevant_need_availability` explains an
unavailable state with a bounded reason (`candidate_potential_unavailable`,
`candidate_potential_incomplete`, `company_intent_coverage_unavailable`, or the
combined/fallback states) and may preserve the upstream candidate-potential reason.
Missing Company metadata is unknown, not evidence that Company intent is unavailable.
Nullable analytical percentages remain unavailable values rather than numeric zero.
''',
)

print("issue 222 additive availability contract fix applied")
