from pathlib import Path

path = Path('bbtool/app/static/recruitment.js')
text = path.read_text(encoding='utf-8')
old = '''  function evidenceLabel(candidate) {
    if (candidate?.potential_availability?.state === 'unavailable') return 'Analysis unavailable';
    const names = evidenceNames(candidate);
    if (names.length) return names.join(', ');
    const potential = candidate?.potential || [];
    if (potential.some((row) => row.state === 'known_evidence_estimate')) return 'Known evidence applied';
    if (potential.some((row) => row.state === 'prior_only')) return 'Prior-only evidence';
    if (candidate?.potential_availability?.state === 'partial') return 'Analysis partially unavailable';
    return 'Analysis unavailable';
  }
'''
new = '''  function evidenceLabel(candidate) {
    const availability = candidate?.potential_availability?.state;
    if (availability === 'unavailable') return 'Analysis unavailable';
    const partial = availability === 'partial';
    const names = evidenceNames(candidate);
    if (names.length) {
      const applied = names.join(', ');
      return partial ? `${applied} · analysis partially unavailable` : applied;
    }
    const potential = candidate?.potential || [];
    if (potential.some((row) => row.state === 'known_evidence_estimate')) {
      return partial ? 'Known evidence applied · analysis partially unavailable' : 'Known evidence applied';
    }
    if (potential.some((row) => row.state === 'prior_only')) {
      return partial ? 'Prior-only evidence · analysis partially unavailable' : 'Prior-only evidence';
    }
    if (partial) return 'Analysis partially unavailable';
    return 'Analysis unavailable';
  }
'''
if old not in text:
    raise SystemExit('recruitment evidenceLabel block not found')
path.write_text(text.replace(old, new, 1), encoding='utf-8')

path = Path('tests/ui/test_recruitment_browser.py')
text = path.read_text(encoding='utf-8')
old = '''    need_text = browser.execute_script(
        "return document.getElementById('recruit-needs').textContent"
    )
    assert "candidate-potential evidence is incomplete" in need_text
    _assert_no_js_errors(browser)
'''
new = '''    evidence_text = browser.execute_script(
        "return document.getElementById('recruit-evidence').textContent"
    )
    assert "Prior-only evidence · analysis partially unavailable" in evidence_text
    need_text = browser.execute_script(
        "return document.getElementById('recruit-needs').textContent"
    )
    assert "candidate-potential evidence is incomplete" in need_text
    _assert_no_js_errors(browser)
'''
if old not in text:
    raise SystemExit('partial browser assertion block not found')
path.write_text(text.replace(old, new, 1), encoding='utf-8')

print('issue 222 partial-evidence review fix applied')
