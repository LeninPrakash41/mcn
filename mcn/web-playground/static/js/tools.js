// ── Workspace Switching & Redesign ──────────────────────────────────────────
let _activeWorkspace = 'react';

// ── DB, IoT, and AI Trace Helper Functions ────────────────────────────────
// ── Database explorer: a tree of tables, a table's schema on click, and a SQL console ──

let _dbSchema = []
let _dbOpen = new Set()          // tables expanded in the tree
let _dbSelected = ''

const _DB_ICONS = {
  db: '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5"/><path d="M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3"/></svg>',
  table: '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 10h18M9 10v10"/></svg>',
  key: '<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><circle cx="8" cy="15" r="4"/><path d="M11 12l9-9M17 6l3 3"/></svg>',
  col: '<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 7h16M4 12h10M4 17h7"/></svg>',
}

async function refreshDBTables() {
  const tree = document.getElementById('db-tables-list')
  if (!tree) return
  try {
    const d = await apiFetch('/api/db/schema').then(r => r.json())
    if (!d.success) throw new Error(d.error || 'Could not read the database')
    _dbSchema = d.schema || []
  } catch (e) {
    tree.innerHTML = `<div class="pane-empty dbx-error">${escapeHtml(e.message)}</div>`
    return
  }
  renderDBTree()
  if (_dbSelected && _dbSchema.some(t => t.table === _dbSelected)) selectDBTable(_dbSelected)
  else { _dbSelected = ''; document.getElementById('db-table-detail').hidden = true }
}

function renderDBTree() {
  const tree = document.getElementById('db-tables-list')
  if (!_dbSchema.length) {
    tree.innerHTML = '<div class="pane-empty">No tables yet. They appear once your backend runs a CREATE TABLE.</div>'
    return
  }
  const mine = _dbSchema.filter(t => t.in_app), other = _dbSchema.filter(t => !t.in_app)
  const group = (label, tables, note) => tables.length ? `
    <div class="dbx-group">${escapeHtml(label)} <span class="dbx-count">${tables.length}</span>${note ? `<span class="dbx-note">${escapeHtml(note)}</span>` : ''}</div>
    ${tables.map(tableNode).join('')}` : ''
  tree.innerHTML = `
    <div class="dbx-root">${_DB_ICONS.db}<span>mcn_data.db</span></div>
    ${group(mine.length ? 'Tables in this app' : 'Tables', mine.length ? mine : other, '')}
    ${mine.length ? group('Other tables', other, 'left by other templates') : ''}`
}

function tableNode(t) {
  const open = _dbOpen.has(t.table), name = escapeHtml(t.table)
  const cols = open ? `<div class="dbx-cols" role="group">${t.columns.map(c => `
      <div class="dbx-col" title="${escapeHtml(c.name)} ${escapeHtml(c.type)}${c.pk ? ' · primary key' : ''}${c.notnull ? ' · required' : ''}">
        <span class="dbx-col-icon${c.pk ? ' pk' : ''}">${c.pk ? _DB_ICONS.key : _DB_ICONS.col}</span>
        <span class="dbx-col-name">${escapeHtml(c.name)}</span>
        <span class="dbx-col-type">${escapeHtml((c.type || 'any').toLowerCase())}</span>
      </div>`).join('')}</div>` : ''
  return `
    <div class="dbx-table${t.table === _dbSelected ? ' selected' : ''}" role="treeitem" aria-expanded="${open}" tabindex="0"
         data-table="${name}" onclick="selectDBTable(this.dataset.table)" onkeydown="if(event.key==='Enter')selectDBTable(this.dataset.table)">
      <span class="dbx-caret${open ? ' open' : ''}" onclick="event.stopPropagation(); toggleDBTable(this.parentElement.dataset.table)">›</span>
      <span class="dbx-icon">${_DB_ICONS.table}</span>
      <span class="dbx-name">${name}</span>
      <span class="dbx-rows">${t.rows} row${t.rows === 1 ? '' : 's'}</span>
    </div>${cols}`
}

