// ── State ────────────────────────────────────────────────────────────────
let _openTabs  = []       // [{path}]
let _models    = new Map() // path → monaco model
let _tabState  = new Map() // path → {dirty}
let _active    = null
let _devOn     = false
let _built     = false
let _expandedFolders = new Set(['backend', 'ui', 'mobile', 'scripts']) // Keep active folders expanded by default
let _projectRootCollapsed = false;

function toggleProjectRoot() {
  _projectRootCollapsed = !_projectRootCollapsed;
  const scrollEl = document.getElementById('sidebar-scroll-container');
  const caretEl = document.getElementById('project-root-caret');
  if (scrollEl) {
    scrollEl.classList.toggle('collapsed', _projectRootCollapsed);
  }
  if (caretEl) {
    caretEl.textContent = _projectRootCollapsed ? '▶' : '▼';
  }
}

function toggleCollapseAllFolders() {
  if (_expandedFolders.size > 0) {
    _expandedFolders.clear();
  } else {
    _expandedFolders = new Set(['backend', 'ui', 'frontend', 'mobile', 'scripts']);
  }
  renderFileTree(window._workspaceFiles || []);
}

// ── Init ─────────────────────────────────────────────────────────────────
async function initApp() {
  const isDesktop = !!(window.mcnDesktop || window.__MCN_DESKTOP__ || /Electron/i.test(navigator.userAgent));
  const isMac = /(Mac|iPhone|iPod|iPad)/i.test(navigator.platform || navigator.userAgent);
  if (isDesktop) {
    document.documentElement.classList.add('is-desktop');
    if (isMac) document.documentElement.classList.add('is-mac-desktop');
  }
  await loadFileTree()
  await loadExamples()
  await openFile('backend/main.mcn')
  pollDevStatus()
}

// ── File tree ────────────────────────────────────────────────────────────
async function loadFileTree() {
  try {
    const r = await apiFetch('/api/workspace/files')
    const d = await r.json()
    window._workspaceFiles = d.files || []
    renderFileTree(window._workspaceFiles)
  } catch (_) {}
}

async function promptCreateFile() {
  const defaultDir = _activeWorkspace === 'flutter' ? 'mobile/lib/' : _activeWorkspace === 'repl' ? 'scripts/' : 'ui/';
  const path = await showIdePrompt(
    'Create New Workspace File',
    'Enter the path for the new file:',
    defaultDir,
    'e.g. backend/api.mcn, ui/component.mcn, mobile/lib/screen.dart',
    {
      suggestions: [
        'backend/api.mcn',
        'backend/services/auth.mcn',
        'ui/dashboard.mcn',
        'ui/components/stats.mcn',
        'mobile/lib/main.dart',
        'mobile/lib/screens/dashboard.dart',
        'scripts/sandbox.mcn',
        'frontend/src/App.tsx'
      ],
      confirmText: 'Create File'
    }
  );
  if (!path) return;
  
  const allowedExts = ['.mcn', '.tsx', '.ts', '.json', '.css', '.html', '.dart', '.yaml', '.yml'];
  const hasValidExt = allowedExts.some(ext => path.endsWith(ext));
  if (!hasValidExt) {
    await showIdeAlert('Invalid Extension', 'File must end with a valid extension: .mcn, .dart, .yaml, .tsx, .ts, .json, .css, or .html', 'warn');
    return;
  }
  
  try {
    const r = await apiFetch('/api/workspace/file', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: path, content: '' })
    });
    const d = await r.json();
    if (!r.ok || d.error) {
      await showIdeAlert('Creation Failed', d.error || 'Failed to create file', 'error');
      return;
    }
    showToast(`Created file ${path}`, 'success');
    await loadFileTree();
    await openFile(path);
  } catch (e) {
    await showIdeAlert('File Error', 'Error creating file: ' + e.message, 'error');
  }
}


