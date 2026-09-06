'use strict';

(() => {
  const recruitmentState = {
    data: null,
    candidates: [],
    selectedIndex: null,
    shortlist: new Set(),
    currentSettlementIndex: 0,
    loadedJobId: null,
    lastFreshness: null,
    loading: false,
    compareOpen: false,
  };

  function money(value) {
    const number = Number(value);
    return Number.isFinite(number) ? `${Math.round(number)}g` : '—';
  }

  function candidateByIndex(index) {
    if (index === null || index === undefined || index === '') return null;
    const numericIndex = Number(index);
    if (!Number.isInteger(numericIndex)) return null;
    return recruitmentState.candidates.find((item) => item.recruit_index === numericIndex) || null;
  }

  function flattenCandidates(data) {
    const rows = [];
    for (const settlement of data?.settlements || []) {
      for (const candidate of settlement.candidates || []) {
        rows.push({...candidate, settlement_context: settlement});
      }
    }
    return rows;
  }

  function publicationChanged(previous, next) {
    if (!previous || !next) return false;
    return previous.generation !== next.generation || previous.job_id !== next.job_id;
  }

  function resetPublicationDecisionState() {
    recruitmentState.selectedIndex = null;
    recruitmentState.shortlist.clear();
    recruitmentState.currentSettlementIndex = 0;
    recruitmentState.compareOpen = false;
  }

  function potentialLabel(top) {
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
    const need = candidate?.relevant_need || {};
    if (need.state !== 'available') return 'Unavailable';
    if (!need.relevant) return 'No matching company gap';
    return need.relevant.role || 'Matching company gap';
  }

  function evidenceNames(candidate) {
    const names = new Set();
    for (const row of candidate?.potential || []) {
      for (const name of row.evidence || []) names.add(name);
    }
    return [...names].sort();
  }

  function evidenceLabel(candidate) {
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

  function setLoading(message) {
    const loading = document.getElementById('recruitment-loading');
    loading.hidden = false;
    loading.textContent = message;
    document.getElementById('recruitment-layout').hidden = true;
  }

  function renderCurrentSettlement(index = recruitmentState.currentSettlementIndex) {
    const settlements = recruitmentState.data?.settlements || [];
    if (!settlements.length) return;
    const bounded = Math.min(Math.max(index, 0), settlements.length - 1);
    recruitmentState.currentSettlementIndex = bounded;
    const settlement = settlements[bounded];
    document.getElementById('recruit-current-settlement-name').textContent = settlement.settlement;
    document.getElementById('recruit-current-settlement-summary').textContent = settlement.observation_summary;
  }

  function syncCurrentSettlement() {
    const browser = document.getElementById('recruit-browser');
    const header = browser?.querySelector('.recruit-browser-head');
    if (!browser || !header || browser.offsetParent === null) return;
    const groups = [...browser.querySelectorAll('.settlement-group')];
    if (!groups.length) return;
    const top = header.getBoundingClientRect().bottom;
    const bottom = browser.getBoundingClientRect().bottom;
    const visible = groups.map((group, index) => {
      let area = 0;
      group.querySelectorAll('.recruit-row').forEach((row) => {
        const rect = row.getBoundingClientRect();
        area += Math.max(0, Math.min(rect.bottom, bottom) - Math.max(rect.top, top));
      });
      return {index, area};
    });
    const leader = visible.reduce((best, item) => item.area > best.area ? item : best, visible[0]);
    const current = visible[recruitmentState.currentSettlementIndex] || {area: 0};
    const hysteresis = 24;
    if (leader.index !== recruitmentState.currentSettlementIndex
        && (current.area === 0 || leader.area > current.area + hysteresis)) {
      renderCurrentSettlement(leader.index);
    } else {
      renderCurrentSettlement(recruitmentState.currentSettlementIndex);
    }
  }

  function addMiniScan(parent, label, value) {
    const cell = node('span', 'recruit-scan-mini');
    cell.append(node('span', '', label));
    cell.append(node('strong', '', value));
    parent.append(cell);
  }

  function renderBrowser() {
    const browser = document.getElementById('recruit-browser');
    const host = document.getElementById('recruit-browser-groups');
    const select = document.getElementById('recruit-mobile-select');
    const scrollTop = browser.scrollTop;
    clear(host);
    clear(select);

    for (const [settlementIndex, settlement] of (recruitmentState.data?.settlements || []).entries()) {
      const group = node('section', 'settlement-group');
      group.dataset.settlementIndex = String(settlementIndex);
      const heading = node('div', 'settlement-group-head');
      heading.append(node('strong', '', settlement.settlement));
      heading.append(node('small', '', settlement.observation_summary));
      group.append(heading);

      for (const candidate of settlement.candidates || []) {
        const facts = candidate.facts || {};
        const row = node('div', 'recruit-row');
        row.dataset.recruitIndex = candidate.recruit_index;
        row.setAttribute('role', 'button');
        row.setAttribute('tabindex', '0');
        row.setAttribute('aria-pressed', String(candidate.recruit_index === recruitmentState.selectedIndex));
        const topLine = node('span', 'recruit-row-top');
        topLine.append(node('span', 'recruit-row-name', facts.Name || `Candidate ${candidate.recruit_index + 1}`));
        topLine.append(node('span', 'recruit-row-cost', money(facts.HireCost)));
        row.append(topLine);
        row.append(node('span', 'recruit-row-meta', `${facts.Background || 'Unknown background'} · L${facts.Level ?? '—'} · ${money(facts.DailyWage)}/day`));
        const scan = node('span', 'recruit-row-scan');
        addMiniScan(scan, 'Top Potential', potentialLabel(candidate.top_potential));
        addMiniScan(scan, 'Relevant Need', needLabel(candidate));
        row.append(scan);
        const bottom = node('span', 'recruit-row-bottom');
        bottom.append(node('span', 'recruit-row-evidence', `${evidenceLabel(candidate)} · ${facts.TryoutDone ? 'tryout' : 'no tryout'}`));
        const shortlist = node('button', 'recruit-shortlist-toggle', recruitmentState.shortlist.has(candidate.recruit_index) ? 'Shortlisted' : 'Shortlist');
        shortlist.type = 'button';
        shortlist.dataset.shortlistIndex = candidate.recruit_index;
        shortlist.dataset.active = String(recruitmentState.shortlist.has(candidate.recruit_index));
        shortlist.addEventListener('click', (event) => {
          event.stopPropagation();
          toggleShortlist(candidate.recruit_index);
        });
        bottom.append(shortlist);
        row.append(bottom);
        row.addEventListener('click', () => selectCandidate(candidate.recruit_index));
        row.addEventListener('keydown', (event) => {
          if ((event.key === 'Enter' || event.key === ' ') && event.target === row) {
            event.preventDefault();
            selectCandidate(candidate.recruit_index);
          }
        });
        group.append(row);

        const option = node('option', '', mobileCandidateLabel(settlement.settlement, candidate));
        option.value = candidate.recruit_index;
        select.append(option);
      }
      host.append(group);
    }
    select.value = recruitmentState.selectedIndex == null ? '' : String(recruitmentState.selectedIndex);
    browser.scrollTop = scrollTop;
    requestAnimationFrame(syncCurrentSettlement);
  }

  function renderScanCard(id, label, value, note) {
    const target = document.getElementById(id);
    clear(target);
    target.append(node('span', '', label));
    target.append(node('strong', '', value));
    target.append(node('small', '', note));
  }

  function renderPotential(candidate) {
    const host = document.getElementById('recruit-potential');
    clear(host);
    if (candidate?.potential_availability?.state === 'unavailable') {
      host.append(node('p', 'subtle', potentialUnavailableMessage(candidate)));
      return;
    }
    const topIdentity = candidate.top_potential?.build_identity;
    for (const potential of candidate.potential || []) {
      const row = node('article', 'recruit-potential-row');
      const main = node('div', 'recruit-potential-main');
      const identity = node('div');
      identity.append(node('div', 'recruit-potential-name', potential.role || potential.build_identity || 'Unknown role'));
      if (potential.build_identity === topIdentity) identity.append(node('span', 'tag', 'Top Potential'));
      main.append(identity);

      const candidateValue = node('div');
      candidateValue.append(node('span', 'recruit-potential-label', potential.state === 'known_evidence_estimate' ? 'Known-evidence estimate' : 'Candidate estimate'));
      if (potential.state === 'known_evidence_estimate' && potential.candidate_estimate_pct != null) {
        candidateValue.append(node('div', 'recruit-potential-value', formatPct(potential.candidate_estimate_pct)));
        if (potential.evidence?.length) candidateValue.append(node('small', 'recruit-evidence-note', `Basis: ${potential.evidence.join(', ')}`));
      } else if (potential.state === 'prior_only') {
        candidateValue.append(node('div', 'recruit-potential-value', 'Not available'));
        candidateValue.append(node('span', 'recruit-prior-only', 'Prior only'));
      } else {
        candidateValue.append(node('div', 'recruit-potential-value', 'Unavailable'));
      }
      main.append(candidateValue);

      const prior = node('div');
      prior.append(node('span', 'recruit-potential-label', 'Background prior'));
      prior.append(node('div', 'recruit-potential-value', formatPct(potential.background_prior_pct)));
      main.append(prior);
      row.append(main);
      host.append(row);
    }
    if (!host.children.length) host.append(node('p', 'subtle', 'No intrinsic Recruitment potential is available.'));
  }

  function needExplanation(row) {
    const labels = {
      assigned_but_no_viable_holder: 'Assigned role has no viable holder',
      single_point_of_failure: 'Single point of failure',
      contested_backup_only: 'Only contested backup depth',
    };
    return (row?.need_bases || []).map((item) => labels[item] || humanize(item)).join(' · ') || 'Company gap';
  }

  function renderNeed(candidate) {
    const host = document.getElementById('recruit-needs');
    const other = document.getElementById('recruit-other-gaps');
    clear(host);
    clear(other);
    const need = candidate.relevant_need || {};
    if (need.state !== 'available') {
      host.append(node('p', 'subtle', relevantNeedUnavailableMessage(candidate)));
      return;
    }
    for (const row of need.matches || []) {
      const card = node('article', 'recruit-need-card');
      card.dataset.relevant = 'true';
      const head = node('div', 'recruit-need-head');
      head.append(node('strong', '', row.role || row.build_identity || 'Company need'));
      head.append(node('span', 'tag', 'Relevant'));
      card.append(head);
      card.append(node('p', '', needExplanation(row)));
      host.append(card);
    }
    if (!need.matches?.length) host.append(node('p', 'subtle', 'No current company gap matches a plausible intrinsic path for this candidate.'));
    if (need.other_company_gaps?.length) {
      other.append(node('strong', '', 'Other company gaps not served by this candidate'));
      for (const row of need.other_company_gaps) {
        other.append(node('div', '', `${row.role || row.build_identity || 'Unknown role'} · ${needExplanation(row)}`));
      }
    }
  }

  function evidenceLine(parent, label, value) {
    const line = node('div', 'recruit-evidence-line');
    line.append(node('span', '', label));
    line.append(node('strong', '', value));
    parent.append(line);
  }

  function renderEvidence(candidate) {
    const facts = candidate.facts || {};
    const evidence = document.getElementById('recruit-evidence');
    const observation = document.getElementById('recruit-observation');
    clear(evidence);
    clear(observation);
    evidenceLine(evidence, 'Background', facts.Background || 'Unknown');
    evidenceLine(evidence, 'Level', facts.Level ?? '—');
    evidenceLine(evidence, 'Tryout', facts.TryoutDone ? 'Purchased' : 'Not purchased');
    evidenceLine(evidence, 'Applied evidence', evidenceLabel(candidate));
    evidenceLine(observation, 'Settlement', candidate.settlement_context.settlement);
    evidenceLine(observation, 'Settlement observation', candidate.settlement_context.observation_summary);
    evidenceLine(observation, 'Observed', 'Current analysis publication');
    evidenceLine(observation, 'Historical refresh age', 'Unavailable');
  }

  function renderShortlist() {
    const chips = document.getElementById('recruit-shortlist-chips');
    const compare = document.getElementById('recruit-compare');
    const grid = document.getElementById('recruit-compare-grid');
    clear(chips);
    clear(grid);
    const picks = [...recruitmentState.shortlist].map(candidateByIndex).filter(Boolean);
    if (!picks.length) chips.append(node('span', 'subtle', 'No candidates shortlisted.'));
    for (const candidate of picks) {
      chips.append(node('span', 'recruit-shortlist-chip', `${candidate.facts?.Name || `Candidate ${candidate.recruit_index + 1}`} · ${money(candidate.facts?.HireCost)}`));
      const card = node('article', 'recruit-compare-card');
      card.append(node('h4', '', candidate.facts?.Name || `Candidate ${candidate.recruit_index + 1}`));
      card.append(node('small', 'subtle', `${candidate.facts?.Background || 'Unknown'} · ${candidate.settlement_context.settlement}`));
      for (const [label, value] of [
        ['Economics', `${money(candidate.facts?.HireCost)} · ${money(candidate.facts?.DailyWage)}/day`],
        ['Top Potential', potentialLabel(candidate.top_potential)],
        ['Relevant Need', needLabel(candidate)],
        ['Evidence', evidenceLabel(candidate)],
        ['Tryout', candidate.facts?.TryoutDone ? 'Purchased' : 'Not purchased'],
      ]) {
        const line = node('div', 'recruit-compare-line');
        line.append(node('span', '', label));
        line.append(node('strong', '', value));
        card.append(line);
      }
      grid.append(card);
    }
    compare.hidden = !recruitmentState.compareOpen;
    document.getElementById('recruit-compare-toggle').textContent = recruitmentState.compareOpen ? 'Hide comparison ↑' : 'Compare shortlist ↓';
  }

  function renderDetail() {
    const candidate = candidateByIndex(recruitmentState.selectedIndex);
    if (!candidate) return;
    const facts = candidate.facts || {};
    document.getElementById('recruit-settlement').textContent = candidate.settlement_context.settlement;
    document.getElementById('recruit-name').textContent = facts.Name || `Candidate ${candidate.recruit_index + 1}`;
    document.getElementById('recruit-meta').textContent = `${facts.Background || 'Unknown background'} · Level ${facts.Level ?? '—'}${facts.Title ? ` · ${facts.Title}` : ''}`;
    document.getElementById('recruit-hire-cost').textContent = money(facts.HireCost);
    document.getElementById('recruit-daily-wage').textContent = money(facts.DailyWage);
    const top = candidate.top_potential;
    renderScanCard('recruit-top-scan', 'Top Potential · Intrinsic', potentialLabel(top), top?.state === 'known_evidence_estimate' ? 'Known-evidence estimate' : top?.state === 'prior_only' ? 'Background prior only' : 'Unavailable');
    renderScanCard('recruit-need-scan', 'Relevant Need · Company context', needLabel(candidate), 'Kept separate from intrinsic potential');
    renderScanCard('recruit-evidence-scan', 'Known Evidence', evidenceLabel(candidate), facts.TryoutDone ? 'Tryout purchased' : 'No tryout evidence');
    renderPotential(candidate);
    renderNeed(candidate);
    renderEvidence(candidate);
    const toggle = document.getElementById('recruit-shortlist-current');
    toggle.textContent = recruitmentState.shortlist.has(candidate.recruit_index) ? 'Remove from shortlist' : 'Add to shortlist';
    renderShortlist();
  }

  function selectCandidate(index) {
    if (!candidateByIndex(index)) return;
    recruitmentState.selectedIndex = Number(index);
    renderBrowser();
    renderDetail();
  }

  function toggleShortlist(index) {
    const key = Number(index);
    if (recruitmentState.shortlist.has(key)) recruitmentState.shortlist.delete(key);
    else recruitmentState.shortlist.add(key);
    renderBrowser();
    renderDetail();
  }

  function renderRecruitment() {
    if (!recruitmentState.data?.available) {
      setLoading(state.result?.available ? 'Recruitment data is temporarily unavailable.' : 'Waiting for a completed analysis.');
      return;
    }
    recruitmentState.candidates = flattenCandidates(recruitmentState.data);
    if (!recruitmentState.candidates.length) {
      setLoading('No recruits are available in the current analysis.');
      return;
    }
    if (!candidateByIndex(recruitmentState.selectedIndex)) {
      recruitmentState.selectedIndex = recruitmentState.candidates[0].recruit_index;
    }
    document.getElementById('recruitment-loading').hidden = true;
    document.getElementById('recruitment-layout').hidden = false;
    renderBrowser();
    renderDetail();
  }

  async function loadRecruitment() {
    if (recruitmentState.loading) return;
    recruitmentState.loading = true;
    try {
      const nextData = await fetchData('/api/v1/recruitment');
      if (publicationChanged(recruitmentState.data, nextData)) {
        resetPublicationDecisionState();
      }
      recruitmentState.data = nextData;
      recruitmentState.loadedJobId = recruitmentState.data?.job_id ?? null;
      renderRecruitment();
    } catch (_error) {
      setLoading('Recruitment data is temporarily unavailable.');
    } finally {
      recruitmentState.loading = false;
    }
  }

  async function syncRecruitment() {
    if (routeFromHash().workspace !== 'recruitment') return;
    const freshness = freshnessFromState()?.status || 'unavailable';
    const becameCurrent = freshness === 'current' && recruitmentState.lastFreshness !== 'current';
    recruitmentState.lastFreshness = freshness;
    const desiredJobId = state.activeJob?.id ?? null;
    const publicationChanged = freshness === 'current' && desiredJobId != null && recruitmentState.loadedJobId !== desiredJobId;
    if (!recruitmentState.data || becameCurrent || publicationChanged) await loadRecruitment();
  }

  window.addEventListener('hashchange', () => {
    if (routeFromHash().workspace === 'recruitment') {
      renderRecruitment();
      syncRecruitment();
    }
  });
  window.addEventListener('resize', () => requestAnimationFrame(syncCurrentSettlement));

  document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('recruit-mobile-select').addEventListener('change', (event) => selectCandidate(event.target.value));
    document.getElementById('recruit-browser').addEventListener('scroll', syncCurrentSettlement, {passive: true});
    document.getElementById('recruit-shortlist-current').addEventListener('click', () => toggleShortlist(recruitmentState.selectedIndex));
    document.getElementById('recruit-compare-toggle').addEventListener('click', () => {
      recruitmentState.compareOpen = !recruitmentState.compareOpen;
      renderShortlist();
    });
    syncRecruitment();
    window.setInterval(syncRecruitment, 800);
  });
})();
