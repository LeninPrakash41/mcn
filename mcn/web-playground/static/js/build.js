// ── Format / Check / Test / Clear ────────────────────────────────────────
async function formatActiveFile() {
  if (!_active) return
  const model = _models.get(_active)
  if (!model) return
  switchPanel('output', document.querySelector('[data-panel="output"]'))
  try {
    const r = await apiFetch('/api/format', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code: model.getValue() })
    })
    const d = await r.json()
    if (d.formatted) {
      model.setValue(d.formatted)
      if (_tabState.has(_active)) _tabState.get(_active).dirty = true
      renderTabs()
      appendLog('success', '✓ Formatted')
      setStatus('Formatted', 'ok')
    } else {
      appendLog('error', '✗ ' + (d.error || 'Format failed'))
      setStatus('Format error', 'err')
    }
  } catch (e) { appendLog('error', '✗ ' + e.message); setStatus('Error', 'err') }
}

async function checkActiveFile() {
  if (!_active) return
  const model = _models.get(_active)
  if (!model) return
  switchPanel('output', document.querySelector('[data-panel="output"]'))
  appendLog('info', '✓ Multi-Stage Verification: ' + _active)
  try {
    const r = await apiFetch('/api/agent/verify', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code: model.getValue() })
    })
    const d = await r.json()
    if (d.success && d.result) {
      updateDiagnosticsState(d.result)
      if (d.result.valid) {
        appendLog('success', '✓ All stages passed: Lexer, Parser, AST, and Type Checks clean.')
        setStatus('Verification passed', 'ok')
      } else {
        appendLog('error', `✗ Found ${d.result.issues_count} issue(s):`)
        for (const iss of d.result.issues) {
          appendLog('error', `  [${iss.stage.toUpperCase()}] Line ${iss.line}:${iss.col} - ${iss.message}`)
          if (iss.code_context) appendLog('dim', `    Code: ${iss.code_context.trim()}`)
          if (iss.fix_suggestion) appendLog('info', `    Suggested Fix: ${iss.fix_suggestion}`)
        }
        setStatus(`${d.result.issues_count} issue(s) found`, 'err')
      }
    } else {
      appendLog('error', '✗ Verification error: ' + (d.error || 'Unknown error'))
      setStatus('Verification error', 'err')
    }
  } catch (e) { appendLog('error', '✗ ' + e.message); setStatus('Error', 'err') }
}

function updateDiagnosticsState(result) {
  const badge = document.getElementById('verify-label')
  const icon = document.getElementById('verify-icon')
  const banner = document.getElementById('editor-diagnostic-banner')
  const msgEl = document.getElementById('diag-msg')
  const diagBadge = document.getElementById('diag-badge')

  if (result && result.valid) {
    if (badge) badge.textContent = 'Verified (0)'
    if (icon) icon.textContent = '✓'
    dismissDiagnosticBanner()
  } else if (result && result.issues && result.issues.length > 0) {
    const count = result.issues_count || result.issues.length
    if (badge) badge.textContent = `Issues (${count})`
    if (icon) icon.textContent = '!'
    const first = result.issues[0]
    if (diagBadge) diagBadge.textContent = first.stage.toUpperCase()
    if (msgEl) msgEl.textContent = `Line ${first.line}:${first.col} — ${first.message}`
    if (banner) banner.classList.remove('hidden')
  }
}

function dismissDiagnosticBanner() {
  const banner = document.getElementById('editor-diagnostic-banner')
  if (banner) banner.classList.add('hidden')
}

async function autoFixWithAI() {
  if (!_active) return
  const model = _models.get(_active)
  if (!model) return
  const code = model.getValue()
  setStatus('AI Self-Healing…')
  switchPanel('output', document.querySelector('[data-panel="output"]'))
  appendLog('info', 'AI Copilot: Synthesizing self-healing fix for current file…')
  try {
    const res = await apiFetch('/api/agent/repair', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code })
    })
    const data = await res.json()
    if (data.success && data.repair_prompt) {
      appendLog('success', 'Diagnostic repair prompt prepared.')
      openAgentStudioModal()
      const promptInput = document.getElementById('agent-prompt-input')
      if (promptInput) {
        promptInput.value = 'Fix the following compiler and syntax errors:\n' + data.repair_prompt
      }
      dismissDiagnosticBanner()
    }
  } catch (e) {
    appendLog('error', 'Auto-fix error: ' + e.message)
  }
}

