'use strict';

// Additive local-application controls for the validated Target workspaces.
// Durable state and revisions remain authoritative in the loopback service.
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

  function localElement(tag, options = {}, ...children) {
    const element = localNode(tag, options.className, options.text);
    if (options.id) element.id = options.id;
    if (options.type) element.type = options.type;
    if (options.name) element.name = options.name;
    if (options.value !== undefined) element.value = options.value;
    if (options.hidden !== undefined) element.hidden = options.hidden;
    for (const [name, value] of Object.entries(options.attributes || {})) {
      element.setAttribute(name, value);
    }
    if (children.length) element.append(...children);
    return element;
  }

  function localStaticButton(id, text) {
    return localElement('button', {id, className: 'btn', text, type: 'button'});
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

  function renderCatalogConflict(container) {
    const conflicts = local.catalog?.catalog_conflict?.entries || [];
    if (!conflicts.length) return false;
    document.getElementById('local-archetype-summary').textContent = `Catalog conflict · authoritative revision ${local.catalog.revision} · effective builds are unavailable until user intent is recovered`;
    for (const conflict of conflicts) {
      const row = localNode('article', 'coverage-card');
      row.dataset.catalogRecovery = 'true';
      row.dataset.revision = String(local.catalog.revision);
      const head = localNode('div', 'coverage-head');
      const identity = localNode('div');
      identity.append(localNode('strong', '', 'Shipped build conflict'));
      identity.append(localNode('small', 'subtle', `${conflict.id} · ${humanize(conflict.reason)}`));
      head.append(identity);
      row.append(head);
      row.append(localNode(
        'p',
        'subtle',
        (conflict.errors || []).join('; ') || 'Persisted user intent no longer validates against the shipped catalog.',
      ));
      if (conflict.recovery_operation === 'reset_base') {
        const actions = localNode('div', 'chip-list');
        actions.append(localButton(
          'Reset shipped',
          () => mutateCatalog('reset_base', {id: conflict.id}, `Reset ${conflict.id} to shipped definition`),
        ));
        row.append(actions);
      }
      container.append(row);
    }
    return true;
  }

  function renderCatalog() {
    const container = document.getElementById('local-archetype-list');
    if (!container || !local.catalog) return;
    container.replaceChildren();
    if (renderCatalogConflict(container)) return;
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

  function buildLocalDialog() {
    const dialog = localElement('dialog', {
      id: 'local-app-dialog',
      className: 'card',
      attributes: {'aria-labelledby': 'local-app-heading'},
    });
    const body = localNode('div', 'card-body');

    const head = localNode('div', 'card-head');
    const headCopy = localNode('div');
    headCopy.append(
      localNode('span', 'eyebrow', 'Authoritative local state'),
      localElement('h2', {id: 'local-app-heading', text: 'Local app'}),
      localNode('p', 'subtle', 'The browser requests changes. The loopback service validates, persists, revisions, and returns authoritative state.'),
    );
    const closeForm = localElement('form', {attributes: {method: 'dialog'}});
    closeForm.append(localElement('button', {
      className: 'btn',
      text: 'Close',
      type: 'submit',
      attributes: {'aria-label': 'Close local app'},
    }));
    head.append(headCopy, closeForm);

    const status = localElement('p', {
      id: 'local-app-status',
      className: 'intent-note',
      attributes: {role: 'status', 'aria-live': 'polite', 'aria-atomic': 'true'},
    });

    const columns = localNode('div', 'fact-columns');
    const saveSection = localElement('section', {
      className: 'intent-card',
      attributes: {'aria-labelledby': 'local-save-heading'},
    });
    saveSection.append(
      localNode('span', 'eyebrow', 'First run & recovery'),
      localElement('h3', {id: 'local-save-heading', text: 'Followed save'}),
      localElement('p', {id: 'local-save-summary', className: 'subtle', text: 'Loading…'}),
    );
    const pathLabel = localNode('label', 'search-field');
    pathLabel.append(localNode('span', '', 'Full path to Battle Brothers .sav file'));
    pathLabel.append(localElement('input', {
      id: 'local-save-path',
      type: 'text',
      attributes: {spellcheck: 'false', autocomplete: 'off', placeholder: 'C:\\Users\\…\\save.sav'},
    }));
    const autoLabel = localNode('label');
    autoLabel.append(
      localElement('input', {id: 'local-save-auto', type: 'checkbox'}),
      document.createTextNode(' Automatically refresh after stable save changes'),
    );
    const saveActions = localNode('div', 'chip-list');
    saveActions.append(
      localStaticButton('local-save-select', 'Save selection'),
      localStaticButton('local-save-run', 'Analyze now'),
      localStaticButton('local-save-forget', 'Forget selection'),
    );
    saveSection.append(pathLabel, autoLabel, saveActions);

    const archetypeSection = localElement('section', {
      className: 'intent-card',
      attributes: {'aria-labelledby': 'local-archetype-heading'},
    });
    archetypeSection.append(
      localNode('span', 'eyebrow', 'Persistent configuration'),
      localElement('h3', {id: 'local-archetype-heading', text: 'Archetypes'}),
      localElement('p', {id: 'local-archetype-summary', className: 'subtle', text: 'Loading…'}),
    );
    const archetypeActions = localNode('div', 'chip-list');
    archetypeActions.append(
      localStaticButton('local-archetype-new', 'New custom build'),
      localStaticButton('local-archetype-refresh', 'Reload authoritative state'),
    );
    archetypeSection.append(
      archetypeActions,
      localElement('div', {id: 'local-archetype-list', className: 'coverage-grid'}),
    );
    columns.append(saveSection, archetypeSection);

    const editor = localElement('section', {
      id: 'local-editor',
      className: 'intent-card',
      hidden: true,
      attributes: {'aria-labelledby': 'local-editor-title'},
    });
    editor.append(
      localElement('h3', {id: 'local-editor-title', text: 'Edit archetype'}),
      localNode('p', 'subtle', 'JSON is submitted to the local service for authoritative validation. Base-build overrides are sparse patches; custom builds are complete definitions.'),
    );
    const editorLabel = localNode('label');
    editorLabel.append(
      localNode('span', 'context-label', 'Definition / patch JSON'),
      localElement('textarea', {
        id: 'local-editor-json',
        attributes: {rows: '12', cols: '40', spellcheck: 'false'},
      }),
    );
    const editorActions = localNode('div', 'chip-list');
    editorActions.append(
      localStaticButton('local-editor-save', 'Validate & save'),
      localStaticButton('local-editor-cancel', 'Cancel'),
    );
    editor.append(editorLabel, editorActions);

    const importSection = localElement('section', {
      className: 'intent-card',
      attributes: {'aria-labelledby': 'local-import-heading'},
    });
    importSection.append(
      localNode('span', 'eyebrow', 'Backup & transfer'),
      localElement('h3', {id: 'local-import-heading', text: 'Import / export user archetypes'}),
      localNode('p', 'subtle', 'Exports contain user-owned archetype state only. Replace and merge imports remain revision-checked durable mutations.'),
    );
    const importLabel = localNode('label');
    importLabel.append(
      localNode('span', 'context-label', 'Archetype document'),
      localElement('textarea', {
        id: 'local-import-json',
        attributes: {rows: '12', cols: '40', spellcheck: 'false'},
      }),
    );
    const importActions = localNode('div', 'chip-list');
    importActions.append(
      localStaticButton('local-export', 'Export current state'),
      localStaticButton('local-import-replace', 'Replace from import'),
      localStaticButton('local-import-merge', 'Merge import'),
    );
    importSection.append(importLabel, importActions);

    body.append(head, status, columns, editor, importSection);
    dialog.append(body);
    return dialog;
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

    const dialog = buildLocalDialog();
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
