'use strict';

const WORKSPACES = ['company', 'level-up', 'recruitment'];
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

const state = {
  followedSave: null,
  result: null,
  analysisHealth: null,
  activeJob: null,
};

function requestedWorkspace() {
  const value = window.location.hash.slice(1).toLowerCase();
  return WORKSPACES.includes(value) ? value : 'company';
}

function selectWorkspace(workspace) {
  const selected = WORKSPACES.includes(workspace) ? workspace : 'company';
  document.querySelectorAll('[data-workspace]').forEach((link) => {
    if (link.dataset.workspace === selected) {
      link.setAttribute('aria-current', 'page');
    } else {
      link.removeAttribute('aria-current');
    }
  });
  document.querySelectorAll('[data-workspace-panel]').forEach((panel) => {
    panel.hidden = panel.dataset.workspacePanel !== selected;
  });
  document.title = `${WORKSPACE_LABELS[selected]} · Battle Brothers Save Toolkit`;

  if (window.location.hash !== `#${selected}`) {
    history.replaceState(null, '', `#${selected}`);
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
    element.title = freshness.reason.replaceAll('_', ' ');
  } else {
    element.removeAttribute('title');
  }
}

function renderFollowedSave() {
  const element = document.getElementById('save-label');
  const followed = state.followedSave;
  if (!followed?.selected_path) {
    element.textContent = 'No save selected';
    element.removeAttribute('title');
    return;
  }
  element.textContent = followed.name || 'Selected save';
  element.title = followed.name || 'Selected save';
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

function humanizeStage(stage) {
  return String(stage || 'analysis')
    .replaceAll('_', ' ')
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
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
  const events = job?.progress || [];
  const latest = events.at(-1);
  const label = document.getElementById('progress-label');
  const detail = document.getElementById('progress-detail');

  if (latest) {
    label.textContent = humanizeStage(latest.stage);
    detail.textContent = `${events.length} completed stage${events.length === 1 ? '' : 's'}`;
  } else {
    label.textContent = FRESHNESS_LABELS[freshness?.status] || 'Analysis in progress';
    detail.textContent = job?.status === 'queued' ? 'Waiting for analysis worker' : '';
  }
}

function render() {
  renderFollowedSave();
  renderFreshness();
  renderHealth();
  renderProgress();
}

async function refreshApplicationState() {
  try {
    const shell = await fetchData('/api/v1/shell');
    state.followedSave = shell.followed_save;
    state.result = shell.result;
    state.analysisHealth = shell.analysis_health;
    state.activeJob = shell.active_job;
    render();
  } catch (_error) {
    const status = document.getElementById('freshness-status');
    status.dataset.state = 'unavailable';
    status.textContent = 'Local service unavailable';
    document.getElementById('progress-region').hidden = true;
  }
}

window.addEventListener('hashchange', () => selectWorkspace(requestedWorkspace()));

document.addEventListener('DOMContentLoaded', () => {
  selectWorkspace(requestedWorkspace());

  const healthButton = document.getElementById('health-button');
  const healthPanel = document.getElementById('health-panel');
  healthButton.addEventListener('click', () => {
    const open = healthButton.getAttribute('aria-expanded') === 'true';
    healthButton.setAttribute('aria-expanded', String(!open));
    healthPanel.hidden = open;
  });

  refreshApplicationState();
  window.setInterval(refreshApplicationState, 1000);
});