function toggleDBTable(name) {
  _dbOpen.has(name) ? _dbOpen.delete(name) : _dbOpen.add(name)
  renderDBTree()
}

function selectDBTable(name) {
  const t = _dbSchema.find(x => x.table === name)
  if (!t) return
  _dbSelected = name
  renderDBTree()
  const q = _sqlName(name)
  const box = document.getElementById('db-table-detail')
  box.hidden = false
  box.innerHTML = `
    <div class="dbx-detail-head">
      <div><div class="dbx-detail-title">${_DB_ICONS.table}${escapeHtml(name)}</div>
        <div class="dbx-detail-sub">${t.columns.length} column${t.columns.length === 1 ? '' : 's'} · ${t.rows} row${t.rows === 1 ? '' : 's'}${t.in_app ? '' : ' · not created by this app'}</div></div>
      <div class="dbx-detail-actions">
        <button class="btn btn-sm" onclick="dbWriteQuery()">Write a query</button>
        <button class="btn btn-primary btn-sm" onclick="dbShowRows()">Show rows</button>
      </div>
    </div>
    <table class="dbx-grid dbx-schema">
      <thead><tr><th>Column</th><th>Type</th><th>Required</th><th>Default</th></tr></thead>
      <tbody>${t.columns.map(c => `<tr>
        <td><span class="dbx-col-icon${c.pk ? ' pk' : ''}">${c.pk ? _DB_ICONS.key : ''}</span>${escapeHtml(c.name)}</td>
        <td class="dbx-muted">${escapeHtml(c.type || 'any')}</td>
        <td class="dbx-muted">${c.pk || c.notnull ? 'yes' : ''}</td>
        <td class="dbx-muted">${c.default === null || c.default === undefined ? '' : escapeHtml(String(c.default))}</td></tr>`).join('')}</tbody>
    </table>`
  box.dataset.sqlName = q
}

function _sqlName(name) {
  return /^[A-Za-z_][A-Za-z0-9_]*$/.test(name) ? name : '"' + name.replace(/"/g, '""') + '"'
}

function dbShowRows() {
  const name = document.getElementById('db-table-detail').dataset.sqlName
  document.getElementById('db-sql-console').value = `SELECT * FROM ${name} LIMIT 100`
  runConsoleSQL()
}

function dbWriteQuery() {
  const t = _dbSchema.find(x => x.table === _dbSelected)
  const name = document.getElementById('db-table-detail').dataset.sqlName
  const cols = t ? t.columns.map(c => _sqlName(c.name)).join(', ') : '*'
  const input = document.getElementById('db-sql-console')
  input.value = `SELECT ${cols}\nFROM ${name}\nWHERE 1 = 1\nLIMIT 100`
  input.focus()
}

async function runConsoleSQL() {
  const sql = document.getElementById('db-sql-console').value.trim()
  const out = document.getElementById('db-query-results')
  if (!sql || !out) return
  out.innerHTML = '<div class="pane-empty">Running…</div>'
  try {
    const d = await apiFetch('/api/db/query', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ sql })
    }).then(r => r.json())
    if (!d.success) {
      out.innerHTML = `<div class="dbx-msg dbx-error">${escapeHtml(d.error || 'The query failed')}</div>`
      return
    }
    const res = d.result
    if (!res.columns.length) {
      out.innerHTML = `<div class="dbx-msg dbx-ok">Done: ${res.affected} row${res.affected === 1 ? '' : 's'} changed · ${res.ms} ms</div>`
      refreshDBTables()
      return
    }
    const cell = v => v === null ? '<span class="dbx-null">NULL</span>' : escapeHtml(String(v))
    out.innerHTML = `
      <div class="dbx-msg">${res.rows.length}${res.truncated ? '+' : ''} row${res.rows.length === 1 ? '' : 's'} · ${res.ms} ms${res.truncated ? ' · showing the first 1000' : ''}</div>
      <div class="dbx-grid-wrap"><table class="dbx-grid">
        <thead><tr>${res.columns.map(c => `<th>${escapeHtml(c)}</th>`).join('')}</tr></thead>
        <tbody>${res.rows.map(r => `<tr>${r.map(v => `<td title="${v === null ? 'NULL' : escapeHtml(String(v))}">${cell(v)}</td>`).join('')}</tr>`).join('')}</tbody>
      </table></div>`
    out.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  } catch (e) {
    out.innerHTML = `<div class="dbx-msg dbx-error">Couldn't reach Studio: ${escapeHtml(e.message)}</div>`
  }
}

