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
  loadedJobId: null,
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
  updateBrotherMutationAvailability();
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

function updateBrotherMutationAvailability() {
  const route = routeFromHash();
  if (route.workspace !== 'company' || !route.brotherId || !state.companyData?.available) return;
  const brother = brotherById(route.brotherId);
  if (!brother) return;
  const select = document.getElementById('assigned-build-select');
  const current = freshnessFromState()?.status === 'current';
  select.disabled = state.mutatingAssignment || !brother.assignment_address || !current;
  if (!current && !state.mutatingAssignment) {
    const status = document.getElementById('assignment-status');
    status.textContent = `${assignmentLabel(brother.assigned_build)} · wait for current analysis before changing intent`;
  }
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
    state.loadedJobId = state.activeJob?.id ?? null;
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
    const publishedJobChanged = currentStatus === 'current'
      && state.activeJob?.id != null
      && state.loadedJobId !== state.activeJob.id;
    if (state.result?.available && (
      !state.companyData
      || (currentStatus === 'current' && previousStatus !== 'current')
      || publishedJobChanged
    )) {
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

(() => {
  const local = {
    token: null,
    followed: null,
    shell: null,
    catalog: null,
    busy: false,
    pendingInitialAnalysis: false,
    editorSave: null,
  };

  function localNode(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined && text !== null) element.textContent = String(text);
    return element;
  }

  async function localGet(path) {
    const response = await fetch(path, {
      credentials: 'same-origin',
      cache: 'no-store',
      headers: {Accept: 'application/json'},
    });
    const payload = await response.json();
    if (!response.ok || payload.error) {
      const error = new Error(payload.error?.message || `Request failed (${response.status})`);
      error.code = payload.error?.code;
      error.details = payload.error?.details;
      throw error;
    }
    return payload.data;
  }

  async function localPost(path, body, retrySession = true) {
    if (!local.token) local.token = (await localGet('/api/v1/session')).token;
    const response = await fetch(path, {
      method: 'POST',
      credentials: 'same-origin',
      cache: 'no-store',
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/json',
        'X-BBST-Session': local.token,
      },
      body: JSON.stringify(body),
    });
    const payload = await response.json();
    if (!response.ok || payload.error) {
      if (payload.error?.code === 'invalid_session' && retrySession) {
        local.token = null;
        return localPost(path, body, false);
      }
      const error = new Error(payload.error?.message || `Request failed (${response.status})`);
      error.code = payload.error?.code;
      error.details = payload.error?.details;
      throw error;
    }
    return payload.data;
  }

  function localErrorText(error) {
    if (Array.isArray(error.details) && error.details.length) {
      return `${error.message}: ${error.details.join('; ')}`;
    }
    return error.message || 'The local application operation failed.';
  }

  function announceLocal(message, kind = '') {
    const status = document.getElementById('local-app-status');
    if (!status) return;
    status.textContent = message;
    status.dataset.state = kind;
  }

  function selectedName(path) {
    if (!path) return null;
    const parts = String(path).split(/[\\/]/).filter(Boolean);
    return parts[parts.length - 1] || path;
  }

  function authoritativeFreshness() {
    return local.shell?.result?.freshness || local.followed?.freshness || {status: 'unavailable'};
  }

  function renderLocalFlow() {
    const flow = document.getElementById('local-app-flow');
    if (!flow || !local.followed) return;
    const title = document.getElementById('local-app-flow-title');
    const detail = document.getElementById('local-app-flow-detail');
    const run = document.getElementById('local-app-flow-run');
    const selected = local.followed.selected_path;
    const freshness = authoritativeFreshness();
    const status = freshness.status || 'unavailable';
    const resultAvailable = Boolean(local.shell?.result?.available);
    flow.dataset.state = status;
    run.hidden = true;

    if (!selected) {
      flow.hidden = false;
      flow.dataset.state = 'first-run';
      title.textContent = 'Choose a Battle Brothers save to begin';
      detail.textContent = 'The loopback service will remember the selected .sav path. No terminal command is required.';
      return;
    }
    if (!local.followed.available) {
      flow.hidden = false;
      title.textContent = 'Selected save is unavailable';
      detail.textContent = `${selected} · choose another save or forget this selection. A previous successful analysis is never relabelled as current.`;
      return;
    }
    if (resultAvailable && status === 'current') {
      flow.hidden = true;
      return;
    }

    flow.hidden = false;
    if (resultAvailable) {
      title.textContent = status === 'failed'
        ? 'Refresh failed — previous analysis is still visible'
        : `Analysis is not current · ${FRESHNESS_LABELS[status] || humanize(status)}`;
      detail.textContent = `${selectedName(selected)} · previous analytical output remains visible, but it is explicitly stale until a current generation publishes.`;
    } else {
      title.textContent = ['queued', 'analyzing'].includes(status)
        ? 'Preparing current analysis'
        : 'Save selected — analysis is not current yet';
      detail.textContent = `${selectedName(selected)} · the Target workspaces populate only from an authoritative successful publication.`;
    }
    run.hidden = ['queued', 'analyzing', 'stabilizing'].includes(status);
    run.disabled = local.busy;
  }

  function renderSavePanel() {
    if (!local.followed) return;
    const input = document.getElementById('local-save-path');
    if (document.activeElement !== input) input.value = local.followed.selected_path || '';
    document.getElementById('local-save-auto').checked = Boolean(local.followed.auto_refresh);
    const stateLabel = local.followed.selected_path
      ? (local.followed.available ? 'Available' : 'Unavailable')
      : 'No save selected';
    document.getElementById('local-save-summary').textContent = `${stateLabel} · preferences revision ${local.followed.revision} · ${local.followed.freshness?.status || 'unavailable'}`;
    document.getElementById('local-save-forget').disabled = local.busy || !local.followed.selected_path;
    document.getElementById('local-save-run').disabled = local.busy || !local.followed.available;
    document.getElementById('local-save-select').disabled = local.busy;
  }

  function catalogEntry(kind, id) {
    return (local.catalog?.user_entries || []).find((entry) => {
      if (entry.kind !== kind) return false;
      return kind === 'custom' ? entry.definition?.id === id : entry.id === id;
    }) || null;
  }

  function cleanDefinition(role) {
    const copy = JSON.parse(JSON.stringify(role));
    delete copy.id;
    for (const stat of Object.values(copy.stats || {})) {
      if (stat && typeof stat === 'object') {
        delete stat.fit;
        delete stat.projected_curve;
      }
    }
    return copy;
  }

  function localButton(text, callback, className = 'btn') {
    const button = localNode('button', className, text);
    button.type = 'button';
    button.disabled = local.busy;
    button.addEventListener('click', callback);
    return button;
  }

  function openCatalogEditor(title, value, save) {
    document.getElementById('local-editor-title').textContent = title;
    document.getElementById('local-editor-json').value = JSON.stringify(value, null, 2);
    document.getElementById('local-editor').hidden = false;
    local.editorSave = save;
    document.getElementById('local-editor-json').focus();
  }

  function closeCatalogEditor() {
    document.getElementById('local-editor').hidden = true;
    local.editorSave = null;
  }

  function renderCatalog() {
    const container = document.getElementById('local-archetype-list');
    if (!container || !local.catalog) return;
    container.replaceChildren();
    document.getElementById('local-archetype-summary').textContent = `${local.catalog.roles.length} effective build${local.catalog.roles.length === 1 ? '' : 's'} · catalog revision ${local.catalog.revision}`;
    const visible = new Set();

    for (const role of local.catalog.roles) {
      visible.add(role.id);
      const provenance = local.catalog.provenance?.[role.id] || 'base';
      const row = localNode('article', 'coverage-card');
      const head = localNode('div', 'coverage-head');
      const identity = localNode('div');
      identity.append(localNode('strong', '', role.name || role.id));
      identity.append(localNode('small', 'subtle', `${role.id} · ${provenance.replaceAll('_', ' ')}`));
      head.append(identity);
      row.append(head);
      const actions = localNode('div', 'chip-list');

      if (provenance === 'user_custom') {
        actions.append(localButton('Edit', () => openCatalogEditor(
          `Edit ${role.name}`,
          cleanDefinition(role),
          (documentValue) => mutateCatalog('edit_custom', {id: role.id, definition: documentValue}, `Updated ${role.name}`),
        )));
        actions.append(localButton('Duplicate', () => mutateCatalog('duplicate', {id: role.id}, `Duplicated ${role.name}`)));
        actions.append(localButton('Delete', () => mutateCatalog('delete_custom', {id: role.id}, `Deleted ${role.name}`)));
      } else {
        const override = catalogEntry('override', role.id);
        actions.append(localButton(override ? 'Edit override' : 'Override', () => openCatalogEditor(
          `${override ? 'Edit' : 'Create'} override · ${role.name}`,
          override?.patch || {name: role.name},
          (patch) => mutateCatalog('set_override', {id: role.id, patch}, `Updated override for ${role.name}`),
        )));
        if (override) {
          actions.append(localButton('Reset override', () => mutateCatalog('reset_override', {id: role.id}, `Reset override for ${role.name}`)));
        }
        actions.append(localButton('Duplicate', () => mutateCatalog('duplicate', {id: role.id}, `Duplicated ${role.name}`)));
        actions.append(localButton('Disable', () => mutateCatalog('set_disabled', {id: role.id, disabled: true}, `Disabled ${role.name}`)));
      }
      row.append(actions);
      container.append(row);
    }

    for (const entry of local.catalog.user_entries || []) {
      if (entry.kind !== 'disabled' || visible.has(entry.id)) continue;
      const row = localNode('article', 'coverage-card');
      const head = localNode('div', 'coverage-head');
      head.append(localNode('strong', '', 'Disabled shipped build'));
      head.append(localNode('small', 'subtle', entry.id));
      row.append(head);
      const actions = localNode('div', 'chip-list');
      actions.append(localButton('Enable', () => mutateCatalog('set_disabled', {id: entry.id, disabled: false}, `Enabled ${entry.id}`)));
      actions.append(localButton('Reset shipped', () => mutateCatalog('reset_base', {id: entry.id}, `Reset ${entry.id} to shipped definition`)));
      row.append(actions);
      container.append(row);
    }
  }

  async function refreshLocalAuthority(renderDialog = false) {
    try {
      const [followed, shell] = await Promise.all([
        localGet('/api/v1/followed-save'),
        localGet('/api/v1/shell'),
      ]);
      local.followed = followed;
      local.shell = shell;
      renderLocalFlow();
      if (renderDialog) renderSavePanel();
      if (
        local.pendingInitialAnalysis
        && followed.selected_path
        && followed.available
        && followed.freshness?.status === 'detected'
      ) {
        local.pendingInitialAnalysis = false;
        await requestLocalAnalysis('Save selection persisted and initial analysis requested.');
      }
    } catch (_error) {
      const flow = document.getElementById('local-app-flow');
      if (!flow) return;
      flow.hidden = false;
      flow.dataset.state = 'unavailable';
      document.getElementById('local-app-flow-title').textContent = 'Local application service unavailable';
      document.getElementById('local-app-flow-detail').textContent = 'Durable changes cannot be made or confirmed until the loopback service is reachable.';
    }
  }

  async function loadCatalog() {
    local.catalog = await localGet('/api/v1/archetypes');
    renderCatalog();
  }

  async function requestLocalAnalysis(successMessage = 'Analysis request accepted by the local service.') {
    if (!local.followed?.selected_path) {
      announceLocal('Choose a save before requesting analysis.', 'error');
      return false;
    }
    try {
      await localPost('/api/v1/analysis/jobs', {
        expected_preferences_revision: local.followed.revision,
      });
      announceLocal(successMessage, 'success');
      await refreshLocalAuthority(true);
      return true;
    } catch (error) {
      if (error.code === 'selected_save_stabilizing') {
        local.pendingInitialAnalysis = true;
        announceLocal('The save selection is persisted. Waiting for the file to become stable before analysis starts.', 'success');
        return false;
      }
      if (error.code === 'state_revision_conflict') {
        await refreshLocalAuthority(true);
        announceLocal('Save preferences changed elsewhere. Reloaded authoritative state; retry the analysis request.', 'error');
        return false;
      }
      announceLocal(`Analysis did not start: ${localErrorText(error)}`, 'error');
      return false;
    }
  }

  async function selectLocalSave() {
    if (local.busy) return;
    const input = document.getElementById('local-save-path');
    const requestedPath = input.value.trim();
    const autoRefresh = document.getElementById('local-save-auto').checked;
    if (!requestedPath) {
      announceLocal('Enter the full path to an existing .sav file.', 'error');
      input.focus();
      return;
    }
    local.busy = true;
    renderSavePanel();
    try {
      local.followed = await localPost('/api/v1/followed-save/select', {
        path: requestedPath,
        expected_revision: local.followed.revision,
        auto_refresh: autoRefresh,
      });
      announceLocal('Save selection persisted by the local service.', 'success');
      local.pendingInitialAnalysis = !autoRefresh;
      renderSavePanel();
      await refreshLocalAuthority(true);
      if (
        !autoRefresh
        && local.pendingInitialAnalysis
        && local.followed.freshness?.status !== 'stabilizing'
      ) {
        local.pendingInitialAnalysis = false;
        await requestLocalAnalysis('Save selection persisted and initial analysis requested.');
      }
    } catch (error) {
      if (error.code === 'state_revision_conflict') {
        await refreshLocalAuthority(true);
        input.value = requestedPath;
        document.getElementById('local-save-auto').checked = autoRefresh;
        announceLocal('Save preferences changed elsewhere. Reloaded authoritative revision; review and retry your selection.', 'error');
      } else {
        announceLocal(`Save selection was not changed: ${localErrorText(error)}`, 'error');
      }
    } finally {
      local.busy = false;
      renderSavePanel();
      renderLocalFlow();
    }
  }

  async function forgetLocalSave() {
    if (local.busy || !local.followed?.selected_path) return;
    local.busy = true;
    renderSavePanel();
    try {
      local.followed = await localPost('/api/v1/followed-save/forget', {
        expected_revision: local.followed.revision,
      });
      local.pendingInitialAnalysis = false;
      announceLocal('Save selection was removed from authoritative user state.', 'success');
      await refreshLocalAuthority(true);
    } catch (error) {
      if (error.code === 'state_revision_conflict') {
        await refreshLocalAuthority(true);
        announceLocal('Save preferences changed elsewhere. Reloaded authoritative state; retry if needed.', 'error');
      } else {
        announceLocal(`Save selection was not forgotten: ${localErrorText(error)}`, 'error');
      }
    } finally {
      local.busy = false;
      renderSavePanel();
      renderLocalFlow();
    }
  }

  async function refreshAfterCatalogMutation(message) {
    await refreshLocalAuthority(true);
    if (!local.followed?.selected_path || !local.followed.available) {
      announceLocal(`${message} persisted. Choose an available save before recomputing analysis.`, 'success');
      return;
    }
    try {
      await localPost('/api/v1/analysis/jobs', {
        expected_preferences_revision: local.followed.revision,
      });
      announceLocal(`${message} persisted. Analysis refresh requested; old derived output remains stale until publication.`, 'success');
    } catch (error) {
      announceLocal(`${message} persisted, but analysis refresh did not start: ${localErrorText(error)}`, 'error');
    }
    await refreshLocalAuthority(true);
  }

  async function mutateCatalog(operation, payload, message) {
    if (local.busy || !local.catalog) return;
    local.busy = true;
    renderCatalog();
    const endpoint = operation.replaceAll('_', '-');
    try {
      local.catalog = await localPost(`/api/v1/archetypes/${endpoint}`, {
        ...payload,
        expected_revision: local.catalog.revision,
      });
      closeCatalogEditor();
      renderCatalog();
      await refreshAfterCatalogMutation(message);
    } catch (error) {
      if (error.code === 'state_revision_conflict' || error.code === 'catalog_conflict') {
        try {
          await loadCatalog();
        } catch (_reloadError) {
          // Preserve the original actionable conflict message.
        }
        announceLocal(`Archetype state changed elsewhere or conflicts with the shipped catalog. Reloaded authoritative state where possible: ${localErrorText(error)}`, 'error');
      } else {
        announceLocal(`Archetype change was not persisted: ${localErrorText(error)}`, 'error');
      }
    } finally {
      local.busy = false;
      renderCatalog();
    }
  }

  async function exportCatalog() {
    try {
      const result = await localGet('/api/v1/archetypes/export');
      document.getElementById('local-import-json').value = result.document;
      announceLocal('Authoritative user archetype state exported below. No analysis state is embedded.', 'success');
    } catch (error) {
      announceLocal(`Archetype export failed: ${localErrorText(error)}`, 'error');
    }
  }

  async function importCatalog(merge) {
    const documentText = document.getElementById('local-import-json').value;
    if (!documentText.trim()) {
      announceLocal('Paste an archetype export document before importing.', 'error');
      return;
    }
    await mutateCatalog(
      'import',
      {document: documentText, merge},
      merge ? 'Merged archetype import' : 'Replaced user archetype state from import',
    );
  }

  async function openLocalApplication() {
    const dialog = document.getElementById('local-app-dialog');
    if (typeof dialog.showModal === 'function') dialog.showModal();
    else dialog.setAttribute('open', '');
    announceLocal('Loading authoritative local application state.');
    try {
      const [followed, shell, catalog] = await Promise.all([
        localGet('/api/v1/followed-save'),
        localGet('/api/v1/shell'),
        localGet('/api/v1/archetypes'),
      ]);
      local.followed = followed;
      local.shell = shell;
      local.catalog = catalog;
      renderSavePanel();
      renderCatalog();
      renderLocalFlow();
      announceLocal('Authoritative local application state loaded.');
    } catch (error) {
      announceLocal(`Could not load local application state: ${localErrorText(error)}`, 'error');
    }
  }

  function installLocalApplication() {
    const trigger = localButton('Local app', openLocalApplication, 'health-button');
    trigger.id = 'local-app-trigger';
    trigger.setAttribute('aria-haspopup', 'dialog');
    trigger.setAttribute('aria-controls', 'local-app-dialog');
    document.querySelector('.run-context').append(trigger);

    const flow = localNode('section', 'card');
    flow.id = 'local-app-flow';
    flow.setAttribute('role', 'status');
    flow.setAttribute('aria-live', 'polite');
    flow.setAttribute('aria-atomic', 'true');
    const flowHead = localNode('div', 'card-head');
    const flowCopy = localNode('div');
    const flowTitle = localNode('strong');
    flowTitle.id = 'local-app-flow-title';
    const flowDetail = localNode('p', 'subtle');
    flowDetail.id = 'local-app-flow-detail';
    flowCopy.append(flowTitle, flowDetail);
    const flowActions = localNode('div', 'chip-list');
    const manage = localButton('Manage local app', openLocalApplication);
    manage.id = 'local-app-flow-manage';
    const run = localButton('Analyze now', () => requestLocalAnalysis());
    run.id = 'local-app-flow-run';
    flowActions.append(manage, run);
    flowHead.append(flowCopy, flowActions);
    flow.append(flowHead);
    document.getElementById('workspace').before(flow);

    const dialog = localNode('dialog', 'card');
    dialog.id = 'local-app-dialog';
    dialog.setAttribute('aria-labelledby', 'local-app-heading');
    dialog.innerHTML = `
      <div class="card-body">
        <div class="card-head">
          <div>
            <span class="eyebrow">Authoritative local state</span>
            <h2 id="local-app-heading">Local app</h2>
            <p class="subtle">The browser requests changes. The loopback service validates, persists, revisions, and returns authoritative state.</p>
          </div>
          <form method="dialog"><button class="btn" type="submit" aria-label="Close local app">Close</button></form>
        </div>
        <p id="local-app-status" class="intent-note" role="status" aria-live="polite" aria-atomic="true"></p>
        <div class="fact-columns">
          <section class="intent-card" aria-labelledby="local-save-heading">
            <span class="eyebrow">First run & recovery</span>
            <h3 id="local-save-heading">Followed save</h3>
            <p id="local-save-summary" class="subtle">Loading…</p>
            <label class="search-field">
              <span>Full path to Battle Brothers .sav file</span>
              <input id="local-save-path" type="text" spellcheck="false" autocomplete="off" placeholder="C:\\Users\\…\\save.sav">
            </label>
            <label><input id="local-save-auto" type="checkbox"> Automatically refresh after stable save changes</label>
            <div class="chip-list">
              <button id="local-save-select" class="btn" type="button">Save selection</button>
              <button id="local-save-run" class="btn" type="button">Analyze now</button>
              <button id="local-save-forget" class="btn" type="button">Forget selection</button>
            </div>
          </section>
          <section class="intent-card" aria-labelledby="local-archetype-heading">
            <span class="eyebrow">Persistent configuration</span>
            <h3 id="local-archetype-heading">Archetypes</h3>
            <p id="local-archetype-summary" class="subtle">Loading…</p>
            <div class="chip-list">
              <button id="local-archetype-new" class="btn" type="button">New custom build</button>
              <button id="local-archetype-refresh" class="btn" type="button">Reload authoritative state</button>
            </div>
            <div id="local-archetype-list" class="coverage-grid"></div>
          </section>
        </div>
        <section id="local-editor" class="intent-card" hidden aria-labelledby="local-editor-title">
          <h3 id="local-editor-title">Edit archetype</h3>
          <p class="subtle">JSON is submitted to the local service for authoritative validation. Base-build overrides are sparse patches; custom builds are complete definitions.</p>
          <label><span class="context-label">Definition / patch JSON</span><textarea id="local-editor-json" rows="12" cols="40" spellcheck="false"></textarea></label>
          <div class="chip-list"><button id="local-editor-save" class="btn" type="button">Validate & save</button><button id="local-editor-cancel" class="btn" type="button">Cancel</button></div>
        </section>
        <section class="intent-card" aria-labelledby="local-import-heading">
          <span class="eyebrow">Backup & transfer</span>
          <h3 id="local-import-heading">Import / export user archetypes</h3>
          <p class="subtle">Exports contain user-owned archetype state only. Replace and merge imports remain revision-checked durable mutations.</p>
          <label><span class="context-label">Archetype document</span><textarea id="local-import-json" rows="12" cols="40" spellcheck="false"></textarea></label>
          <div class="chip-list"><button id="local-export" class="btn" type="button">Export current state</button><button id="local-import-replace" class="btn" type="button">Replace from import</button><button id="local-import-merge" class="btn" type="button">Merge import</button></div>
        </section>
      </div>`;
    document.body.append(dialog);

    document.getElementById('local-save-select').addEventListener('click', selectLocalSave);
    document.getElementById('local-save-run').addEventListener('click', () => requestLocalAnalysis());
    document.getElementById('local-save-forget').addEventListener('click', forgetLocalSave);
    document.getElementById('local-archetype-refresh').addEventListener('click', async () => {
      try {
        await loadCatalog();
        announceLocal('Authoritative archetype state reloaded.');
      } catch (error) {
        announceLocal(`Could not reload archetypes: ${localErrorText(error)}`, 'error');
      }
    });
    document.getElementById('local-archetype-new').addEventListener('click', () => {
      if (!local.catalog?.roles?.length) return;
      const template = cleanDefinition(local.catalog.roles[0]);
      template.name = 'New Custom Build';
      openCatalogEditor(
        'Create custom build',
        template,
        (definition) => mutateCatalog('create_custom', {definition}, 'Created custom build'),
      );
    });
    document.getElementById('local-editor-save').addEventListener('click', async () => {
      if (!local.editorSave) return;
      let documentValue;
      try {
        documentValue = JSON.parse(document.getElementById('local-editor-json').value);
      } catch (error) {
        announceLocal(`JSON is not valid: ${error.message}`, 'error');
        return;
      }
      await local.editorSave(documentValue);
    });
    document.getElementById('local-editor-cancel').addEventListener('click', closeCatalogEditor);
    document.getElementById('local-export').addEventListener('click', exportCatalog);
    document.getElementById('local-import-replace').addEventListener('click', () => importCatalog(false));
    document.getElementById('local-import-merge').addEventListener('click', () => importCatalog(true));
    dialog.addEventListener('close', closeCatalogEditor);

    refreshLocalAuthority();
    window.setInterval(() => refreshLocalAuthority(false), 1000);
  }

  document.addEventListener('DOMContentLoaded', installLocalApplication);
})();
