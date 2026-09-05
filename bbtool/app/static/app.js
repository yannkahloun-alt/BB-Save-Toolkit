'use strict';

const WORKSPACES = ['company', 'level-up', 'recruitment'];
const BROTHER_SECTIONS = ['current', 'gear', 'mechanics', 'potential', 'development'];
const WORKSPACE_LABELS = {
  company: 'Company',
  'level-up': 'Level Up',
  recruitment: 'Recruitment',
};
const FRESHNESS_LABELS = {
  current: 'Current',
  stale: 'Stale',
  detected: 'Update detected',
  stabilizing: 'Stabilizing save',
  queued: 'Queued',
  analyzing: 'Analyzing',
  unavailable: 'Unavailable',
  failed: 'Refresh failed',
  loading: 'Starting…',
};
const WARNING_LABELS = {
  recoverable_parsing_failures: 'Parsing recoveries',
  unresolved_references: 'Unresolved references',
  unresolved_backgrounds: 'Unresolved backgrounds',
  projection_validation_violations: 'Projection validation',
};
const STAT_LABELS = {
  HP: 'HP',
  Fatigue: 'FAT',
  Resolve: 'RES',
  Initiative: 'INI',
  MAtk: 'MAtk',
  RAtk: 'RAtk',
  MDef: 'MDef',
  RDef: 'RDef',
};
const GEAR_SLOTS = [
  ['Head', 'Head'],
  ['Body', 'Body'],
  ['MainHand', 'Main Hand'],
  ['OffHand', 'Off Hand'],
  ['Accessory', 'Accessory'],
  ['Ammo', 'Ammo'],
  ['Bag', 'Bag'],
];

const state = {
  followedSave: null,
  result: null,
  analysisHealth: null,
  activeJob: null,
  companyData: null,
  companySubview: 'roster',
  companySearch: '',
  companyReturn: null,
  sessionToken: null,
  mutatingAssignment: false,
};

function node(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined && text !== null) element.textContent = String(text);
  return element;
}

function clear(element) {
  while (element.firstChild) element.removeChild(element.firstChild);
}

function formatPct(value, fallback = '—') {
  const number = Number(value);
  return Number.isFinite(number) ? `${number.toFixed(1)}%` : fallback;
}

function formatNumber(value, fallback = '—') {
  const number = Number(value);
  return Number.isFinite(number) ? String(Math.round(number * 10) / 10) : fallback;
}

function humanize(value) {
  return String(value || '')
    .replaceAll('_', ' ')
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function routeFromHash() {
  const raw = window.location.hash.slice(1);
  const parts = raw.split('/');
  const workspace = WORKSPACES.includes(parts[0]) ? parts[0] : 'company';
  if (workspace !== 'company' || parts[1] !== 'brother' || !parts[2]) {
    return {workspace, brotherId: null, section: 'current'};
  }
  let brotherId;
  try {
    brotherId = decodeURIComponent(parts[2]);
  } catch (_error) {
    brotherId = null;
  }
  const section = BROTHER_SECTIONS.includes(parts[3]) ? parts[3] : 'current';
  return {workspace: 'company', brotherId, section};
}

function brotherHash(brotherId, section) {
  return `#company/brother/${encodeURIComponent(brotherId)}/${section}`;
}

function selectWorkspace(route = routeFromHash()) {
  document.querySelectorAll('[data-workspace]').forEach((link) => {
    if (link.dataset.workspace === route.workspace) {
      link.setAttribute('aria-current', 'page');
    } else {
      link.removeAttribute('aria-current');
    }
  });
  document.querySelectorAll('[data-workspace-panel]').forEach((panel) => {
    panel.hidden = panel.dataset.workspacePanel !== route.workspace;
  });
  document.title = `${WORKSPACE_LABELS[route.workspace]} · Battle Brothers Save Toolkit`;

  if (route.workspace === 'company') {
    renderCompanyRoute(route);
  }

  const canonical = route.brotherId
    ? brotherHash(route.brotherId, route.section)
    : `#${route.workspace}`;
  if (window.location.hash !== canonical) {
    history.replaceState(null, '', canonical);
  }
}

async function fetchData(path) {
  const response = await fetch(path, {
    credentials: 'same-origin',
    cache: 'no-store',
    headers: {Accept: 'application/json'},
  });
  const payload = await response.json();
  if (!response.ok || payload.error) {
    throw new Error(payload.error?.message || `Request failed (${response.status})`);
  }
  return payload.data;
}

async function postData(path, body) {
  if (!state.sessionToken) {
    state.sessionToken = (await fetchData('/api/v1/session')).token;
  }
  const response = await fetch(path, {
    method: 'POST',
    credentials: 'same-origin',
    cache: 'no-store',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
      'X-BBST-Session': state.sessionToken,
    },
    body: JSON.stringify(body),
  });
  const payload = await response.json();
  if (!response.ok || payload.error) {
    const error = new Error(payload.error?.message || `Request failed (${response.status})`);
    error.code = payload.error?.code;
    throw error;
  }
  return payload.data;
}