document.addEventListener('keydown', e => {
  if (e.target && e.target.id === 'db-sql-console' && e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
    e.preventDefault()
    runConsoleSQL()
  }
})

// IoT panel: Studio's own devices plus the running Preview backend's, refreshed while the panel is open
let iotTimer = null
let iotBusy = false

function iotWhere(info) {
  const w = info.where || {}
  const parts = []
  if (info.driver && info.driver !== 'simulated') parts.push(info.driver)
  if (w.pin !== undefined) parts.push('pin ' + w.pin)
  if (w.channel !== undefined) parts.push('channel ' + w.channel)
  if (w.sensor) parts.push(w.sensor)
  if (w.port) parts.push(w.port)
  if (w.topic) parts.push(w.topic)
  if (w.url) parts.push(w.url)
  if (info.location) parts.push(info.location)
  return parts.join(' · ')
}

function iotControl(id, info) {
  const key = `'${escapeHtml(id)}', '${info.source}'`
  const val = info.value
  const unit = escapeHtml(info.unit || '')
  const release = info.pinned
    ? `<button class="btn btn-sm" title="Back to the simulated reading" onclick="setIoTValue(${key}, null, true)" style="padding:2px 6px;font-size:10px;">↺ live</button>` : ''
  if (info.kind === 'sensor' || info.kind === 'level') {
    const lo = info.min ?? 0, hi = info.max ?? 100
    const step = (hi - lo) > 50 ? 1 : 0.5
    const pin = info.kind === 'sensor'
    return `<div style="display:flex;align-items:center;gap:8px;">
      <input type="range" min="${lo}" max="${hi}" step="${step}" value="${val}" style="flex:1;height:4px;"
        oninput="this.nextElementSibling.textContent = this.value + '${unit}'"
        onchange="setIoTValue(${key}, Number(this.value), ${pin})" />
      <span style="font-weight:600;color:var(--text);min-width:56px;text-align:right;font-size:11.5px;">${escapeHtml(val)}${unit}</span>${release}</div>`
  }
  if (info.kind === 'binary_sensor') {
    return `<div style="display:flex;align-items:center;gap:8px;">
      <button class="btn btn-sm" onclick="setIoTValue(${key}, ${val ? 0 : 1}, true)"
        style="padding:2px 10px;font-size:11px;background:${val ? '#3b82f6' : 'var(--surface3)'};color:${val ? '#fff' : 'var(--text)'};">
        ${val ? 'Detected: clear it' : 'Trigger'}</button>${release}</div>`
  }
  if (info.kind === 'switch') {
    return `<label style="display:flex;align-items:center;gap:8px;cursor:pointer;font-size:11.5px;">
      <input type="checkbox" ${val ? 'checked' : ''} onchange="setIoTValue(${key}, this.checked ? 1 : 0, false)" />
      <span style="font-weight:600;color:${val ? '#22c55e' : 'var(--muted)'};">${val ? 'ON' : 'OFF'}</span></label>`
  }
  return `<input type="text" value="${escapeHtml(val)}" class="form-input" style="padding:2px 6px;font-size:11px;"
    onchange="setIoTValue(${key}, this.value, false)" />`
}

