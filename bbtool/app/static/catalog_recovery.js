'use strict';

(() => {
  let catalog = null;
  let token = null;
  let rendering = false;

  async function getCatalog() {
    const response = await fetch('/api/v1/archetypes', {
      credentials: 'same-origin',
      cache: 'no-store',
      headers: {Accept: 'application/json'},
    });
    const payload = await response.json();
    if (!response.ok || payload.error) {
      const error = new Error(payload.error?.message || `Request failed (${response.status})`);
      error.code = payload.error?.code;
      throw error;
    }
    return payload.data;
  }

  async function getSession() {
    const response = await fetch('/api/v1/session', {
      credentials: 'same-origin',
      cache: 'no-store',
      headers: {Accept: 'application/json'},
    });
    const payload = await response.json();
    if (!response.ok || payload.error) {
      throw new Error(payload.error?.message || `Request failed (${response.status})`);
    }
    return payload.data.token;
  }

  async function resetBase(identity, expectedRevision, retrySession = true) {
    if (!token) token = await getSession();
    const response = await fetch('/api/v1/archetypes/reset-base', {
      method: 'POST',
      credentials: 'same-origin',
      cache: 'no-store',
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/json',
        'X-BBST-Session': token,
      },
      body: JSON.stringify({id: identity, expected_revision: expectedRevision}),
    });
    const payload = await response.json();
    if (!response.ok || payload.error) {
      if (payload.error?.code === 'invalid_session' && retrySession) {
        token = null;
        return resetBase(identity, expectedRevision, false);
      }
      const error = new Error(payload.error?.message || `Request failed (${response.status})`);
      error.code = payload.error?.code;
      throw error;
    }
    return payload.data;
  }

  function announce(message, kind = '') {
    const status = document.getElementById('local-app-status');
    if (!status) return;
    status.textContent = message;
    status.dataset.state = kind;
  }

  function humanize(value) {
    return String(value || '').replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
  }

  function conflictEntries() {
    return catalog?.catalog_conflict?.entries || [];
  }

  async function recover(conflict) {
    const expectedRevision = catalog.revision;
    try {
      catalog = await resetBase(conflict.id, expectedRevision);
      announce(`Reset ${conflict.id} to the current shipped definition at archetype revision ${catalog.revision}.`, 'success');
      const reload = document.getElementById('local-archetype-refresh');
      if (reload) reload.click();
    } catch (error) {
      if (error.code === 'state_revision_conflict' || error.code === 'catalog_conflict') {
        try {
          catalog = await getCatalog();
          renderRecovery();
        } catch (_reloadError) {
          // Keep the mutation failure as the actionable message.
        }
        announce('Archetype state changed elsewhere. Reloaded the authoritative recovery revision; review and retry.', 'error');
        return;
      }
      announce(`Could not reset ${conflict.id}: ${error.message}`, 'error');
    }
  }

  function renderRecovery() {
    const entries = conflictEntries();
    const container = document.getElementById('local-archetype-list');
    const summary = document.getElementById('local-archetype-summary');
    if (!container || !summary || !entries.length || rendering) return;
    if (container.querySelector('[data-catalog-recovery]')?.dataset.revision === String(catalog.revision)) {
      return;
    }

    rendering = true;
    try {
      container.replaceChildren();
      summary.textContent = `Catalog conflict · authoritative revision ${catalog.revision} · effective builds are unavailable until user intent is recovered`;
      for (const conflict of entries) {
        const row = document.createElement('article');
        row.className = 'coverage-card';
        row.dataset.catalogRecovery = 'true';
        row.dataset.revision = String(catalog.revision);

        const head = document.createElement('div');
        head.className = 'coverage-head';
        const identity = document.createElement('div');
        const title = document.createElement('strong');
        title.textContent = 'Shipped build conflict';
        const detail = document.createElement('small');
        detail.className = 'subtle';
        detail.textContent = `${conflict.id} · ${humanize(conflict.reason)}`;
        identity.append(title, detail);
        head.append(identity);
        row.append(head);

        const evidence = document.createElement('p');
        evidence.className = 'subtle';
        evidence.textContent = (conflict.errors || []).join('; ') || 'Persisted user intent no longer validates against the shipped catalog.';
        row.append(evidence);

        if (conflict.recovery_operation === 'reset_base') {
          const actions = document.createElement('div');
          actions.className = 'chip-list';
          const reset = document.createElement('button');
          reset.className = 'btn';
          reset.type = 'button';
          reset.textContent = 'Reset shipped';
          reset.addEventListener('click', () => recover(conflict));
          actions.append(reset);
          row.append(actions);
        }
        container.append(row);
      }
    } finally {
      rendering = false;
    }
  }

  async function refreshRecovery() {
    try {
      catalog = await getCatalog();
      renderRecovery();
    } catch (_error) {
      // The primary local-app code owns ordinary load failures.
    }
  }

  function install() {
    const container = document.getElementById('local-archetype-list');
    if (container) {
      new MutationObserver(() => renderRecovery()).observe(container, {childList: true});
    }
    document.addEventListener('click', (event) => {
      const target = event.target.closest?.('#local-app-trigger, #local-app-flow-manage, #local-archetype-refresh');
      if (target) window.setTimeout(refreshRecovery, 0);
    });
    refreshRecovery();
  }

  document.addEventListener('DOMContentLoaded', install);
})();