function freshnessFromState() {
  if (state.result?.available && state.result.freshness) {
    return state.result.freshness;
  }
  return state.followedSave?.freshness || {
    status: state.followedSave?.available ? 'stale' : 'unavailable',
  };
}

function renderFreshness() {
  const freshness = freshnessFromState();
  const status = freshness?.status || 'unavailable';
  const element = document.getElementById('freshness-status');
  element.dataset.state = status;
  element.textContent = FRESHNESS_LABELS[status] || status;
  if (freshness?.reason) {
    element.title = humanize(freshness.reason);
  } else {
    element.removeAttribute('title');
  }
}

function renderFollowedSave() {
  const element = document.getElementById('save-label');
  const followed = state.followedSave;
  if (!followed?.name) {
    element.textContent = 'No save selected';
    element.removeAttribute('title');
    return;
  }
  element.textContent = followed.name;
  element.title = followed.name;
}

function renderHealth() {
  const health = state.analysisHealth;
  const button = document.getElementById('health-button');
  const heading = document.getElementById('health-heading');
  const detail = document.getElementById('health-detail');
  const counts = health?.counts;

  if (!health || !state.result?.available) {
    button.dataset.state = 'unavailable';
    button.textContent = 'Run Health · —';
    heading.textContent = 'Run Health unavailable';
    document.getElementById('health-result-warnings').textContent = '—';
    document.getElementById('health-parsing').textContent = '—';
    document.getElementById('health-references').textContent = '—';
    document.getElementById('health-validation').textContent = '—';
    detail.textContent = 'No completed analysis is available yet.';
    return;
  }

  const label = health.status === 'degraded' ? 'Degraded' : 'Healthy';
  button.dataset.state = health.status;
  button.textContent = `Run Health · ${label}`;
  heading.textContent = `Run Health: ${label}`;
  document.getElementById('health-result-warnings').textContent = counts.result_affecting_warnings;
  document.getElementById('health-parsing').textContent = counts.recoverable_parsing_failures;
  document.getElementById('health-references').textContent = counts.unresolved_references_relevant_to_save;
  document.getElementById('health-validation').textContent = health.projection_validation.status === 'pass' ? 'Pass' : 'Needs attention';

  if (!health.warning_categories.length) {
    detail.textContent = 'No result-affecting warning categories are present.';
    return;
  }
  detail.textContent = health.warning_categories
    .map((item) => `${WARNING_LABELS[item.code] || item.code}: ${item.count}`)
    .join(' · ');
}

function renderProgress() {
  const region = document.getElementById('progress-region');
  const job = state.activeJob;
  const freshness = freshnessFromState();
  const activeFreshness = ['stabilizing', 'queued', 'analyzing'].includes(freshness?.status);
  const activeJob = job && ['stabilizing', 'queued', 'running'].includes(job.status);

  if (!activeFreshness && !activeJob) {
    region.hidden = true;
    return;
  }

  region.hidden = false;
  const progress = job?.progress;
  const completedCount = progress?.completed_count || 0;
  const latestStage = progress?.latest_stage;
  const label = document.getElementById('progress-label');
  const detail = document.getElementById('progress-detail');

  if (latestStage) {
    label.textContent = humanize(latestStage);
    detail.textContent = `${completedCount} completed stage${completedCount === 1 ? '' : 's'}`;
  } else {
    label.textContent = FRESHNESS_LABELS[freshness?.status] || 'Analysis in progress';
    detail.textContent = job?.status === 'queued' ? 'Waiting for analysis worker' : '';
  }
}