async function refreshIoTSimulator() {
  const container = document.getElementById('iot-devices-list')
  if (!container) return
  const panel = document.getElementById('panel-iot-simulator')
  if (panel && panel.classList.contains('active') && !iotTimer) {
    iotTimer = setInterval(() => {
      if (!panel.classList.contains('active')) { clearInterval(iotTimer); iotTimer = null; return }
      refreshIoTSimulator()
    }, 1500)
  }
  // Don't redraw under the user's hand while they drag a slider or type
  const active = document.activeElement
  if (iotBusy || (active && container.contains(active) && active.matches('input[type=range], input[type=text]'))) return
  iotBusy = true
  try {
    const d = await (await apiFetch('/api/iot/devices')).json()
    const live = document.getElementById('iot-live')
    if (live) live.textContent = d.backend ? '● live · backend running' : '● live'
    const entries = Object.entries((d.success && d.devices) || {})
    if (entries.length) {
      container.innerHTML = entries.map(([id, info]) => `
        <div style="background:var(--surface2);border:1px solid var(--border);border-radius:6px;padding:8px 12px;display:flex;flex-direction:column;gap:6px;">
          <div style="display:flex;justify-content:space-between;align-items:center;gap:6px;">
            <strong style="color:var(--text);font-size:12px;">${escapeHtml(id)}</strong>
            <span style="display:flex;gap:4px;">
              ${info.source === 'backend' ? '<span style="font-size:10px;background:rgba(59,130,246,.15);color:#60a5fa;padding:1px 6px;border-radius:4px;">backend</span>' : ''}
              <span style="font-size:10px;background:var(--surface3);color:var(--muted);padding:1px 6px;border-radius:4px;">${escapeHtml(info.type)}</span>
            </span>
          </div>
          ${iotControl(id, info)}
          ${iotWhere(info) ? `<div style="font-size:10.5px;color:var(--muted);">${escapeHtml(iotWhere(info))}${info.simulated && info.driver !== 'simulated' ? ' (simulated)' : ''}</div>` : ''}
        </div>`).join('')
    } else {
      container.innerHTML = '<div style="text-align:center;font-style:italic;color:var(--muted);padding:12px;background:var(--surface2);border:1px solid var(--border);border-radius:6px;font-size:11.5px;">No devices yet. Register one with device("register", ...) and press Run.</div>'
    }

    const logsD = await (await apiFetch('/api/iot/commands')).json()
    const logContainer = document.getElementById('iot-actions-log')
    if (logContainer && logsD.success && logsD.commands && logsD.commands.length > 0) {
      logContainer.innerHTML = logsD.commands.slice().reverse().map(cmd => `
        <div style="border-bottom:1px solid var(--border);padding:4px 0;font-size:10.5px;">
          <span style="color:#565f89;">[${new Date(cmd.timestamp * 1000).toLocaleTimeString()}]</span>
          <strong style="color:#89ddff;">${escapeHtml(cmd.device_id)}</strong>:
          <span style="color:#bb9af3;">${escapeHtml(cmd.command)}</span>
          <span style="color:var(--muted);">${escapeHtml(JSON.stringify(cmd.params || {}))}</span>
        </div>`).join('')
    }
  } catch (e) {
    container.innerHTML = `<div style="color:#f87171;">Couldn't load devices: ${escapeHtml(e.message)}</div>`
  } finally {
    iotBusy = false
  }
}

async function setIoTValue(deviceId, source, value, pin) {
  try {
    const r = await apiFetch('/api/iot/device/value', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ device_id: deviceId, source, value, pin })
    })
    const d = await r.json()
    if (!d.success && d.error) appendLog('error', `${deviceId}: ${d.error}`)
  } catch (e) {}
  if (document.activeElement) document.activeElement.blur()
  refreshIoTSimulator()
}

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]))
}