function fileIcon(path) {
  const ext = path.split('.').pop().toLowerCase()
  if (ext === 'mcn')  return '<span class="ext-badge mcn">MCN</span>'
  if (ext === 'tsx' || ext === 'ts') return `<span class="ext-badge ${ext}">${ext.toUpperCase()}</span>`
  if (ext === 'json') return '<span class="ext-badge json">JSON</span>'
  if (ext === 'css')  return '<span class="ext-badge css">CSS</span>'
  if (ext === 'html') return '<span class="ext-badge html">HTML</span>'
  if (ext === 'dart') return '<span class="ext-badge dart" style="background:#0284c7;color:#fff;font-weight:700;">DART</span>'
  if (ext === 'yaml' || ext === 'yml') return '<span class="ext-badge yaml" style="background:#f43f5e;color:#fff;font-weight:700;">YAML</span>'
  return `<span class="ext-badge file">${ext.slice(0, 4).toUpperCase()}</span>`
}

function renderFileTree(files) {
  const ct = document.getElementById('file-tree')
  if (!ct) return
  ct.innerHTML = ''

  // Filter based on active workspace mode (completely exclude any legacy flutter/ folder)
  const filteredFiles = (files || []).filter(f => {
    if (!f || !f.path) return false;
    if (f.path.includes('node_modules') || f.path.includes('.git') || f.path.startsWith('flutter/')) return false;
    const p = f.path;
    if (_activeWorkspace === 'react') {
      if (p.startsWith('mobile/') || p.startsWith('scripts/')) return false;
    } else if (_activeWorkspace === 'flutter') {
      if (p.startsWith('ui/') || p.startsWith('frontend/') || p.startsWith('scripts/')) return false;
    } else if (_activeWorkspace === 'repl') {
      if (p.startsWith('ui/') || p.startsWith('frontend/') || p.startsWith('mobile/')) return false;
    }
    return true;
  });

  const folders = {}
  for (const f of filteredFiles) {
    const parts = f.path.split('/')
    const folder = parts.length > 1 ? parts[0] : '__root__'
    if (!folders[folder]) folders[folder] = []
    folders[folder].push(f)
  }
  const folderOrder = ['backend', 'ui', 'frontend', 'mobile', 'scripts', '__root__']
  const allFolders = [...new Set([...folderOrder, ...Object.keys(folders)])]
  for (const folder of allFolders) {
    if (!folders[folder] || folders[folder].length === 0) continue
    if (folder !== '__root__') {
      const isExpanded = _expandedFolders.has(folder)

      
      const folderHeader = document.createElement('div')
      folderHeader.className = 'tree-folder' + (isExpanded ? ' expanded' : '')
      folderHeader.innerHTML = `
        <span class="folder-caret">${isExpanded ? '▼' : '▶'}</span>
        <span class="tree-folder-icon">${isExpanded ? '▾' : '▸'}</span>
        <span>${folder}</span>
      `
      
      const folderContents = document.createElement('div')
      folderContents.className = 'tree-folder-contents'
      folderContents.style.display = isExpanded ? 'block' : 'none'
      
      for (const f of folders[folder]) {
        folderContents.appendChild(makeFileItem(f.path))
      }
      
      folderHeader.onclick = () => {
        if (_expandedFolders.has(folder)) {
          _expandedFolders.delete(folder)
          folderHeader.classList.remove('expanded')
          folderHeader.querySelector('.folder-caret').textContent = '▶'
          folderHeader.querySelector('.tree-folder-icon').textContent = '▸'
          folderContents.style.display = 'none'
        } else {
          _expandedFolders.add(folder)
          folderHeader.classList.add('expanded')
          folderHeader.querySelector('.folder-caret').textContent = '▼'
          folderHeader.querySelector('.tree-folder-icon').textContent = '▾'
          folderContents.style.display = 'block'
        }
      }
      
      ct.appendChild(folderHeader)
      ct.appendChild(folderContents)
    } else {
      for (const f of folders[folder]) {
        ct.appendChild(makeFileItem(f.path))
      }
    }
  }
  syncTreeActive()
}