function renderShell() {
  renderFollowedSave();
  renderFreshness();
  renderHealth();
  renderProgress();
  const route = routeFromHash();
  if (route.workspace === 'company' && route.brotherId) {
    renderBrother(route.brotherId, route.section);
  }
}

function matchesSearch(brother) {
  const query = state.companySearch.trim().toLowerCase();
  if (!query) return true;
  return [
    brother.snapshot?.Name,
    brother.snapshot?.Background,
    brother.assigned_build?.display_name,
    brother.best_fit?.role,
    brother.best_fit?.category,
  ].some((value) => String(value || '').toLowerCase().includes(query));
}

function setCompanySubview(name) {
  state.companySubview = ['roster', 'planning', 'matrix'].includes(name) ? name : 'roster';
  document.querySelectorAll('[data-company-view]').forEach((button) => {
    button.setAttribute('aria-pressed', String(button.dataset.companyView === state.companySubview));
  });
  for (const key of ['roster', 'planning', 'matrix']) {
    document.getElementById(`company-${key}`).hidden = key !== state.companySubview;
  }
  renderCompanySubview();
}

function rosterRoleCell(label, value, detail) {
  const cell = node('span', 'roster-role');
  cell.append(node('small', 'roster-label', label));
  cell.append(node('strong', '', value || 'Unassigned'));
  if (detail) cell.append(node('small', 'roster-detail', detail));
  return cell;
}

function renderRoster() {
  const container = document.getElementById('company-roster');
  clear(container);
  const brothers = (state.companyData?.brothers || []).filter(matchesSearch);
  if (!brothers.length) {
    container.append(node('p', 'empty-state', state.companyData?.brothers?.length ? 'No Brothers match this search.' : 'No roster data is available.'));
    return;
  }
  const list = node('div', 'roster-list');
  for (const brother of brothers) {
    const button = node('button', 'brother-row');
    button.type = 'button';
    button.dataset.brotherId = brother.brother_id;
    const identity = node('span', 'roster-identity');
    identity.append(node('strong', 'roster-name', brother.snapshot?.Name || brother.brother_id));
    identity.append(node('small', 'roster-detail', `Lv ${brother.snapshot?.Level ?? '—'} · ${brother.snapshot?.Background || 'Unknown background'}`));
    button.append(identity);
    const assignment = brother.assigned_build || {};
    const assignedLabel = assignment.display_name || (assignment.build_identity ? `${assignment.build_identity} (${humanize(assignment.status)})` : 'Unassigned');
    button.append(rosterRoleCell('Assigned Build', assignedLabel, assignment.status && assignment.status !== 'current' && assignment.status !== 'unassigned' ? humanize(assignment.status) : 'Intent'));
    button.append(rosterRoleCell('Best Fit', brother.best_fit?.role || '—', `${formatPct(brother.best_fit?.fit_pct)} · intrinsic`));
    const fit = node('span', 'roster-fit');
    fit.append(node('strong', '', formatPct(brother.best_fit?.fit_pct)));
    fit.append(node('small', 'roster-detail', `P ≥ target ${formatPct(brother.best_fit?.feasibility_pct)}`));
    button.append(fit);
    button.addEventListener('click', () => openBrother(brother.brother_id, 'current'));
    list.append(button);
  }
  container.append(list);
}