async function refreshAIInspector() {
  const traceContainer = document.getElementById('ai-execution-trace')
  if (!traceContainer) return
  try {
    const r = await apiFetch('/api/ai/trace')
    const d = await r.json()
    if (d.success) {
      document.getElementById('ai-active-model').textContent = d.model

      if (d.trace && d.trace.length > 0) {
        // Newest first; prompts and responses are model output, so escape them
        traceContainer.innerHTML = d.trace.slice().reverse().map(t => `
          <div style="background:var(--surface2);border:1px solid var(--border);border-radius:6px;padding:8px 12px;font-size:11px;">
            <div style="display:flex;justify-content:space-between;gap:8px;color:var(--muted);margin-bottom:4px;border-bottom:1px solid var(--border);padding-bottom:2px;">
              <strong>${escapeHtml(t.type)}${t.model ? ' · ' + escapeHtml(t.model) : ''}</strong>
              <span>${t.duration_ms != null ? escapeHtml(t.duration_ms) + ' ms · ' : ''}${new Date(t.timestamp * 1000).toLocaleTimeString()}</span>
            </div>
            <div style="color:#89ddff;margin-bottom:4px;white-space:pre-wrap;"><b>Query:</b> ${escapeHtml(t.prompt)}</div>
            <div style="color:#34d399;white-space:pre-wrap;"><b>Response:</b> ${escapeHtml(t.response)}</div>
          </div>
        `).join('')
      } else {
        traceContainer.innerHTML = '<div style="color:var(--muted);font-style:italic;">No AI operations yet. Run code that calls ai(), llm(), extract(), classify(), embed() or rag() to see each call here.</div>'
      }
    }
  } catch (e) {
    traceContainer.innerHTML = `<div style="color:#f87171;">Failed to load trace: ${escapeHtml(e.message)}</div>`
  }
}

// Initialize workspace selectors and view defaults
setTimeout(() => {
  switchWorkspace('react');
}, 100);