function makeFileItem(path) {
  const el = document.createElement('div')
  el.className = 'tree-item' + (_active === path ? ' active' : '')
  el.dataset.path = path
  const parts = path.split('/')
  const name = parts.length > 1 ? parts.slice(1).join('/') : path
  el.innerHTML = `<span class="tree-icon">${fileIcon(path)}</span><span>${name}</span>`
  el.onclick = () => openFile(path)
  return el
}

// ── IDE Menu Bar Handlers ───────────────────────────────────────────────────
function toggleMenu(menuName, event) {
  if (event) event.stopPropagation();
  const allMenus = document.querySelectorAll('.menu-dropdown');
  const allTriggers = document.querySelectorAll('.menu-item');
  const targetMenu = document.getElementById(`menu-${menuName}`) || (menuName === 'templates' ? document.getElementById('templates-menu-popover') : null);
  const targetItem = document.querySelector(`.menu-item[data-menu="${menuName}"]`);
  
  const wasOpen = targetMenu && !targetMenu.classList.contains('hidden');
  
  allMenus.forEach(m => m.classList.add('hidden'));
  allTriggers.forEach(t => t.classList.remove('open'));
  
  if (!wasOpen && targetMenu && targetItem) {
    targetMenu.classList.remove('hidden');
    targetItem.classList.add('open');
  }
}

document.addEventListener('click', (e) => {
  if (!e.target.closest('.menu-item')) {
    document.querySelectorAll('.menu-dropdown').forEach(m => m.classList.add('hidden'));
    document.querySelectorAll('.menu-item').forEach(t => t.classList.remove('open'));
  }
});

// ── Right Panel Expand / Collapse ───────────────────────────────────────────
function toggleRightPanel() {
  const panel = document.querySelector('.preview-panel');
  if (!panel) return;
  panel.classList.toggle('collapsed');
  const isCollapsed = panel.classList.contains('collapsed');
  
  const btn = document.getElementById('btn-toggle-panel');
  if (btn) {
    btn.classList.toggle('active', isCollapsed);
    btn.title = isCollapsed ? 'Expand Right Panel (Cmd+B)' : 'Collapse Right Panel (Cmd+B)';
  }
  const menuLabel = document.getElementById('menu-toggle-panel-label');
  if (menuLabel) {
    menuLabel.textContent = isCollapsed ? 'Expand Right Panel' : 'Collapse Right Panel';
  }
  
  if (window._editor) {
    setTimeout(() => { window._editor.layout(); }, 60);
  }
}

// Global hotkeys (Cmd+B, Ctrl+B, etc.)
window.addEventListener('keydown', (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key === 'b') {
    e.preventDefault();
    toggleRightPanel();
  }
});

