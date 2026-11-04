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

  // Build a nested tree: frontend/src/components/ui/button.tsx becomes four folders and a file
  const root = { folders: {}, files: [] }
  for (const f of filteredFiles) {
    const parts = f.path.split('/')
    let node = root
    for (let i = 0; i < parts.length - 1; i++) {
      const key = parts.slice(0, i + 1).join('/')
      node = node.folders[parts[i]] || (node.folders[parts[i]] = { key, folders: {}, files: [] })
    }
    node.files.push(f.path)
  }
  const topOrder = ['backend', 'ui', 'frontend', 'mobile', 'scripts']
  const sortFolders = (names, depth) => depth === 0
    ? [...topOrder.filter(n => names.includes(n)), ...names.filter(n => !topOrder.includes(n)).sort()]
    : names.sort()

  const renderNode = (node, parent, depth) => {
    for (const name of sortFolders(Object.keys(node.folders), depth)) {
      const sub = node.folders[name]
      const isExpanded = _expandedFolders.has(sub.key)
      const header = document.createElement('div')
      header.className = 'tree-folder' + (isExpanded ? ' expanded' : '')
      header.style.paddingLeft = (12 + depth * 14) + 'px'
      header.title = sub.key
      header.innerHTML = `
        <span class="folder-caret">${isExpanded ? '▼' : '▶'}</span>
        <span class="tree-folder-icon">${isExpanded ? '▾' : '▸'}</span>
        <span>${escapeHtml(name)}</span>`
      const contents = document.createElement('div')
      contents.className = 'tree-folder-contents'
      contents.style.display = isExpanded ? 'block' : 'none'
      renderNode(sub, contents, depth + 1)
      header.onclick = () => {
        const open = !_expandedFolders.has(sub.key)
        open ? _expandedFolders.add(sub.key) : _expandedFolders.delete(sub.key)
        header.classList.toggle('expanded', open)
        header.querySelector('.folder-caret').textContent = open ? '▼' : '▶'
        header.querySelector('.tree-folder-icon').textContent = open ? '▾' : '▸'
        contents.style.display = open ? 'block' : 'none'
      }
      parent.appendChild(header)
      parent.appendChild(contents)
    }
    for (const path of node.files.sort()) {
      const item = makeFileItem(path)
      item.style.paddingLeft = (depth === 0 ? 12 : 14 + depth * 14) + 'px'
      parent.appendChild(item)
    }
  }
  renderNode(root, ct, 0)
  syncTreeActive()
}

function makeFileItem(path) {
  const el = document.createElement('div')
  el.className = 'tree-item' + (_active === path ? ' active' : '')
  el.dataset.path = path
  const name = path.split('/').pop()
  el.title = path
  el.innerHTML = `<span class="tree-icon">${fileIcon(path)}</span><span>${escapeHtml(name)}</span>`
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
        Syntax highlighting, completions, hover docs, and errors underlined as you type (the same checks as <code>mcn check</code>), plus commands to run, test, serve and open Studio.
      </div>
      <div style="background:#080e21;border:1px solid #1e293b;border-radius:8px;padding:10px;font-family:monospace;font-size:11px;color:#38bdf8;">
        # Installs the extension bundled with MCN (needs the <code>code</code> command on PATH):<br>
        mcn vscode
      </div>
      <div style="display:flex;gap:8px;justify-content:flex-end;">
        <button onclick="navigator.clipboard.writeText('mcn vscode'); showToast('Install command copied!', 'success');" class="btn btn-hero-run" style="padding:6px 14px;font-size:11px;">📋 Copy Install Command</button>
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
    } else {
      appendLog('error', '✗ ' + d.error);
      await loadFileTree();
    }
  } catch (err) {
    appendLog('error', 'Reset workspace failed: ' + err.message);
  }
}

// ── Categorized Templates & Examples ──────────────────────────────────────────
let _allExamples = [];

const TEMPLATE_CATEGORIES = {
  internal_app: { title: "Web apps & AI" },
  data:         { title: "Data & ML" },
  flutter_app:  { title: "Mobile & IoT" },
  backend:      { title: "Backends & APIs" },
  repl:         { title: "Learn the language" },
};
const NEW_TEMPLATES = new Set(['data_labeling', 'ml_training_lab']);
let _galleryCategory = 'all';

function openTemplateGallery() {
  document.getElementById('template-gallery').classList.remove('hidden');
  try { localStorage.setItem('mcn_gallery_seen', '1') } catch (e) {}
  renderTemplateGallery();
  setTimeout(() => document.getElementById('tg-search').focus(), 50);
}

function closeTemplateGallery() {
  document.getElementById('template-gallery').classList.add('hidden');
}

async function maybeShowGalleryOnFirstVisit() {
  // Newcomers see the gallery once, in Studio's own workspace (not when editing their project)
  try {
    const info = await (await apiFetch('/api/workspace/info')).json()
    const ws = document.getElementById('status-ws')
    if (ws && info.path) ws.textContent = info.path
    let seen = false
    try { seen = !!localStorage.getItem('mcn_gallery_seen') } catch (e) {}
    if (!seen && !info.own_project) openTemplateGallery()
  } catch (e) {}
}