function switchWorkspace(workspace) {
  _activeWorkspace = workspace;
  
  // 1. Update switcher buttons and mode pills
  document.querySelectorAll('.switcher-item').forEach(btn => btn.classList.remove('active'));
  const activeBtn = document.getElementById('ws-' + workspace);
  if (activeBtn) activeBtn.classList.add('active');

  document.querySelectorAll('.mode-pill').forEach(p => p.classList.remove('active'));
  const activePill = document.getElementById('pill-' + workspace);
  if (activePill) activePill.classList.add('active');

  // 2. Update dynamic action buttons & menu items
  const heroRunText = document.getElementById('hero-run-text');
  const heroPreviewText = document.getElementById('hero-preview-text');
  const btnHeroRun = document.getElementById('btn-hero-run');
  const btnHeroPreview = document.getElementById('btn-hero-preview');
  const verifyLabel = document.getElementById('verify-label');
  const btnVerify = document.getElementById('btn-verify');
  const menuBuildRunText = document.getElementById('menu-build-run-text');
  const menuBuildPreviewText = document.getElementById('menu-build-preview-text');
  const menuBuildVerifyText = document.getElementById('menu-build-verify-text');

  if (workspace === 'flutter') {
    if (heroRunText) heroRunText.textContent = 'Run';
    if (heroPreviewText) heroPreviewText.textContent = 'App Preview';
    if (btnHeroRun) btnHeroRun.title = 'Run backend service for mobile app (Ctrl+Enter)';
    if (btnHeroPreview) btnHeroPreview.title = 'Generate the Flutter app from ui/app.mcn and run it in the phone preview (Cmd+R)';
    if (verifyLabel) verifyLabel.textContent = 'Verify';
    if (btnVerify) btnVerify.title = 'Verify Flutter / Dart and MCN syntax';
    if (menuBuildRunText) menuBuildRunText.textContent = 'Run Mobile Backend';
    if (menuBuildPreviewText) menuBuildPreviewText.textContent = 'Build & Preview Flutter App';
    if (menuBuildVerifyText) menuBuildVerifyText.textContent = 'Verify Flutter Code';
  } else if (workspace === 'repl') {
    if (heroRunText) heroRunText.textContent = 'Run';
    if (heroPreviewText) heroPreviewText.textContent = 'REPL';
    if (btnHeroRun) btnHeroRun.title = 'Run active script in REPL environment (Ctrl+Enter)';
    if (btnHeroPreview) btnHeroPreview.title = 'Focus interactive REPL shell';
    if (verifyLabel) verifyLabel.textContent = 'Verify';
    if (btnVerify) btnVerify.title = 'Verify MCN Syntax';
    if (menuBuildRunText) menuBuildRunText.textContent = 'Execute REPL Script';
    if (menuBuildPreviewText) menuBuildPreviewText.textContent = 'Open REPL Console';
    if (menuBuildVerifyText) menuBuildVerifyText.textContent = 'Verify MCN Syntax';
  } else {
    // react / web
    if (heroRunText) heroRunText.textContent = 'Run';
    if (heroPreviewText) heroPreviewText.textContent = 'Preview';
    if (btnHeroRun) btnHeroRun.title = 'Execute MCN Backend Service on port 8080 (Ctrl+Enter)';
    if (btnHeroPreview) btnHeroPreview.title = 'Compile MCN to React TSX and launch web preview (Cmd+R)';
    if (verifyLabel) verifyLabel.textContent = 'Verify';
    if (btnVerify) btnVerify.title = 'Verify syntax, AST, and types (F8)';
    if (menuBuildRunText) menuBuildRunText.textContent = 'Run Backend API';
    if (menuBuildPreviewText) menuBuildPreviewText.textContent = 'Build UI & Launch Preview';
    if (menuBuildVerifyText) menuBuildVerifyText.textContent = 'Run Static Verification';
  }
  
  // 3. Hide/show workspace-specific tabs in preview-panel
  const tabWeb = document.getElementById('tab-web-preview');
  const tabMobile = document.getElementById('tab-mobile-preview');
  const tabRepl = document.getElementById('tab-repl-console');
  
  [tabWeb, tabMobile, tabRepl].forEach(t => {
    if (t) t.style.display = 'none';
  });
  
  // 4. Update editor-area views & right panel
  const monacoContainer = document.getElementById('monaco-container');
  const tabBar = document.getElementById('tab-bar');
  
  if (monacoContainer) monacoContainer.style.display = '';
  if (tabBar) tabBar.style.display = '';
  
  if (workspace === 'repl') {
    if (tabRepl) {
      tabRepl.style.display = '';
      switchPanel('repl-console', tabRepl);
      setTimeout(() => {
        if (window._replEditor) {
          window._replEditor.layout();
          window._replEditor.focus();
        }
      }, 60);
    }
  } else if (workspace === 'react') {
    if (tabWeb) {
      tabWeb.style.display = '';
      switchPanel('preview', tabWeb);
    }
  } else if (workspace === 'flutter') {
    if (tabMobile) {
      tabMobile.style.display = '';
      switchPanel('flutter-preview', tabMobile);
      renderFlutterSimulator();
    }
  }

  // 5. Filter file tree
  if (window._workspaceFiles) {
    renderFileTree(window._workspaceFiles);
  }

  // 6. Ensure an appropriate file is opened for the active mode
  if (workspace === 'flutter') {
    if (!_active || _active.startsWith('frontend/') || _active.startsWith('scripts/')) {
      const candidates = ['ui/app.mcn', 'mobile/lib/main.dart', 'mobile/pubspec.yaml', 'backend/main.mcn'];
      for (const cand of candidates) {
        if (window._workspaceFiles && window._workspaceFiles.some(f => f.path === cand)) {
          openFile(cand);
          break;
        }
      }
    }
  } else if (workspace === 'repl') {
    if (!_active || _active.startsWith('ui/') || _active.startsWith('frontend/') || _active.startsWith('mobile/')) {
      const candidates = ['scripts/sandbox.mcn', 'backend/main.mcn'];
      for (const cand of candidates) {
        if (window._workspaceFiles && window._workspaceFiles.some(f => f.path === cand)) {
          openFile(cand);
          break;
        }
      }
    }
  } else if (workspace === 'react') {
    if (!_active || _active.startsWith('mobile/') || _active.startsWith('scripts/')) {
      const candidates = ['ui/app.mcn', 'backend/main.mcn', 'frontend/src/App.tsx'];
      for (const cand of candidates) {
        if (window._workspaceFiles && window._workspaceFiles.some(f => f.path === cand)) {
          openFile(cand);
          break;
        }
      }
    }
  }
}