// ── Modals & Help Handlers ──────────────────────────────────────────────────
function showKeyboardShortcutsModal() {
  document.getElementById('shortcuts-modal')?.classList.remove('hidden');
}
function closeShortcutsModal() {
  document.getElementById('shortcuts-modal')?.classList.add('hidden');
}
function showAboutModal() {
  document.getElementById('about-modal')?.classList.remove('hidden');
}
function closeAboutModal() {
  document.getElementById('about-modal')?.classList.add('hidden');
}
function openDocumentation() {
  window.open('https://github.com/mcn-lang/mcn', '_blank');
}
function openSwaggerDocs() {
  window.open('/docs', '_blank');
  showToast('Opened API Swagger Explorer on /docs', 'info');
}
async function openDatabaseMigrationsModal() {
  showToast('Generating PostgreSQL / Supabase DDL migrations…', 'info');
  try {
    const r = await apiFetch('/api/database/export_migrations?dialect=postgres');
    const d = await r.json();
    if (d.success) {
      const sql = d.migration_sql;
      const modalHtml = `
        <div style="display:flex;flex-direction:column;gap:12px;max-width:550px;">
          <div style="display:flex;justify-content:space-between;align-items:center;">
            <div>
              <span style="font-size:10px;color:#38bdf8;font-weight:700;text-transform:uppercase;">DATABASE MIGRATION</span>
              <h3 style="font-size:14px;font-weight:800;color:#fff;margin:2px 0 0 0;">PostgreSQL &amp; Supabase DDL Schema</h3>
            </div>
            <button onclick="closeModal('db-mig-modal')" style="background:none;border:none;color:#94a3b8;font-size:16px;cursor:pointer;">✕</button>
          </div>
          <div style="background:#080e21;border:1px solid #1e293b;border-radius:8px;padding:12px;font-family:monospace;font-size:11px;color:#38bdf8;max-height:280px;overflow-y:auto;white-space:pre-wrap;">${sql.replace(/</g, '&lt;')}</div>
          <div style="display:flex;gap:8px;justify-content:flex-end;">
            <button onclick="navigator.clipboard.writeText(\`${sql.replace(/`/g, '\\`')}\`); showToast('SQL Migration copied to clipboard!', 'success');" class="btn btn-hero-run" style="padding:6px 14px;font-size:11px;">📋 Copy SQL DDL</button>
            <button onclick="closeModal('db-mig-modal')" class="btn" style="padding:6px 12px;font-size:11px;background:rgba(255,255,255,0.08);color:#fff;">Close</button>
          </div>
        </div>
      `;
      let m = document.getElementById('db-mig-modal');
      if (!m) {
        m = document.createElement('div');
        m.id = 'db-mig-modal';
        m.className = 'modal-backdrop';
        m.innerHTML = `<div class="modal-card" id="db-mig-card"></div>`;
        document.body.appendChild(m);
      }
      document.getElementById('db-mig-card').innerHTML = modalHtml;
      m.classList.remove('hidden');
    }
  } catch (err) {
    showToast('Failed to export migrations: ' + err.message, 'error');
  }
}
function showVsCodeExtensionModal() {
  const modalHtml = `
    <div style="display:flex;flex-direction:column;gap:12px;max-width:520px;">
      <div style="display:flex;justify-content:space-between;align-items:center;">
        <div>
          <span style="font-size:10px;color:#38bdf8;font-weight:700;text-transform:uppercase;">DEVELOPER TOOLING</span>
          <h3 style="font-size:14px;font-weight:800;color:#fff;margin:2px 0 0 0;">Official MCN VS Code Extension</h3>
        </div>
        <button onclick="closeModal('vscode-ext-modal')" style="background:none;border:none;color:#94a3b8;font-size:16px;cursor:pointer;">✕</button>
      </div>
      <div style="font-size:12px;color:#cbd5e1;line-height:1.5;">
        The official VS Code extension provides full TextMate syntax highlighting for <code>.mcn</code> contracts, services, endpoints, RBAC guards, and UI components, along with rich code snippets.
      </div>
      <div style="background:#080e21;border:1px solid #1e293b;border-radius:8px;padding:10px;font-family:monospace;font-size:11px;color:#38bdf8;">
        # Install into local VS Code extensions folder:<br>
        cp -r mcn-vscode-extension ~/.vscode/extensions/mcn-lang
      </div>
      <div style="display:flex;gap:8px;justify-content:flex-end;">
        <button onclick="navigator.clipboard.writeText('cp -r mcn-vscode-extension ~/.vscode/extensions/mcn-lang'); showToast('Install command copied!', 'success');" class="btn btn-hero-run" style="padding:6px 14px;font-size:11px;">📋 Copy Install Command</button>
        <button onclick="closeModal('vscode-ext-modal')" class="btn" style="padding:6px 12px;font-size:11px;background:rgba(255,255,255,0.08);color:#fff;">Close</button>
      </div>
    </div>
  `;
  let m = document.getElementById('vscode-ext-modal');
  if (!m) {
    m = document.createElement('div');
    m.id = 'vscode-ext-modal';
    m.className = 'modal-backdrop';
    m.innerHTML = `<div class="modal-card" id="vscode-ext-card"></div>`;
    document.body.appendChild(m);
  }
  document.getElementById('vscode-ext-card').innerHTML = modalHtml;
  m.classList.remove('hidden');
}
function clearOutputLog() {
  const ct = document.getElementById('output-log');
  if (ct) ct.innerHTML = '';
}