function renderPlanning() {
  const container = document.getElementById('company-planning');
  clear(container);
  const data = state.companyData;
  if (!data?.available) {
    container.append(node('p', 'empty-state', 'Planning data is unavailable.'));
    return;
  }
  const buildNames = new Map(data.builds.map((item) => [item.build_identity, item.display_name]));
  const intrinsic = new Map((data.company?.intrinsic_coverage || []).map((item) => [item.BuildIdentity, item]));
  const intended = data.company?.intended_coverage || [];

  if (data.company?.intent_fresh === false) {
    const stale = node('p', 'planning-stale', 'Planning / Coverage still represents the previous Assigned Build state while refreshed analysis is pending. Intrinsic Fit remains valid.');
    stale.setAttribute('role', 'status');
    container.append(stale);
  }

  const grid = node('div', 'coverage-grid');
  for (const item of intended) {
    const card = node('article', 'coverage-card');
    const header = node('div', 'coverage-head');
    header.append(node('strong', '', buildNames.get(item.BuildIdentity) || item.BuildIdentity));
    const need = item.NeedBases || [];
    header.append(node('span', need.length ? 'tag tag-warn' : 'tag', need.length ? need.map(humanize).join(', ') : (item.FragilityFacts?.NoIntent ? 'No intent yet' : 'Covered')));
    card.append(header);

    const metrics = node('dl', 'coverage-metrics');
    const intrinsicItem = intrinsic.get(item.BuildIdentity) || {};
    const values = [
      ['Assigned', item.AssignedCount],
      ['Assigned viable', item.AssignedViableCount],
      ['Free backups', item.FreeViableBackupCount],
      ['Contested', item.ContestedViableBackupCount],
      ['Intrinsic viable', intrinsicItem.ViableCount],
      ['Top intrinsic Fit', formatPct(intrinsicItem.TopFitPct)],
    ];
    for (const [label, value] of values) {
      const wrap = node('div');
      wrap.append(node('dt', '', label));
      wrap.append(node('dd', '', value ?? '—'));
      metrics.append(wrap);
    }
    card.append(metrics);
    grid.append(card);
  }
  if (!intended.length) {
    container.append(node('p', 'empty-state', 'Intent-aware Company coverage is unavailable for this analysis.'));
    return;
  }
  container.append(grid);
}

function renderMatrix() {
  const container = document.getElementById('company-matrix');
  clear(container);
  const data = state.companyData;
  const brothers = (data?.brothers || []).filter(matchesSearch);
  if (!data?.builds?.length || !brothers.length) {
    container.append(node('p', 'empty-state', 'Fit Matrix data is unavailable for this selection.'));
    return;
  }

  const wrap = node('div', 'matrix-wrap');
  const table = node('table', 'fit-matrix');
  const head = node('thead');
  const headRow = node('tr');
  headRow.append(node('th', '', 'Brother'));
  for (const build of data.builds) headRow.append(node('th', '', build.display_name));
  head.append(headRow);
  table.append(head);
  const body = node('tbody');
  for (const brother of brothers) {
    const row = node('tr');
    const nameCell = node('th', '', brother.snapshot?.Name || brother.brother_id);
    nameCell.scope = 'row';
    row.append(nameCell);
    const potentialByBuild = new Map(brother.potential.map((item) => [item.build_identity, item]));
    for (const build of data.builds) {
      const item = potentialByBuild.get(build.build_identity);
      const cell = node('td');
      cell.append(node('strong', '', formatPct(item?.fit_pct)));
      cell.append(node('small', 'matrix-range', item ? `${formatPct(item.likely_min_pct)}–${formatPct(item.likely_max_pct)}` : '—'));
      row.append(cell);
    }
    body.append(row);
  }
  table.append(body);
  wrap.append(table);
  container.append(wrap);
}

function renderCompanySubview() {
  if (state.companySubview === 'planning') renderPlanning();
  else if (state.companySubview === 'matrix') renderMatrix();
  else renderRoster();
}

function renderCompany() {
  const loading = document.getElementById('company-loading');
  if (!state.companyData?.available) {
    loading.hidden = false;
    loading.textContent = state.result?.available ? 'Loading Company data…' : 'Waiting for a completed analysis.';
    for (const key of ['roster', 'planning', 'matrix']) document.getElementById(`company-${key}`).hidden = true;
    return;
  }
  loading.hidden = true;
  setCompanySubview(state.companySubview);
}

function openBrother(brotherId, section) {
  state.companyReturn = {
    subview: state.companySubview,
    search: state.companySearch,
    scrollY: window.scrollY,
  };
  window.location.hash = brotherHash(brotherId, section);
}