function renderTemplateGallery() {
  const chips = document.getElementById('tg-chips')
  const grid = document.getElementById('tg-grid')
  const q = (document.getElementById('tg-search').value || '').trim().toLowerCase()
  const cats = Object.keys(TEMPLATE_CATEGORIES).filter(c => _allExamples.some(e => (e.category || 'repl') === c))
  chips.innerHTML = ['all', ...cats].map(c => {
    const label = c === 'all' ? `All (${_allExamples.length})` : TEMPLATE_CATEGORIES[c].title
    return `<button class="tg-chip" role="tab" aria-selected="${c === _galleryCategory}" onclick="_galleryCategory='${c}';renderTemplateGallery()">${escapeHtml(label)}</button>`
  }).join('')
  const matches = _allExamples.filter(e =>
    (_galleryCategory === 'all' || (e.category || 'repl') === _galleryCategory) &&
    (!q || `${e.name} ${e.description} ${e.badge}`.toLowerCase().includes(q)))
  if (!matches.length) {
    grid.innerHTML = `<div class="tg-empty">No templates match “${escapeHtml(q)}”.</div>`
    return
  }
  let html = ''
  for (const c of cats) {
    const items = matches.filter(e => (e.category || 'repl') === c)
    if (!items.length) continue
    html += `<div class="tg-group">${escapeHtml(TEMPLATE_CATEGORIES[c].title)}</div>`
    for (const e of items) {
      const paths = (e.files || []).map(f => f.path || f)
      const tags = []
      if (paths.some(p => p.startsWith('backend/')) || e.file) tags.push('Backend')
      if (paths.some(p => p.startsWith('ui/'))) tags.push('Web + mobile UI')
      if (!e.project) tags.push('Single file')
      html += `<button class="tg-item" onclick="openTemplateFromGallery('${escapeHtml(e.id)}')">
        <div class="tg-item-top"><span class="tg-item-name">${escapeHtml(e.name)}</span>${NEW_TEMPLATES.has(e.id) ? '<span class="tg-new">NEW</span>' : ''}</div>
        <div class="tg-item-desc">${escapeHtml(e.description || '')}</div>
        <div class="tg-item-meta"><span class="template-badge ${escapeHtml(e.category || 'repl')}">${escapeHtml(e.badge || '')}</span>${tags.map(t => `<span class="tg-tag">${t}</span>`).join('')}</div>
      </button>`
    }
  }
  grid.innerHTML = html
}

const FEATURED_TEMPLATES = ['ai_agent_builder', 'ops_dashboard', 'data_labeling', 'ml_training_lab', 'iot_smart_home', 'hello']

function renderStarterHub() {
  const grid = document.getElementById('starter-grid')
  if (!grid) return
  const items = FEATURED_TEMPLATES.map(id => _allExamples.find(e => e.id === id)).filter(Boolean)
  grid.innerHTML = items.map(e => `
    <div class="starter-card" role="button" tabindex="0" onclick="openTemplateFromGallery('${escapeHtml(e.id)}')"
         onkeydown="if(event.key==='Enter')openTemplateFromGallery('${escapeHtml(e.id)}')">
      <div class="starter-card-hdr"><span class="starter-card-tag">${escapeHtml(e.badge || '')}</span></div>
      <div class="starter-card-title">${escapeHtml(e.name)}</div>
      <div class="starter-card-desc">${escapeHtml(e.description || '')}</div>
    </div>`).join('')
}

function openTemplateFromGallery(id) {
  const ex = _allExamples.find(e => e.id === id)
  if (!ex) return
  closeTemplateGallery()
  loadExample(ex)
}

document.addEventListener('keydown', e => {
  if (e.key === 'Escape' && !document.getElementById('template-gallery').classList.contains('hidden')) closeTemplateGallery()
})
document.getElementById('template-gallery').addEventListener('click', function (e) {
  if (e.target === this) closeTemplateGallery()
})

async function loadExamples() {
  try {
    const r = await apiFetch('/api/examples')
    if (!r.ok) { console.warn('Examples failed:', r.status); return }
    const examples = await r.json()
    _allExamples = examples;
    renderTemplatesDropdown(examples);
    renderStarterHub();
    maybeShowGalleryOnFirstVisit();
  } catch (err) {
    console.warn('loadExamples error:', err)
  }
}

function renderTemplatesDropdown(examples) {
  const popover = document.getElementById('templates-menu-popover');
  if (!popover) return;
  popover.innerHTML = '';

  const browse = document.createElement('div');
  browse.className = 'templates-menu-item';
  browse.innerHTML = `<div class="templates-menu-item-left"><span class="templates-menu-item-name">Browse all ${examples.length} templates…</span>
    <span class="templates-menu-item-desc">Search and filter by category</span></div>`;
  browse.onclick = () => {
    popover.classList.add('hidden');
    document.querySelectorAll('.menu-item').forEach(t => t.classList.remove('open'));
    openTemplateGallery();
  };
  popover.appendChild(browse);

  const categoryMeta = TEMPLATE_CATEGORIES;
  const categories = Object.keys(TEMPLATE_CATEGORIES);
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
  } else if (ex.category === 'internal_app' || ex.category === 'data') {
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
    if (!d.success) { appendLog('error', '✗ ' + d.error); await loadFileTree(); return }
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
  // Expand every folder above the file
  const parts = path.split('/')
  let expanded = false
  for (let i = 1; i < parts.length; i++) {
    const folder = parts.slice(0, i).join('/')
    if (!_expandedFolders.has(folder)) { _expandedFolders.add(folder); expanded = true }
  }
  if (expanded && window._workspaceFiles) renderFileTree(window._workspaceFiles)

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
      // Two quick opens of the same file (e.g. at startup) share one model
      const model = monaco.editor.getModel(uri) || monaco.editor.createModel(d.content, ext, uri)
      _models.set(path, model)
      _tabState.set(path, { dirty: false })
    } catch (e) {
      if (typeof appendLog === 'function') appendLog('error', 'Cannot open ' + path + ': ' + e.message)
      else console.warn('Cannot open ' + path, e)
      return
    }
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

