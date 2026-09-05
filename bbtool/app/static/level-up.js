'use strict';

const BrotherViews = (() => {
  const STANDARD_GEAR_SLOTS = [
    ['Head', 'Head'],
    ['Body', 'Body'],
    ['MainHand', 'Main Hand'],
    ['OffHand', 'Off Hand'],
    ['Accessory', 'Accessory'],
    ['Ammo', 'Ammo'],
  ];
  const ITEM_DETAIL_FIELDS = [
    ['Slot', 'Slot'],
    ['ItemID', 'Item ID'],
    ['Type', 'Type'],
    ['Condition', 'Condition'],
    ['ConditionMax', 'Condition max'],
    ['Armor', 'Armor'],
    ['ArmorMax', 'Armor max'],
    ['Fatigue', 'FAT'],
    ['Quantity', 'Quantity'],
    ['DamageMin', 'Damage min'],
    ['DamageMax', 'Damage max'],
    ['ArmorDamagePercent', 'Armor damage'],
    ['DirectDamagePercent', 'Direct damage'],
  ];
  const PERCENT_FIELDS = new Set(['ArmorDamagePercent', 'DirectDamagePercent']);

  function itemName(value) {
    if (value === null || value === undefined) return 'Empty';
    if (typeof value !== 'object' || Array.isArray(value)) return String(value);
    return value.Name || value.DisplayName || value.ItemName || value.ItemID || 'Equipped item';
  }

  function itemDetails(value) {
    if (!value || typeof value !== 'object' || Array.isArray(value)) return [];
    return ITEM_DETAIL_FIELDS
      .filter(([key]) => value[key] !== undefined && value[key] !== null)
      .map(([key, label]) => {
        const suffix = PERCENT_FIELDS.has(key) ? '%' : '';
        return `${label}: ${value[key]}${suffix}`;
      });
  }

  function itemCard(label, value, extraDetails = []) {
    const card = node('div', 'gear-card');
    card.append(node('span', 'context-label', label));
    card.append(node('strong', '', itemName(value)));
    const details = [...itemDetails(value), ...extraDetails];
    if (details.length) card.append(node('small', 'gear-detail', details.join(' · ')));
    return card;
  }

  function renderGear(equipment, fatigue, targets) {
    const container = document.getElementById(targets.gridId);
    const total = document.getElementById(targets.fatigueId);
    if (!container || !total) return;
    clear(container);
    const safeEquipment = equipment && typeof equipment === 'object' ? equipment : {};
    const safeFatigue = fatigue && typeof fatigue === 'object' ? fatigue : {};

    for (const [key, label] of STANDARD_GEAR_SLOTS) {
      const slotDetails = safeFatigue[key] !== undefined
        ? [`Slot FAT: ${formatNumber(safeFatigue[key])}`]
        : [];
      container.append(itemCard(label, safeEquipment[key], slotDetails));
    }

    const bag = Array.isArray(safeEquipment.Bag) ? safeEquipment.Bag : [];
    const bagSummary = node('div', 'gear-card');
    bagSummary.append(node('span', 'context-label', 'Bag'));
    bagSummary.append(node('strong', '', bag.length ? `${bag.length} item${bag.length === 1 ? '' : 's'}` : 'Empty'));
    if (safeFatigue.Bag !== undefined) {
      bagSummary.append(node('small', 'gear-detail', `Bag FAT: ${formatNumber(safeFatigue.Bag)}`));
    }
    container.append(bagSummary);

    for (const [index, item] of bag.entries()) {
      container.append(itemCard(`Bag ${index + 1}`, item));
    }

    total.textContent = `Gear FAT ${formatNumber(safeFatigue.Total)}`;
  }

  function factValue(value) {
    if (value === null || value === undefined) return '—';
    if (typeof value === 'object') return JSON.stringify(value);
    return String(value);
  }

  function renderMechanics(facts, targetId) {
    const container = document.getElementById(targetId);
    if (!container) return;
    clear(container);
    if (!Array.isArray(facts) || !facts.length) {
      container.append(node('p', 'subtle', 'No deterministic perk / gear Mechanical Facts are available for this Brother.'));
      return;
    }
    for (const fact of facts) {
      if (!fact || typeof fact !== 'object') continue;
      const row = node('div', 'mechanic-row');
      const title = node('div');
      title.append(node('strong', '', fact.Perk || fact.Mechanic || 'Mechanical fact'));
      title.append(node('small', 'subtle', fact.Basis ? humanize(fact.Basis) : 'Current state'));
      row.append(title);
      row.append(node('strong', 'mechanic-state', humanize(fact.State || 'known')));
      const evidence = node('div', 'mechanic-evidence');
      for (const [key, value] of Object.entries(fact)) {
        if (['Perk', 'Mechanic', 'Basis', 'State'].includes(key)) continue;
        evidence.append(node('span', 'tag', `${humanize(key)}: ${factValue(value)}`));
      }
      row.append(evidence);
      container.append(row);
    }
  }

  function ensureLevelUpPanels() {
    const decision = document.getElementById('levelup-decision');
    const recommendations = decision?.querySelector('.levelup-recommendations');
    if (!decision || !recommendations) return null;

    let gear = document.getElementById('levelup-gear');
    if (!gear) {
      gear = node('section', 'card');
      gear.id = 'levelup-gear';
      gear.setAttribute('aria-labelledby', 'levelup-gear-heading');
      const head = node('div', 'card-head');
      const title = node('div');
      title.append(node('span', 'eyebrow', 'Fact'));
      const heading = node('h2', '', 'Gear');
      heading.id = 'levelup-gear-heading';
      title.append(heading);
      head.append(title);
      const fatigue = node('strong', '', 'Gear FAT —');
      fatigue.id = 'levelup-gear-fatigue';
      head.append(fatigue);
      gear.append(head);
      const body = node('div', 'card-body');
      const grid = node('div', 'gear-grid');
      grid.id = 'levelup-gear-grid';
      body.append(grid);
      gear.append(body);
      decision.insertBefore(gear, recommendations);
    }

    let mechanics = document.getElementById('levelup-mechanics');
    if (!mechanics) {
      mechanics = node('section', 'card');
      mechanics.id = 'levelup-mechanics';
      mechanics.setAttribute('aria-labelledby', 'levelup-mechanics-heading');
      const head = node('div', 'card-head');
      const title = node('div');
      title.append(node('span', 'eyebrow', 'Fact'));
      const heading = node('h2', '', 'Mechanics');
      heading.id = 'levelup-mechanics-heading';
      title.append(heading);
      head.append(title);
      mechanics.append(head);
      const body = node('div', 'card-body');
      body.id = 'levelup-mechanics-list';
      mechanics.append(body);
      decision.insertBefore(mechanics, recommendations);
    }
    return {
      gear: {gridId: 'levelup-gear-grid', fatigueId: 'levelup-gear-fatigue'},
      mechanicsId: 'levelup-mechanics-list',
    };
  }

  function renderLevelUp(decision) {
    const targets = ensureLevelUpPanels();
    if (!targets) return;
    renderGear(decision?.equipment, decision?.gear_fatigue, targets.gear);
    renderMechanics(decision?.mechanical_facts, targets.mechanicsId);
  }

  return {renderGear, renderMechanics, renderLevelUp};
})();