async function buildAndLaunchPreview() {
  if (_activeWorkspace === 'flutter') {
    await buildProject();
    const tabMobile = document.getElementById('tab-mobile-preview');
    switchPanel('flutter-preview', tabMobile);
    renderFlutterSimulator();
  } else if (_activeWorkspace === 'repl') {
    const tabRepl = document.getElementById('tab-repl-console');
    switchPanel('repl-console', tabRepl);
    if (window._replEditor) {
      window._replEditor.layout();
      window._replEditor.focus();
    }
  } else {
    // 1. Compile project
    await buildProject();
    
    // 2. Switch to web preview tab
    const tabWeb = document.getElementById('tab-web-preview');
    switchPanel('preview', tabWeb || document.querySelector('[data-panel="preview"]'));
    
    // 3. Start dev server if not running, or refresh preview iframe
    if (!_devOn) {
      await startDevServer();
    } else {
      refreshPreview();
      showPreview();
    }
  }
}

async function loadStarterScaffold(template) {
  setStatus(`Loading ${template} scaffold…`)
  try {
    const res = await apiFetch(`/api/agent/scaffold?template=${template}`)
    const data = await res.json()
    if (data.success && data.code) {
      const targetFile = 'backend/main.mcn'
      let model = _models.get(targetFile)
      if (!model) {
        model = monaco.editor.createModel(data.code, 'mcn', monaco.Uri.file(targetFile))
        _models.set(targetFile, model)
      } else {
        model.setValue(data.code)
      }
      if (!_openTabs.some(t => t.path === targetFile)) {
        _openTabs.push({ path: targetFile })
      }
      _tabState.set(targetFile, { dirty: true })
      openTab(targetFile)
      appendLog('success', `Loaded ${template} verified scaffold into ${targetFile}`)
      setStatus('Scaffold loaded', 'ok')
    }
  } catch (e) {
    appendLog('error', 'Scaffold load error: ' + e.message)
  }
}

async function runTests() {
  if (!_active) return
  const model = _models.get(_active)
  if (!model) return
  switchPanel('output', document.querySelector('[data-panel="output"]'))
  appendLog('info', 'Testing ' + _active)
  setStatus('Testing…')
  const code = model.getValue()

  // Use SSE streaming endpoint so results appear as each test completes
  try {
    const resp = await apiFetch('/api/test/stream', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code })
    })
    if (!resp.ok) { appendLog('error', '✗ Server error ' + resp.status); return }
    const reader  = resp.body.getReader()
    const decoder = new TextDecoder()
    let   buf     = ''
    let   passed  = 0, failed = 0, total = 0

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buf += decoder.decode(value, { stream: true })
      const chunks = buf.split('\n\n')
      buf = chunks.pop()
      for (const chunk of chunks) {
        const line = chunk.replace(/^data: /, '').trim()
        if (!line) continue
        try {
          const ev = JSON.parse(line)
          if (ev.type === 'start') {
            total = ev.total
            appendLog('dim', `Running ${total} test(s)…`)
          } else if (ev.type === 'result') {
            const icon = ev.passed ? '✓' : '✗'
            const cls  = ev.passed ? 'success' : 'error'
            appendLog(cls, `${icon} ${ev.description}  (${ev.elapsed_ms}ms)`)
            if (!ev.passed && ev.error) appendLog('error', '  ' + ev.error)
            if (ev.passed) passed++; else failed++
            setStatus(`${passed}/${total} passed`, failed ? 'err' : 'ok')
          } else if (ev.type === 'done') {
            const msg = `${ev.passed} passed, ${ev.failed} failed`
            appendLog(ev.failed ? 'error' : 'success', (ev.failed ? '✗ ' : '✓ ') + msg)
            setStatus(msg, ev.failed ? 'err' : 'ok')
          } else if (ev.type === 'error') {
            appendLog('error', '✗ ' + ev.message)
            setStatus('Error', 'err')
          }
        } catch (_) {}
      }
    }
  } catch (e) { appendLog('error', '✗ ' + e.message); setStatus('Error', 'err') }
}

function clearOutput() {
  document.getElementById('output-log').innerHTML = ''
  switchPanel('output', document.querySelector('[data-panel="output"]'))
  setStatus('Ready')
}

// ── Build ─────────────────────────────────────────────────────────────────
async function buildProject() {
  await saveAllTabs()
  setStatus('Building…')
  const isFlutter = (_activeWorkspace === 'flutter');
  appendLog('info', `Building UI for platform ${isFlutter ? 'Flutter' : 'React'}…`)
  try {
    const uiModel = _models.get('ui/app.mcn');
    const backendModel = _models.get('backend/main.mcn');
    const r = await apiFetch('/api/build', {
      method: 'POST', 
      headers: { 'Content-Type': 'application/json' }, 
      body: JSON.stringify({ 
        platform: isFlutter ? 'flutter' : 'react',
        ui: uiModel ? uiModel.getValue() : undefined,
        backend: backendModel ? backendModel.getValue() : undefined
      })
    })
    const d = await r.json()
    if (d.stdout) appendLog('dim', d.stdout)
    if (d.stderr) appendLog('warn', d.stderr)
    if (d.success) {
      appendLog('success', `Build complete — ${d.files?.length || 0} files generated`)
      setStatus('Build complete', 'ok')
      _built = true
      const btnDownload = document.getElementById('btnDownload')
      if (btnDownload) btnDownload.disabled = false
      renderBuildFiles(d.files || [])
      await loadFileTree()
      if (isFlutter) {
        renderFlutterSimulator();
      }
    } else {
      appendLog('error', '✗ ' + d.error)
      setStatus('Build failed', 'err')
    }
  } catch (e) { appendLog('error', '✗ ' + e.message); setStatus('Error', 'err') }
}