function returnToCompany() {
  const saved = state.companyReturn;
  if (saved) {
    state.companySubview = saved.subview;
    state.companySearch = saved.search;
    document.getElementById('roster-search').value = saved.search;
  }
  window.location.hash = '#company';
  if (saved) {
    requestAnimationFrame(() => window.scrollTo(0, saved.scrollY));
  }
}

function brotherById(brotherId) {
  return state.companyData?.brothers?.find((item) => item.brother_id === brotherId) || null;
}

function renderChipList(id, values, emptyText) {
  const container = document.getElementById(id);
  clear(container);
  const items = Array.isArray(values) ? values : values ? String(values).split(';').map((value) => value.trim()).filter(Boolean) : [];
  if (!items.length) {
    container.append(node('span', 'subtle', emptyText));
    return;
  }
  for (const value of items) container.append(node('span', 'chip', value));
}

function renderStats(snapshot) {
  const container = document.getElementById('brother-stats');
  clear(container);
  for (const stat of Object.keys(STAT_LABELS)) {
    const card = node('div', 'stat-card');
    card.append(node('span', 'stat-name', STAT_LABELS[stat]));
    card.append(node('strong', 'stat-value', snapshot?.[stat] ?? '—'));
    const stars = Number(snapshot?.[`${stat}Stars`] || 0);
    card.append(node('span', 'stat-stars', stars ? '★'.repeat(stars) : '—'));
    container.append(card);
  }
}

function gearItemName(value) {
  if (value === null || value === undefined) return 'Empty';
  if (Array.isArray(value)) return value.length ? `${value.length} item${value.length === 1 ? '' : 's'}` : 'Empty';
  if (typeof value !== 'object') return String(value);
  return value.Name || value.DisplayName || value.name || value.ItemName || value.ID || value.id || 'Equipped item';
}

function gearDetails(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return [];
  const fields = [
    ['Armor', 'Armor'], ['Durability', 'Durability'], ['Condition', 'Condition'],
    ['Fatigue', 'FAT'], ['WeaponType', 'Type'], ['Class', 'Class'],
    ['DamageMin', 'Damage min'], ['DamageMax', 'Damage max'], ['Range', 'Range'],
    ['TwoHanded', 'Two-handed'], ['ShieldMeleeDefense', 'MDef'], ['ShieldRangedDefense', 'RDef'],
  ];
  return fields.filter(([key]) => value[key] !== undefined && value[key] !== null)
    .map(([key, label]) => `${label}: ${value[key]}`);
}

function renderGear(snapshot) {
  const container = document.getElementById('gear-grid');
  clear(container);
  const equipment = snapshot?.Equipment || {};
  const fatigue = snapshot?.GearFatigue || {};
  for (const [key, label] of GEAR_SLOTS) {
    const card = node('div', 'gear-card');
    card.append(node('span', 'context-label', label));
    card.append(node('strong', '', gearItemName(equipment[key])));
    const detailParts = gearDetails(equipment[key]);
    if (fatigue[key] !== undefined) detailParts.push(`FAT ${formatNumber(fatigue[key])}`);
    if (detailParts.length) card.append(node('small', 'gear-detail', detailParts.join(' · ')));
    container.append(card);
  }
  document.getElementById('gear-fatigue').textContent = `Gear FAT ${formatNumber(fatigue.Total)}`;
}

function renderMechanics(facts) {
  const container = document.getElementById('mechanics-list');
  clear(container);
  if (!facts?.length) {
    container.append(node('p', 'subtle', 'No deterministic perk / gear Mechanical Facts are available for this Brother.'));
    return;
  }
  for (const fact of facts) {
    const row = node('div', 'mechanic-row');
    const title = node('div');
    title.append(node('strong', '', fact.Perk || fact.Mechanic || 'Mechanical fact'));
    title.append(node('small', 'subtle', fact.Basis ? humanize(fact.Basis) : 'Current state'));
    row.append(title);
    row.append(node('strong', 'mechanic-state', humanize(fact.State || 'known')));
    const evidence = node('div', 'mechanic-evidence');
    for (const [key, value] of Object.entries(fact)) {
      if (['Perk', 'Mechanic', 'Basis', 'State'].includes(key)) continue;
      evidence.append(node('span', 'tag', `${humanize(key)}: ${value}`));
    }
    row.append(evidence);
    container.append(row);
  }
}