async function resetWorkspacePrompt() {
  const confirmed = await showIdeConfirm(
    'Reset Workspace Files',
    'Are you sure you want to reset all workspace files to the default starter template? All unsaved modifications will be reverted.',
    {
      danger: true,
      confirmText: 'Reset Workspace',
      cancelText: 'Keep Files'
    }
  );
  if (confirmed) {
    await resetWorkspace();
    showToast('Workspace reset to default starter template', 'success');
  }
}

async function resetWorkspace() {
  try {
    for (const [path, model] of _models.entries()) { model.dispose(); }
    _models.clear(); _tabState.clear(); _openTabs = []; _active = null;
    renderTabs();
    const r = await apiFetch('/api/workspace/reset', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({})
    });
    const d = await r.json();
    if (d.success) {
      appendLog('success', 'Workspace reset to default starter template');
      await loadFileTree();
      await openFile('backend/main.mcn');
    }
  } catch (err) {
    appendLog('error', 'Reset workspace failed: ' + err.message);
  }
}

// ── Categorized Templates & Examples ──────────────────────────────────────────
let _allExamples = [];

async function loadExamples() {
  try {
    const r = await apiFetch('/api/examples')
    if (!r.ok) { console.warn('Examples failed:', r.status); return }
    const examples = await r.json()
    _allExamples = examples;
    renderTemplatesDropdown(examples);
  } catch (err) {
    console.warn('loadExamples error:', err)
  }
}

function renderTemplatesDropdown(examples) {
  const popover = document.getElementById('templates-menu-popover');
  if (!popover) return;
  popover.innerHTML = '';
  
  const categoryMeta = {
    repl:         { title: "REPL & Quick Scripts" },
    internal_app: { title: "Internal Tools & Web Apps" },
    flutter_app:  { title: "Mobile Apps (Flutter)" },
    backend:      { title: "Backend & Microservices" }
  };
  
  const categories = ['repl', 'internal_app', 'flutter_app', 'backend'];
  for (const cat of categories) {
    const items = examples.filter(e => (e.category || 'repl') === cat);
    if (items.length === 0) continue;
    const meta = categoryMeta[cat] || { title: cat };
    
    const grp = document.createElement('div');
    grp.className = 'templates-menu-group';
    grp.innerHTML = `<div class="templates-menu-group-title">${meta.title}</div>`;
    
    for (const ex of items) {
      const it = document.createElement('div');
      it.className = 'templates-menu-item';
      it.innerHTML = `
        <div class="templates-menu-item-left">
          <span class="templates-menu-item-name">${ex.name}</span>
          <span class="templates-menu-item-desc">${ex.description || ''}</span>
        </div>
        <span class="template-badge ${cat}">${ex.badge || (ex.project ? 'Project' : 'Script')}</span>
      `;
      it.onclick = () => {
        popover.classList.add('hidden');
        document.querySelectorAll('.menu-item').forEach(t => t.classList.remove('open'));
        loadExample(ex);
      };
      grp.appendChild(it);
    }
    popover.appendChild(grp);
  }
}