// ── REPL Sandbox console logic ────────────────────────────────────────────────
async function executeReplCommand(cmd) {
  const history = document.getElementById('repl-history');
  if (!history) return;
  
  const trimmed = cmd.trim();
  if (!trimmed) return;

  // Echo input command
  const inEl = document.createElement('div');
  inEl.style.color = '#89ddff';
  inEl.style.fontWeight = '600';
  inEl.textContent = `mcn> ${trimmed}`;
  history.appendChild(inEl);

  // Handle REPL utility commands
  if (trimmed === 'clear') {
    history.innerHTML = '<div style="color:#565f89;">// REPL console cleared. Ready for expressions.</div>';
    return;
  }

  if (trimmed === 'help') {
    const helpEl = document.createElement('div');
    helpEl.style.color = '#7aa2f7';
    helpEl.style.whiteSpace = 'pre-wrap';
    helpEl.textContent = 
      "MCN REPL Commands & Tips:\n" +
      "  vars            — List all active variables in the current REPL session\n" +
      "  reset           — Clear REPL state and reset interpreter session\n" +
      "  clear           — Clear this output history\n" +
      "  help            — Show this command help\n" +
      "\n" +
      "Example Statements:\n" +
      "  var count = 42\n" +
      "  function double(n) { return n * 2 }\n" +
      "  log(double(count))\n" +
      "  sum([10, 20, 30])\n";
    history.appendChild(helpEl);
    history.scrollTop = history.scrollHeight;
    return;
  }

  if (trimmed === 'vars') {
    try {
      const r = await apiFetch('/api/repl/vars?session_id=repl_user');
      const d = await r.json();
      const varsEl = document.createElement('div');
      varsEl.style.color = '#bb9af7';
      const keys = Object.keys(d.vars || {});
      if (keys.length === 0) {
        varsEl.textContent = "No user variables currently bound. Define one with: var x = 10";
      } else {
        varsEl.innerHTML = "<strong>Active REPL Environment Variables:</strong><br>" + 
          keys.map(k => `  • <span style="color:#7dcfff;">${k}</span> = <span style="color:#9ece6a;">${d.vars[k]}</span>`).join("<br>");
      }
      history.appendChild(varsEl);
    } catch (err) {
      const errEl = document.createElement('div');
      errEl.style.color = '#f7768e';
      errEl.textContent = `Failed to fetch variables: ${err.message}`;
      history.appendChild(errEl);
    }
    history.scrollTop = history.scrollHeight;
    return;
  }

  if (trimmed === 'reset') {
    try {
      await apiFetch('/api/repl/reset', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: 'repl_user' })
      });
      const resetEl = document.createElement('div');
      resetEl.style.color = '#f7768e';
      resetEl.textContent = "✓ REPL environment reset. All variable bindings cleared.";
      history.appendChild(resetEl);
    } catch (err) {
      const errEl = document.createElement('div');
      errEl.style.color = '#f7768e';
      errEl.textContent = `Failed to reset REPL: ${err.message}`;
      history.appendChild(errEl);
    }
    history.scrollTop = history.scrollHeight;
    return;
  }

  try {
    const r = await apiFetch('/api/execute', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code: trimmed, is_repl: true, session_id: 'repl_user' })
    });
    const d = await r.json();

    if (d.output && d.output.length > 0) {
      for (const line of d.output) {
        const outLine = document.createElement('div');
        outLine.style.color = '#c0caf5';
        outLine.textContent = line;
        history.appendChild(outLine);
      }
    }

    const resEl = document.createElement('div');
    if (d.success) {
      resEl.style.color = '#9ece6a';
      if (d.result !== null && d.result !== undefined && d.result !== 'None' && d.result !== '') {
        resEl.textContent = `=> ${d.result}`;
      } else if (!d.output || d.output.length === 0) {
        resEl.style.color = '#565f89';
        resEl.textContent = '=> (executed)';
      }
      history.appendChild(resEl);
    } else {
      resEl.style.color = '#f7768e';
      resEl.textContent = `Error: ${d.error || 'Execution failed'}`;
      history.appendChild(resEl);
    }
  } catch (err) {
    const errEl = document.createElement('div');
    errEl.style.color = '#f7768e';
    errEl.textContent = `Execution Error: ${err.message}`;
    history.appendChild(errEl);
  }
  history.scrollTop = history.scrollHeight;
}