function renderPotential(potential) {
  const container = document.getElementById('potential-list');
  clear(container);
  if (!potential?.length) {
    container.append(node('p', 'subtle', 'No intrinsic archetype trajectories are available.'));
    return;
  }
  for (const item of potential) {
    const details = node('details', 'potential-row');
    const summary = node('summary');
    const role = node('span', 'potential-role');
    role.append(node('strong', '', item.role || 'Unknown build'));
    role.append(node('small', 'subtle', `Likely ${formatPct(item.likely_min_pct)}–${formatPct(item.likely_max_pct)}`));
    summary.append(role);
    summary.append(node('strong', 'potential-fit', formatPct(item.fit_pct)));
    summary.append(node('span', 'potential-prob', `P ≥ target ${formatPct(item.feasibility_pct)}`));
    details.append(summary);

    const body = node('div', 'potential-detail');
    body.append(node('p', 'subtle', `Full range ${formatPct(item.full_min_pct)}–${formatPct(item.full_max_pct)}. Fit is intrinsic and independent of Assigned Build.`));
    const ranges = node('div', 'range-grid');
    for (const [stat, value] of Object.entries(item.projected_ranges || {})) {
      const cell = node('div', 'range-card');
      cell.append(node('span', 'context-label', STAT_LABELS[stat] || stat));
      cell.append(node('strong', '', `${formatNumber(value.min)}–${formatNumber(value.max)}`));
      cell.append(node('small', 'subtle', `Expected ${formatNumber(value.ev)} · target ${formatNumber(value.target)}`));
      ranges.append(cell);
    }
    body.append(ranges);
    details.append(body);
    container.append(details);
  }
}

function renderDevelopment(brother) {
  const container = document.getElementById('development-list');
  clear(container);
  const best = brother.potential?.[0];
  if (!best) {
    container.append(node('p', 'subtle', 'Development trajectory is unavailable.'));
    return;
  }
  container.append(node('p', 'development-lead', `${best.role} · ${formatPct(best.fit_pct)} Best Fit`));
  const grid = node('div', 'range-grid');
  for (const [stat, value] of Object.entries(best.projected_ranges || {})) {
    const card = node('div', 'range-card');
    card.append(node('span', 'context-label', STAT_LABELS[stat] || stat));
    card.append(node('strong', '', `${formatNumber(value.min)}–${formatNumber(value.max)}`));
    card.append(node('small', 'subtle', `Expected ${formatNumber(value.ev)} · baseline ${formatNumber(value.baseline)} · target ${formatNumber(value.target)}`));
    grid.append(card);
  }
  container.append(grid);
}

function assignmentLabel(assignment) {
  if (!assignment) return 'Unavailable';
  if (assignment.status === 'unassigned') return 'Unassigned';
  if (assignment.display_name) return assignment.display_name;
  if (assignment.build_identity) return `${assignment.build_identity} · ${humanize(assignment.status)}`;
  return humanize(assignment.status);
}

function populateAssignmentSelect(brother) {
  const select = document.getElementById('assigned-build-select');
  clear(select);
  const empty = node('option', '', 'Unassigned');
  empty.value = '';
  select.append(empty);
  const knownIds = new Set();
  for (const build of state.companyData?.builds || []) {
    const option = node('option', '', build.display_name);
    option.value = build.build_identity;
    knownIds.add(build.build_identity);
    select.append(option);
  }
  const assignment = brother.assigned_build || {};
  if (assignment.build_identity && !knownIds.has(assignment.build_identity)) {
    const missing = node('option', '', `${assignment.build_identity} · ${humanize(assignment.status)}`);
    missing.value = assignment.build_identity;
    missing.disabled = true;
    select.append(missing);
  }
  select.value = assignment.build_identity || '';
  const current = freshnessFromState()?.status === 'current';
  select.disabled = state.mutatingAssignment || !brother.assignment_address || !current;

  const status = document.getElementById('assignment-status');
  const parts = [assignmentLabel(assignment)];
  if (!brother.assignment_address) parts.push('exact durable identity unavailable');
  else if (!current) parts.push('wait for current analysis before changing intent');
  else if (assignment.status === 'definition_changed') parts.push('definition changed; selecting this build again acknowledges the current definition');
  status.textContent = parts.join(' · ');
  status.dataset.state = assignment.status || 'unavailable';
}

