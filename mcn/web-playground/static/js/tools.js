// ── Workspace Switching & Redesign ──────────────────────────────────────────
let _activeWorkspace = 'react';

// ── DB, IoT, and AI Trace Helper Functions ────────────────────────────────
async function refreshDBTables() {
  const container = document.getElementById('db-tables-list')
  if (!container) return
  try {
    const r = await apiFetch('/api/db/schema')
    const d = await r.json()
    if (d.success && d.schema && d.schema.length > 0) {
      container.innerHTML = d.schema.map(t => `
        <div style="margin-bottom: 6px;">
          <strong style="color:var(--text);">${t.table}</strong>
          <div style="padding-left:10px;margin-top:2px;color:var(--muted);display:flex;flex-wrap:wrap;gap:4px;">
            ${t.columns.map(c => `<span style="background:var(--surface3);padding:1px 4px;border-radius:3px;font-size:10px;">${c}</span>`).join('')}
          </div>
        </div>
      `).join('')
    } else {
      container.innerHTML = '<div style="text-align:center;font-style:italic;">No tables found. Run database code first.</div>'
    }
  } catch (e) {
    container.innerHTML = `<div style="color:#f87171;">Failed to load tables: ${e.message}</div>`
  }
}

async function runConsoleSQL() {
  const sql = document.getElementById('db-sql-console').value.trim()
  const resultsDiv = document.getElementById('db-query-results')
  if (!sql || !resultsDiv) return
  resultsDiv.textContent = 'Executing query...'
  try {
    const r = await apiFetch('/api/db/query', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sql })
    })
    const d = await r.json()
    if (d.success) {
      if (Array.isArray(d.result) && d.result.length > 0) {
        const cols = Object.keys(d.result[0])
        const headerHtml = cols.map(c => `<th style="text-align:left;padding:6px;border-bottom:2px solid var(--border);color:var(--text);font-weight:600;">${c}</th>`).join('')
        const rowsHtml = d.result.map(row => `
          <tr style="border-bottom:1px solid var(--border);">
            ${cols.map(c => `<td style="padding:6px;color:var(--muted);">${row[c] !== null ? row[c] : 'NULL'}</td>`).join('')}
          </tr>
        `).join('')
        
        resultsDiv.innerHTML = `
          <table style="width:100%;border-collapse:collapse;font-size:11px;">
            <thead><tr>${headerHtml}</tr></thead>
            <tbody>${rowsHtml}</tbody>
          </table>
        `
      } else {
        resultsDiv.innerHTML = `<div style="color:#34d399;font-style:italic;">Query executed successfully. Result: ${JSON.stringify(d.result)}</div>`
      }
      refreshDBTables()
    } else {
      resultsDiv.innerHTML = `<div style="color:#f87171;">Error: ${d.error}</div>`
    }
  } catch (e) {
    resultsDiv.innerHTML = `<div style="color:#f87171;">Connection failed: ${e.message}</div>`
  }
}

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
    if (btnHeroPreview) btnHeroPreview.title = 'Compile MCN/Dart to Flutter package and preview in mobile simulator (Cmd+R)';
    if (verifyLabel) verifyLabel.textContent = 'Verify';
    if (btnVerify) btnVerify.title = 'Verify Flutter / Dart and MCN syntax';
    if (menuBuildRunText) menuBuildRunText.textContent = 'Run Mobile Backend';
    if (menuBuildPreviewText) menuBuildPreviewText.textContent = 'Build Flutter Simulator';
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
    if (!_active || _active.startsWith('ui/') || _active.startsWith('frontend/') || _active.startsWith('scripts/')) {
      const candidates = ['mobile/lib/main.dart', 'mobile/pubspec.yaml', 'mobile/ui.mcn', 'backend/main.mcn'];
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