function renderBuildFiles(files) {
  const ct = document.getElementById('build-files-list')
  ct.innerHTML = ''
  for (const f of files) {
    const el = document.createElement('div')
    el.className = 'build-file-item'
    el.innerHTML = `<span>${fileIcon(f)}</span><span>${f}</span>`
    el.onclick = () => openFile(f)
    ct.appendChild(el)
  }
}

// ── Download ──────────────────────────────────────────────────────────────
function downloadProject(platformOverride) {
  const plat = platformOverride || (_activeWorkspace === 'flutter' ? 'flutter' : 'react');
  window.location.href = `/api/download?platform=${plat}`
}

// ── Dev server ────────────────────────────────────────────────────────────
async function toggleDevServer() {
  if (_devOn) await stopDevServer(); else await startDevServer()
}

async function startDevServer() {
  const btnToggle = document.getElementById('btn-toggle-server');
  if (btnToggle) {
    btnToggle.disabled = true;
    btnToggle.innerHTML = '<span class="spinner" style="display:inline-block; vertical-align:middle; margin-right:4px;"></span> Starting…';
  }
  setStatus('Starting dev server…')
  try {
    const r = await apiFetch('/api/devserver/start', { method: 'POST' })
    const d = await r.json()
    if (d.success) {
      _devOn = true
      const beInfo = d.backend_port ? ` | API :${d.backend_port}` : ''
      if (d.mode === 'static') {
        // npm not available — serve built files via Flask static route
        setStatus(`Static preview${beInfo}`, 'ok')
        if (btnToggle) btnToggle.textContent = 'Stop Server'
        const srvBadge = document.getElementById('server-badge')
        if (srvBadge) {
          srvBadge.textContent = `Static preview${beInfo}`
          srvBadge.className = 'running'
        }
        const statusSrv = document.getElementById('status-srv')
        if (statusSrv) statusSrv.textContent = 'static'
        appendLog('warn', '⚠ npm not found — serving built files statically.')
        appendLog('info', 'Install Node.js for full Vite hot-reload support.')
        if (d.backend_port) appendLog('success', `✓ MCN backend running on :${d.backend_port}`)
        showPreview(d.preview_url)
      } else {
        setStatus(`UI :${d.port}${beInfo}`, 'ok')
        if (btnToggle) btnToggle.textContent = 'Stop Server'
        const srvBadge = document.getElementById('server-badge')
        if (srvBadge) {
          srvBadge.textContent = `Running${beInfo}`
          srvBadge.className = 'running'
        }
        const statusSrv = document.getElementById('status-srv')
        if (statusSrv) statusSrv.textContent = `:${d.port}`
        if (d.backend_port) appendLog('success', `Backend running on :${d.backend_port}`)
        showPreview(d.preview_url || `http://localhost:${d.port}`)
      }
    } else {
      appendLog('error', '✗ ' + d.error)
      setStatus('Server failed', 'err')
      if (btnToggle) btnToggle.textContent = 'Start Server'
    }
  } catch (e) {
    appendLog('error', '✗ ' + e.message);
    setStatus('Error', 'err');
    if (btnToggle) btnToggle.textContent = 'Start Server';
  } finally {
    if (btnToggle) btnToggle.disabled = false;
  }
}

async function stopDevServer() {
  await apiFetch('/api/devserver/stop', { method: 'POST' })
  _devOn = false
  const btnToggle = document.getElementById('btn-toggle-server')
  if (btnToggle) btnToggle.textContent = 'Start Server'
  const srvBadge = document.getElementById('server-badge')
  if (srvBadge) {
    srvBadge.textContent = 'No dev server'
    srvBadge.className = ''
  }
  const statusSrv = document.getElementById('status-srv')
  if (statusSrv) statusSrv.textContent = ''
  hidePreview()
  setStatus('Dev server stopped')
}

const _DEV_PORT = 5174

function refreshPreview() {
  const iframe = document.getElementById('preview-iframe');
  if (iframe && iframe.src && iframe.src !== 'about:blank') {
    const rawUrl = iframe.src.split('?')[0];
    iframe.src = rawUrl + '?t=' + Date.now();
  }
}