function renderBrother(brotherId, section = 'current') {
  const brother = brotherById(brotherId);
  if (!brother) {
    if (state.companyData?.available) {
      history.replaceState(null, '', '#company');
      document.getElementById('brother-view').hidden = true;
      document.getElementById('company-view').hidden = false;
      renderCompany();
    }
    return;
  }
  document.getElementById('company-view').hidden = true;
  const view = document.getElementById('brother-view');
  view.hidden = false;

  document.getElementById('brother-name').textContent = brother.snapshot?.Name || brother.brother_id;
  document.getElementById('brother-meta').textContent = `Lv ${brother.snapshot?.Level ?? '—'} · ${brother.snapshot?.Background || 'Unknown background'} · ${brother.best_fit?.category || 'Unclassified'}`;
  document.getElementById('brother-context').textContent = brother.brother_identity?.confidence === 'exact' ? 'Stable Brother context' : 'Brother context';
  document.getElementById('best-fit-role').textContent = brother.best_fit?.role || '—';
  document.getElementById('best-fit-score').textContent = `${formatPct(brother.best_fit?.fit_pct)} · likely ${formatPct(brother.best_fit?.likely_min_pct)}–${formatPct(brother.best_fit?.likely_max_pct)}`;

  const switcher = document.getElementById('brother-select');
  clear(switcher);
  for (const item of state.companyData.brothers) {
    const option = node('option', '', item.snapshot?.Name || item.brother_id);
    option.value = item.brother_id;
    switcher.append(option);
  }
  switcher.value = brother.brother_id;
  populateAssignmentSelect(brother);
  renderStats(brother.snapshot);
  renderChipList('brother-perks', brother.snapshot?.Perks, 'No perks recorded.');
  renderChipList('brother-traits', brother.snapshot?.Traits, 'No traits recorded.');
  renderChipList('brother-injuries', brother.snapshot?.Injuries, 'No injuries recorded.');
  renderGear(brother.snapshot);
  renderMechanics(brother.mechanical_facts);
  renderPotential(brother.potential);
  renderDevelopment(brother);

  document.querySelectorAll('[data-brother-section]').forEach((link) => {
    const active = link.dataset.brotherSection === section;
    if (active) link.setAttribute('aria-current', 'location');
    else link.removeAttribute('aria-current');
    link.href = brotherHash(brother.brother_id, link.dataset.brotherSection);
  });

  requestAnimationFrame(() => {
    const target = document.getElementById(`brother-${section}`);
    if (target && routeFromHash().brotherId === brother.brother_id) {
      target.scrollIntoView({block: 'start'});
    }
  });
}

function renderCompanyRoute(route) {
  if (route.brotherId) {
    if (state.companyData?.available) renderBrother(route.brotherId, route.section);
    return;
  }
  document.getElementById('brother-view').hidden = true;
  document.getElementById('company-view').hidden = false;
  renderCompany();
}

async function loadCompanyData() {
  try {
    const payload = await fetchData('/api/v1/company-brother');
    state.companyData = payload;
    renderCompanyRoute(routeFromHash());
  } catch (_error) {
    const loading = document.getElementById('company-loading');
    loading.hidden = false;
    loading.textContent = 'Company data is temporarily unavailable.';
  }
}

async function refreshAnalysisAfterAssignment() {
  const preferences = await fetchData('/api/v1/followed-save');
  if (!preferences.selected_path) return false;
  await postData('/api/v1/analysis/jobs', {
    expected_preferences_revision: preferences.revision,
  });
  return true;
}