async function loadExample(ex) {
  _currentExample = ex;
  _mobileRoute = 'home';
  setStatus('Loading ' + ex.name + '…')
  
  // Switch workspace mode accordingly if relevant
  if (ex.category === 'flutter_app') {
    switchWorkspace('flutter');
  } else if (ex.category === 'repl') {
    switchWorkspace('repl');
  } else if (ex.category === 'internal_app') {
    switchWorkspace('react');
  }
  
  if (ex.project && ex.files) {
    // Multi-file project
    for (const [path, model] of _models.entries()) { model.dispose() }
    _models.clear(); _tabState.clear(); _openTabs = []; _active = null
    renderTabs()
    const r = await apiFetch('/api/workspace/reset', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ files: ex.files })
    })
    const d = await r.json()
    if (!d.success) { appendLog('error', '✗ ' + d.error); return }
    _devOn = false
    _built = false
    const btnToggle = document.getElementById('btn-toggle-server')
    if (btnToggle) btnToggle.textContent = 'Start Server'
    const btnDownload = document.getElementById('btnDownload')
    if (btnDownload) btnDownload.disabled = true
    const srvBadge = document.getElementById('server-badge')
    if (srvBadge) { srvBadge.textContent = 'No dev server'; srvBadge.className = ''; }
    const stSrv = document.getElementById('status-srv')
    if (stSrv) stSrv.textContent = ''
    hidePreview()
    await loadFileTree()
    await openFile(ex.open || ex.files[0].path)
    setStatus('Template loaded: ' + ex.name, 'ok')
    appendLog('success', `Loaded "${ex.name}" template (${d.written.length} files). Click Run or Build to test.`)
  } else {
    // Single-file snippet
    const targetFile = ex.file || 'backend/main.mcn';
    await apiFetch('/api/workspace/file', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: targetFile, content: ex.code })
    })
    if (_models.has(targetFile)) {
      _models.get(targetFile).setValue(ex.code)
      if (_tabState.has(targetFile)) _tabState.get(targetFile).dirty = false
    }
    await loadFileTree()
    await openFile(targetFile)
    renderTabs()
    setStatus('Loaded: ' + ex.name, 'ok')
    appendLog('success', `Loaded "${ex.name}" snippet into ${targetFile}. Click Run to execute.`)
  }
}

// ── Tabs ─────────────────────────────────────────────────────────────────
async function openFile(path) {
  // Auto-expand folder
  const parts = path.split('/')
  if (parts.length > 1) {
    const folder = parts[0]
    if (!_expandedFolders.has(folder)) {
      _expandedFolders.add(folder)
      if (window._workspaceFiles) {
        renderFileTree(window._workspaceFiles)
      }
    }
  }

  if (!_models.has(path)) {
    try {
      const r = await apiFetch(`/api/workspace/file?path=${encodeURIComponent(path)}`)
      const d = await r.json()
      if (d.error) { appendLog('error', d.error); return }
      const ext = path.endsWith('.mcn') ? 'mcn'
                : path.endsWith('.tsx') || path.endsWith('.ts') ? 'typescript'
                : path.endsWith('.json') ? 'json'
                : path.endsWith('.css') ? 'css'
                : 'plaintext'
      const uri   = monaco.Uri.parse('file:///' + path)
      const model = monaco.editor.createModel(d.content, ext, uri)
      _models.set(path, model)
      _tabState.set(path, { dirty: false })
    } catch (e) { appendLog('error', 'Cannot open ' + path); return }
  }
  if (!_openTabs.find(t => t.path === path)) _openTabs.push({ path })
  _active = path
  const model = _models.get(path)
  window._editor.setModel(model)
  window._editor.updateOptions({ readOnly: false })
  const msg = document.getElementById('no-file-msg')
  msg && msg.classList.add('hidden')
  renderTabs()
  syncTreeActive()
}

function closeTab(path, e) {
  if (e) e.stopPropagation()
  const idx = _openTabs.findIndex(t => t.path === path)
  if (idx < 0) return
  _openTabs.splice(idx, 1)
  if (_models.has(path)) { _models.get(path).dispose(); _models.delete(path) }
  _tabState.delete(path)
  if (_active === path) {
    const next = _openTabs[Math.min(idx, _openTabs.length - 1)]
    if (next) openFile(next.path)
    else {
      _active = null
      window._editor.setModel(null)
      document.getElementById('no-file-msg')?.classList.remove('hidden')
      renderTabs()
    }
  } else { renderTabs() }
}

function renderTabs() {
  const bar = document.getElementById('tab-bar')
  bar.innerHTML = ''
  for (const t of _openTabs) {
    const dirty    = _tabState.get(t.path)?.dirty
    const isActive = t.path === _active
    const el = document.createElement('div')
    el.className = 'tab' + (isActive ? ' active' : '') + (dirty ? ' dirty' : '')
    el.onclick = () => openFile(t.path)
    const name = t.path.split('/').pop()
    el.innerHTML = `<span class="tree-icon" style="font-size:11px">${fileIcon(t.path)}</span><span class="tab-label">${name}</span><span class="tab-close" onclick="closeTab('${t.path}', event)">×</span>`
    bar.appendChild(el)
  }
}