function showPreview(url) {
  const iframe = document.getElementById('preview-iframe')
  let targetUrl = url || (_devOn ? `http://localhost:${_DEV_PORT}` : '/preview/index.html')
  if (targetUrl.startsWith('/preview/')) {
    targetUrl = targetUrl.split('?')[0] + '?t=' + Date.now();
  }
  if (iframe) {
    iframe.src = targetUrl
    iframe.classList.remove('hidden')
  }
  const ph = document.getElementById('preview-ph')
  if (ph) ph.classList.add('hidden')
  
  const addr = document.getElementById('preview-address-bar')
  if (addr) addr.textContent = url || (_devOn ? `http://localhost:${_DEV_PORT}` : 'http://localhost:5003/preview/index.html')
  
  const dot = document.getElementById('preview-status-dot')
  if (dot) dot.style.background = '#10b981'
  
  const btnToggle = document.getElementById('btn-toggle-server')
  if (btnToggle) btnToggle.textContent = 'Stop Server'

  const tabWeb = document.getElementById('tab-web-preview')
  switchPanel('preview', tabWeb || document.querySelector('[data-panel="preview"]'))
}

function hidePreview() {
  const iframe = document.getElementById('preview-iframe')
  if (iframe) {
    iframe.src = 'about:blank'
    iframe.classList.add('hidden')
  }
  const ph = document.getElementById('preview-ph')
  if (ph) ph.classList.remove('hidden')
  
  const addr = document.getElementById('preview-address-bar')
  if (addr) addr.textContent = 'Server stopped'
  
  const dot = document.getElementById('preview-status-dot')
  if (dot) dot.style.background = '#ef4444'

  const btnToggle = document.getElementById('btn-toggle-server')
  if (btnToggle) btnToggle.textContent = 'Start Server'
}

function refreshPreview() {
  const iframe = document.getElementById('preview-iframe')
  if (iframe && _devOn) { const s = iframe.src; iframe.src = ''; iframe.src = s }
}

function openPreviewFullscreen() {
  const iframe = document.getElementById('preview-iframe')
  if (iframe && iframe.src && iframe.src !== 'about:blank') {
    window.open(iframe.src, '_blank')
  }
}

let _devPolling = false
async function pollDevStatus() {
  if (_devPolling) return  // one loop per page
  _devPolling = true
  while (true) {
    // Pause while the tab is in the background; resume as soon as it is visible
    if (document.hidden) {
      await new Promise(r => document.addEventListener('visibilitychange', r, { once: true }))
      continue
    }
    try {
      const r = await apiFetch('/api/devserver/status')
      const d = await r.json()
      if (d.running !== _devOn) {
        _devOn = d.running
        const btnToggle = document.getElementById('btn-toggle-server')
        const srvBadge = document.getElementById('server-badge')
        const statusSrv = document.getElementById('status-srv')
        if (_devOn) {
          const label = d.port ? `:${d.port}` : 'static'
          if (btnToggle) btnToggle.textContent = 'Stop Server'
          if (srvBadge) {
            srvBadge.textContent = `Running ${label}`
            srvBadge.className = 'running'
          }
          if (statusSrv) statusSrv.textContent = label
          const dot = document.getElementById('preview-status-dot')
          if (dot) dot.style.background = '#10b981'
        } else {
          if (btnToggle) btnToggle.textContent = 'Start Server'
          if (srvBadge) {
            srvBadge.textContent = d.npm_available ? 'No dev server' : 'npm not installed'
            srvBadge.className = ''
          }
          if (statusSrv) statusSrv.textContent = ''
          const dot = document.getElementById('preview-status-dot')
          if (dot) dot.style.background = '#ef4444'
        }
      }
    } catch (_) {}
    // Poll faster only while a dev server is running and may change state
    await new Promise(r => setTimeout(r, _devOn ? 5000 : 15000))
  }
}

// ── Panel switching ────────────────────────────────────────────────────────
function switchPanel(name, tabEl) {
  document.querySelectorAll('.panel-tab').forEach(t => t.classList.remove('active'))
  document.querySelectorAll('.panel-section').forEach(s => s.classList.remove('active'))
  
  if (tabEl) {
    tabEl.classList.add('active')
  } else {
    const defaultTab = document.querySelector(`.panel-tab[data-panel="${name}"]`)
    if (defaultTab) defaultTab.classList.add('active')
  }
  
  // Handle panel naming mapping
  let secId = 'panel-' + name;
  if (name === 'preview') secId = 'panel-preview';
  
  const sec = document.getElementById(secId)
  if (sec) sec.classList.add('active')

  if (name === 'db-explorer') refreshDBTables()
  else if (name === 'iot-simulator') refreshIoTSimulator()
  else if (name === 'ai-inspector') refreshAIInspector()
}