async function changeAssignedBuild() {
  const route = routeFromHash();
  const brother = brotherById(route.brotherId);
  if (!brother?.assignment_address || state.mutatingAssignment) return;
  const select = document.getElementById('assigned-build-select');
  const requested = select.value;
  const old = brother.assigned_build || {};
  if ((old.build_identity || '') === requested && old.status !== 'definition_changed') return;

  state.mutatingAssignment = true;
  populateAssignmentSelect(brother);
  const status = document.getElementById('assignment-status');
  status.textContent = 'Saving Assigned Build…';
  let feedback = null;
  try {
    const operation = requested ? (old.build_identity ? 'change' : 'assign') : 'clear';
    const payload = {
      ...brother.assignment_address,
      expected_revision: state.companyData.assignment_revision,
    };
    if (requested) payload.build_identity = requested;
    const result = await postData(`/api/v1/assigned-builds/${operation}`, payload);
    state.companyData.assignment_revision = result.revision;
    brother.assigned_build = result.assignment;
    state.companyData.company.intent_fresh = false;
    if (state.result?.available) {
      state.result.freshness = {status: 'stale', reason: 'assigned_build_changed'};
    }
    renderFreshness();
    renderPlanning();

    try {
      const started = await refreshAnalysisAfterAssignment();
      feedback = started
        ? `${assignmentLabel(result.assignment)} · saved; refreshing intent-aware analysis`
        : `${assignmentLabel(result.assignment)} · saved; no selected save is available to refresh`;
    } catch (refreshError) {
      feedback = `${assignmentLabel(result.assignment)} · saved; refresh could not start: ${refreshError.message}`;
    }
  } catch (error) {
    feedback = error.code === 'state_revision_conflict'
      ? 'Assigned Build changed elsewhere; reloading current state.'
      : `Assigned Build was not changed: ${error.message}`;
    await loadCompanyData();
  } finally {
    state.mutatingAssignment = false;
    const current = brotherById(route.brotherId);
    if (current) populateAssignmentSelect(current);
    if (feedback) status.textContent = feedback;
  }
}

async function refreshApplicationState() {
  const previousStatus = freshnessFromState()?.status;
  try {
    const shell = await fetchData('/api/v1/shell');
    state.followedSave = shell.followed_save;
    state.result = shell.result;
    state.analysisHealth = shell.analysis_health;
    state.activeJob = shell.active_job;
    renderShell();
    const currentStatus = freshnessFromState()?.status;
    if (state.result?.available && (!state.companyData || (currentStatus === 'current' && previousStatus !== 'current'))) {
      await loadCompanyData();
    }
  } catch (_error) {
    const status = document.getElementById('freshness-status');
    status.dataset.state = 'unavailable';
    status.textContent = 'Local service unavailable';
    document.getElementById('progress-region').hidden = true;
  }
}

function updateShellHeight() {
  const shell = document.querySelector('[data-app-shell]');
  document.documentElement.style.setProperty('--app-shell-height', `${Math.ceil(shell.getBoundingClientRect().height)}px`);
}

window.addEventListener('hashchange', () => selectWorkspace(routeFromHash()));
window.addEventListener('resize', updateShellHeight);

document.addEventListener('DOMContentLoaded', () => {
  selectWorkspace(routeFromHash());
  updateShellHeight();

  const shell = document.querySelector('[data-app-shell]');
  if ('ResizeObserver' in window) new ResizeObserver(updateShellHeight).observe(shell);

  const healthButton = document.getElementById('health-button');
  const healthPanel = document.getElementById('health-panel');
  healthButton.addEventListener('click', () => {
    const open = healthButton.getAttribute('aria-expanded') === 'true';
    healthButton.setAttribute('aria-expanded', String(!open));
    healthPanel.hidden = open;
  });

  document.querySelectorAll('[data-company-view]').forEach((button) => {
    button.addEventListener('click', () => setCompanySubview(button.dataset.companyView));
  });
  document.getElementById('roster-search').addEventListener('input', (event) => {
    state.companySearch = event.target.value;
    renderCompanySubview();
  });
  document.getElementById('back-to-company').addEventListener('click', returnToCompany);
  document.getElementById('brother-select').addEventListener('change', (event) => {
    const route = routeFromHash();
    window.location.hash = brotherHash(event.target.value, route.section);
  });
  document.getElementById('assigned-build-select').addEventListener('change', changeAssignedBuild);

  refreshApplicationState();
  window.setInterval(refreshApplicationState, 1000);
});