function syncTreeActive() {
  document.querySelectorAll('.tree-item[data-path]').forEach(el =>
    el.classList.toggle('active', el.dataset.path === _active))
}

// ── Save ─────────────────────────────────────────────────────────────────
async function saveActiveTab() {
  if (!_active) return
  const model = _models.get(_active)
  if (!model) return
  await apiFetch('/api/workspace/file', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path: _active, content: model.getValue() })
  })
  if (_tabState.has(_active)) _tabState.get(_active).dirty = false
  renderTabs()
}

async function saveAllTabs() {
  for (const [path, model] of _models.entries()) {
    try {
      await apiFetch('/api/workspace/file', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path, content: model.getValue() })
      })
      const st = _tabState.get(path)
      if (st) st.dirty = false
    } catch (_) {}
  }
  renderTabs()
}

// ── Run MCN ──────────────────────────────────────────────────────────────
// Show an MCN error report: log lines, a squiggle at the location, and the banner
function showRunError(model, d) {
  const lines = String(d.error || 'Execution failed').split('\n')
  lines.forEach((line, i) => {
    if (i === 0) appendLog('error', '✗ ' + line)
    else if (line.startsWith('Hint:')) appendLog('info', '  ' + line)
    else appendLog('dim', '  ' + line)
  })
  const diag = d.diagnostic
  if (!diag || !diag.line || typeof monaco === 'undefined') return
  monaco.editor.setModelMarkers(model, 'mcn-run', [{
    startLineNumber: diag.line, startColumn: Math.max(diag.col, 1),
    endLineNumber: diag.line, endColumn: Math.max(diag.col, 1) + Math.max(diag.length || 1, 1),
    message: diag.message + (diag.hint ? '\n' + diag.hint : ''),
    severity: monaco.MarkerSeverity.Error,
  }])
  if (window._editor && window._editor.getModel() === model) {
    window._editor.revealLineInCenterIfOutsideViewport(diag.line)
  }
  const banner = document.getElementById('editor-diagnostic-banner')
  const badge = document.getElementById('diag-badge')
  const msg = document.getElementById('diag-msg')
  if (badge) badge.textContent = diag.kind.toUpperCase()
  if (msg) msg.textContent = `Line ${diag.line}: ${diag.message}`
  if (banner) banner.classList.remove('hidden')
}

function clearRunError(model) {
  if (typeof monaco !== 'undefined') monaco.editor.setModelMarkers(model, 'mcn-run', [])
  dismissDiagnosticBanner()
}

async function runActiveFile() {
  if (!_active) { appendLog('warn', 'No file open'); return }
  const model = _models.get(_active)
  if (!model) return
  await saveActiveTab()
  setStatus('Running…')
  switchPanel('output', document.querySelector('[data-panel="output"]'))
  appendLog('info', '▶ Executing: ' + _active)
  const startTime = performance.now()
  try {
    const r = await apiFetch('/api/execute', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code: model.getValue() })
    })
    const d = await r.json()
    const elapsed = Math.round(performance.now() - startTime)
    
    if (d.output && d.output.length > 0) {
      for (const l of d.output) appendLog('', l)
    }
    
    if (!d.success) {
      showRunError(model, d)
      setStatus('Error', 'err')
    } else {
      clearRunError(model)
      if (d.result !== null && d.result !== undefined && d.result !== '' && d.result !== 'None') {
        appendLog('success', '=> ' + d.result)
      } else if (!d.output || d.output.length === 0) {
        appendLog('success', `✓ Executed successfully (${elapsed}ms)`)
      }
      setStatus(`Done (${elapsed}ms)`, 'ok')
      // Auto-refresh simulators
      refreshDBTables()
      refreshIoTSimulator()
      refreshAIInspector()
    }
  } catch (e) {
    appendLog('error', '✗ Execution failed: ' + e.message)
    setStatus('Error', 'err')
  }
}