window.BrotherViews = BrotherViews;
window.renderGear = function renderGear(snapshot) {
  BrotherViews.renderGear(snapshot?.Equipment, snapshot?.GearFatigue, {
    gridId: 'gear-grid',
    fatigueId: 'gear-fatigue',
  });
};
window.renderMechanics = function renderMechanics(facts) {
  BrotherViews.renderMechanics(facts, 'mechanics-list');
};

(() => {
  const levelUpState = {
    data: null,
    selectedBrotherId: null,
    loadedJobId: Symbol('not-loaded'),
    lastFreshness: null,
    loading: false,
  };

  function decisionById(id) {
    return levelUpState.data?.decisions?.find((item) => item.brother_id === id) || null;
  }

  function deltaPct(value) {
    const number = Number(value);
    if (!Number.isFinite(number)) return '—';
    return `${number > 0 ? '+' : ''}${number.toFixed(1)}%`;
  }

  function setLoading(message) {
    const loading = document.getElementById('levelup-loading');
    loading.hidden = false;
    loading.textContent = message;
    document.getElementById('levelup-layout').hidden = true;
  }

  function buildPickSummary(candidate) {
    if (!candidate?.Stats?.length) return 'No distinct recommendation';
    return candidate.Stats.map((stat) => `${stat} +${candidate.Rolls?.[stat] ?? '—'}`).join(' · ');
  }

  function renderQueue() {
    const queue = document.getElementById('levelup-queue');
    const select = document.getElementById('levelup-brother-select');
    clear(queue);
    clear(select);
    const decisions = levelUpState.data?.decisions || [];
    for (const decision of decisions) {
      const button = node('button', 'levelup-queue-item');
      button.type = 'button';
      button.dataset.brotherId = decision.brother_id;
      button.setAttribute('aria-pressed', String(decision.brother_id === levelUpState.selectedBrotherId));
      const identity = node('span', 'queue-identity');
      identity.append(node('strong', '', decision.name || decision.brother_id));
      identity.append(node('small', 'subtle', `Lv ${decision.level ?? '—'} · ${decision.background || 'Unknown background'}`));
      button.append(identity);
      button.append(node('small', 'queue-primary', buildPickSummary(decision.primary)));
      button.addEventListener('click', () => selectBrother(decision.brother_id));
      queue.append(button);

      const option = node('option', '', `${decision.name || decision.brother_id} · ${buildPickSummary(decision.primary)}`);
      option.value = decision.brother_id;
      select.append(option);
    }
    select.value = levelUpState.selectedBrotherId || '';
  }

  function renderRoleContext(decision) {
    document.getElementById('levelup-brother-name').textContent = decision.name || decision.brother_id;
    document.getElementById('levelup-brother-meta').textContent = `Lv ${decision.level ?? '—'} · ${decision.background || 'Unknown background'}`;

    const assigned = decision.assigned_build || {};
    const assignedValue = assigned.display_name || assigned.build_identity || 'Unassigned';
    document.getElementById('levelup-assigned-build').textContent = assignedValue;
    const assignedStatus = assigned.status && assigned.status !== 'current'
      ? ` · ${humanize(assigned.status)}` : '';
    document.getElementById('levelup-assigned-note').textContent = `Player intent${assignedStatus}`;

    const best = decision.best_fit || {};
    document.getElementById('levelup-best-fit').textContent = best.role || '—';
    document.getElementById('levelup-best-note').textContent = `${formatPct(best.fit_pct)} · intrinsic analysis`;
  }

  function renderPrimaryPreview(primary) {
    const preview = document.getElementById('levelup-primary-preview');
    clear(preview);
    preview.append(node('span', 'context-label', 'Primary · Take these rolls'));
    preview.append(node('strong', 'primary-preview-picks', buildPickSummary(primary)));
    if (primary) {
      preview.append(node('small', 'subtle', `Anchor Fit ${formatPct(primary.AnchorFitAfterPct)} · ${deltaPct(primary.FitDeltaPct)}`));
    }
  }

  function renderRolls(decision) {
    const container = document.getElementById('levelup-rolls');
    clear(container);
    if (!decision.rolls?.length) {
      container.append(node('p', 'subtle', 'No current level-up rolls are available.'));
      return;
    }
    for (const roll of decision.rolls) {
      const card = node('article', 'levelup-roll');
      const head = node('div', 'roll-head');
      head.append(node('strong', 'roll-stat', roll.stat));
      head.append(node('span', 'roll-offer', `+${roll.offered_roll ?? '—'}`));
      card.append(head);
      const current = node('div', 'roll-current');
      current.append(node('span', 'subtle', `Current ${roll.current_value ?? '—'}`));
      const stars = Number(roll.stars || 0);
      current.append(node('span', 'roll-stars', stars ? '★'.repeat(stars) : '—'));
      card.append(current);
      card.append(node('small', 'subtle', `${roll.band || '—'} · range +${roll.min_roll ?? '—'}–+${roll.max_roll ?? '—'} · quality ${formatPct(Number(roll.quality) * 100)}`));
      const uses = node('div', 'roll-uses');
      if (roll.primary) uses.append(node('span', 'tag tag-primary', 'Primary'));
      if (roll.runner_up) uses.append(node('span', 'tag', 'Runner-up'));
      if (!roll.primary && !roll.runner_up) uses.append(node('span', 'subtle', 'Not selected'));
      card.append(uses);
      container.append(card);
    }
  }

  function renderConsequence(parent, label, consequence) {
    if (!consequence) return;
    const card = node('div', 'consequence-card');
    card.append(node('span', 'context-label', label));
    card.append(node('strong', '', consequence.Role || '—'));
    const fit = node('div', 'consequence-line');
    fit.append(node('span', 'subtle', 'Fit'));
    fit.append(node('strong', '', `${formatPct(consequence.FitBeforePct)} → ${formatPct(consequence.FitAfterPct)} (${deltaPct(consequence.FitDeltaPct)})`));
    card.append(fit);
    const feasible = node('div', 'consequence-line');
    feasible.append(node('span', 'subtle', 'P ≥ target'));
    feasible.append(node('strong', '', `${formatPct(consequence.FitFeasibilityBeforePct)} → ${formatPct(consequence.FitFeasibilityAfterPct)}`));
    card.append(feasible);
    card.append(node('small', 'subtle', `Likely after ${formatPct(consequence.FitLikelyMinAfterPct)}–${formatPct(consequence.FitLikelyMaxAfterPct)}`));
    parent.append(card);
  }

  function renderCandidate(id, candidate, emptyText) {
    const container = document.getElementById(id);
    clear(container);
    if (!candidate) {
      container.append(node('p', 'subtle', emptyText));
      return;
    }
    container.append(node('strong', 'decision-picks', buildPickSummary(candidate)));
    container.append(node('p', 'decision-fit', `Anchor Fit ${formatPct(candidate.AnchorFitBeforePct)} → ${formatPct(candidate.AnchorFitAfterPct)} (${deltaPct(candidate.FitDeltaPct)})`));
    const consequences = node('div', 'consequence-grid');
    renderConsequence(consequences, 'Assigned Build consequence', candidate.Consequences?.AssignedBuild);
    renderConsequence(consequences, 'Best Fit consequence', candidate.Consequences?.BestFit);
    container.append(consequences);
  }

  function renderGamble(gamble) {
    const section = document.getElementById('levelup-gamble');
    if (!gamble) {
      section.hidden = true;
      clear(document.getElementById('levelup-gamble-body'));
      return;
    }
    section.hidden = false;
    const body = document.getElementById('levelup-gamble-body');
    clear(body);
    body.append(node('strong', 'decision-picks', buildPickSummary(gamble)));
    for (const key of ['Trigger', 'Assumption', 'Scenario', 'Interpretation', 'Reason']) {
      if (gamble[key]) body.append(node('p', 'subtle', `${key}: ${gamble[key]}`));
    }
    const consequences = node('div', 'consequence-grid');
    renderConsequence(consequences, 'Assigned Build consequence', gamble.Consequences?.AssignedBuild);
    renderConsequence(consequences, 'Best Fit consequence', gamble.Consequences?.BestFit);
    body.append(consequences);
  }

  function renderExplain(explain) {
    const body = document.getElementById('levelup-explain-body');
    clear(body);
    const reasons = Object.entries(explain?.pick_reasons || {});
    if (reasons.length) {
      const section = node('section', 'explain-section');
      section.append(node('h3', '', 'Why Primary'));
      const list = node('ul');
      for (const [stat, reason] of reasons) list.append(node('li', '', `${stat}: ${reason}`));
      section.append(list);
      body.append(section);
    }
    if (explain?.skipped_important?.length) {
      const section = node('section', 'explain-section');
      section.append(node('h3', '', 'Attractive rolls skipped'));
      const list = node('ul');
      for (const item of explain.skipped_important) list.append(node('li', '', `${item.stat}: ${item.reason}`));
      section.append(list);
      body.append(section);
    }
    if (explain?.free_pick_mode) {
      body.append(node('p', 'subtle', `Fit-neutral free pick mode · selected ${explain.free_pick_stats?.join(', ') || 'none'} · candidates ${explain.free_pick_candidates?.join(', ') || 'none'}`));
    }
    if (explain?.method) body.append(node('p', 'method-note', explain.method));
    if (!body.children.length) body.append(node('p', 'subtle', 'No additional Advisor reasoning is available.'));
  }

  function renderDecision() {
    const decision = decisionById(levelUpState.selectedBrotherId);
    if (!decision) return;
    renderRoleContext(decision);
    renderPrimaryPreview(decision.primary);
    renderRolls(decision);
    BrotherViews.renderLevelUp(decision);
    renderCandidate('levelup-primary-body', decision.primary, 'Primary recommendation is unavailable.');
    renderCandidate('levelup-runner-body', decision.runner_up, 'No distinct Runner-up is available for this decision.');
    renderGamble(decision.gamble);
    renderExplain(decision.explain);
  }

  function selectBrother(id) {
    if (!decisionById(id)) return;
    levelUpState.selectedBrotherId = id;
    renderQueue();
    renderDecision();
  }

  function renderLevelUp() {
    if (!levelUpState.data?.available) {
      setLoading(state.result?.available ? 'Level Up data is temporarily unavailable.' : 'Waiting for a completed analysis.');
      return;
    }
    const decisions = levelUpState.data.decisions || [];
    if (!decisions.length) {
      setLoading('No Brothers currently have a pending level-up decision.');
      return;
    }
    if (!decisionById(levelUpState.selectedBrotherId)) {
      levelUpState.selectedBrotherId = decisions[0].brother_id;
    }
    document.getElementById('levelup-loading').hidden = true;
    document.getElementById('levelup-layout').hidden = false;
    renderQueue();
    renderDecision();
  }

  async function loadLevelUp() {
    if (levelUpState.loading) return;
    levelUpState.loading = true;
    try {
      const payload = await fetchData('/api/v1/level-up');
      levelUpState.data = payload;
      levelUpState.loadedJobId = state.loadedJobId;
      renderLevelUp();
    } catch (_error) {
      setLoading('Level Up data is temporarily unavailable.');
    } finally {
      levelUpState.loading = false;
    }
  }

  async function syncLevelUp() {
    if (routeFromHash().workspace !== 'level-up') return;
    const freshness = freshnessFromState()?.status || 'unavailable';
    const becameCurrent = freshness === 'current' && levelUpState.lastFreshness !== 'current';
    levelUpState.lastFreshness = freshness;
    const publicationChanged = freshness === 'current' && levelUpState.loadedJobId !== state.loadedJobId;
    const publicationBecameAvailable = state.result?.available && !levelUpState.data?.available;
    if (!levelUpState.data || publicationChanged || becameCurrent || publicationBecameAvailable) {
      await loadLevelUp();
    }
  }

  window.addEventListener('hashchange', () => {
    if (routeFromHash().workspace === 'level-up') {
      renderLevelUp();
      syncLevelUp();
    }
  });

  document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('levelup-brother-select').addEventListener('change', (event) => {
      selectBrother(event.target.value);
    });
    syncLevelUp();
    window.setInterval(syncLevelUp, 800);
  });
})();
