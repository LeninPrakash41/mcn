// ── Output log ────────────────────────────────────────────────────────────
function appendLog(type, text) {
  const ct = document.getElementById('output-log')
  const el = document.createElement('div')
  el.className = 'log-line ' + (type || '')
  el.textContent = text
  ct.appendChild(el)
  ct.scrollTop = ct.scrollHeight
}

// ── Status ────────────────────────────────────────────────────────────────
function setStatus(text, state) {
  document.getElementById('status-text').textContent = text
  const dot = document.getElementById('status-dot')
  dot.className = state === 'ok' ? 'ok' : state === 'err' ? 'err' : ''
}

// ── Reviewing a patch from the agent interface (used by the Agent panel) ────
// The agent inspects, finds and explains, then builds a patch of create / modify /
// remove operations and validates and tests it. Nothing is written until Apply.

function _el(tag, cls, text) {
  const e = document.createElement(tag)
  if (cls) e.className = cls
  if (text !== undefined) e.textContent = text
  return e
}

function _renderDiff(diff) {
  const pre = _el('pre', 'change-diff')
  diff.split('\n').forEach(line => {
    if (!line) return
    const cls = line.startsWith('+++') || line.startsWith('---') ? 'file'
      : line.startsWith('@@') ? 'hunk' : line.startsWith('+') ? 'add' : line.startsWith('-') ? 'del' : ''
    pre.appendChild(_el('span', cls, line + '\n'))
  })
  return pre
}

function _renderReview(prefix, ev, box) {
  box.replaceChildren()
  if (ev.summary) {
    if (typeof _apRichText === 'function') {          // `code` and **bold**, like the Agent panel
      const rich = _apRichText(ev.summary)
      rich.classList.add('change-summary')
      box.appendChild(rich)
    } else {
      box.appendChild(_el('p', 'change-summary', ev.summary))
    }
  }
  if (!ev.patch) {
    box.appendChild(_el('p', 'change-line bad', 'No change was made.'))
    return
  }
  const v = ev.validation, t = ev.tests
  box.appendChild(_el('div', 'change-line ' + (v.ok ? 'ok' : 'bad'),
    (v.ok ? '✓ Valid' : '✗ Not valid') + ': changes ' + (v.changed.join(', ') || 'nothing')))
  const problems = [].concat(v.parse_errors || [], v.type_errors || [], v.map_errors || [], v.new_issues || [],
    (v.outside_module || []).map(x => 'Outside the module: ' + x))
  if (problems.length) {
    const ul = _el('ul', 'change-problems')
    problems.slice(0, 8).forEach(p => ul.appendChild(_el('li', '', p)))
    box.appendChild(ul)
  }
  Object.entries(v.affects || {}).forEach(([kind, ids]) =>
    box.appendChild(_el('div', 'change-line', `Affects ${kind}: ${ids.join(', ')}`)))
  box.appendChild(_el('div', 'change-line ' + (t.ok ? 'ok' : 'bad'),
    `${t.ok ? '✓' : '✗'} ${t.passed} of ${t.total} test(s) passed`))
  ;(t.failed || []).slice(0, 5).forEach(f => box.appendChild(_el('div', 'change-line bad', `  ✗ ${f.test}: ${f.error}`)))
  box.appendChild(_renderDiff(ev.diff || ''))
  const actions = _el('div', 'change-actions')
  const discard = _el('button', 'btn btn-sm', 'Discard')
  discard.onclick = () => { box.classList.add('hidden'); showToast('Change discarded; nothing was written', 'info') }
  const apply = _el('button', 'btn btn-primary btn-sm', ev.ok ? 'Apply change' : 'Can’t apply: fix the problems first')
  apply.disabled = !ev.ok
  apply.onclick = () => applyChange(prefix, ev, box, apply)
  actions.append(discard, apply)
  box.appendChild(actions)
}

async function applyChange(prefix, ev, box, button) {
  button.disabled = true
  try {
    const r = await apiFetch('/api/agent/change/apply', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ patch: ev.patch })
    })
    const data = await r.json()
    if (!data.success) {
      button.disabled = false
      await showIdeAlert('Not Applied', data.error || 'The change could not be applied', 'error')
      return
    }
    Object.entries(data.contents || {}).forEach(([path, content]) => {
      if (_models.has(path)) {
        _models.get(path).setValue(content)
        if (_tabState.has(path)) _tabState.get(path).dirty = false
      }
    })
    await loadFileTree()
    showToast('Change applied to ' + data.files.join(', '), 'success')
    const card = document.getElementById(`${prefix}-success-card`)
    if (!card) {                          // the Agent panel: keep the diff, replace the buttons with a note
      const actions = box.querySelector('.change-actions')
      if (actions) actions.replaceWith(_el('div', 'change-line ok', '✓ Applied to ' + data.files.join(', ')))
      return
    }
    box.classList.add('hidden')
    const badge = document.getElementById(`${prefix}-success-badge`)
    if (badge) badge.textContent = '✓ ' + data.files.join(', ')
    const summary = document.getElementById(`${prefix}-success-summary`)
    if (summary) summary.textContent = ev.summary || 'Applied the reviewed change.'
    card.classList.remove('hidden')
  } catch (e) {
    button.disabled = false
    await showIdeAlert('Not Applied', 'Error: ' + e.message, 'error')
  }
}

// ── Deploy ──────────────────────────────────────────────────────────────────

function openDeployModal() {
  const m = document.getElementById('deploy-modal')
  m.classList.remove('hidden')
  document.getElementById('deploy-status').classList.add('hidden')
  document.getElementById('deploy-result').classList.add('hidden')
  document.getElementById('deploy-vercel-result').classList.add('hidden')
  document.getElementById('deploy-submit').disabled = false
  onDeployTargetChange()
}

function onDeployTargetChange() {
  const vercel = document.getElementById('deploy-target').value === 'vercel'
  document.getElementById('deploy-vercel-opts').style.display = vercel ? 'flex' : 'none'
  document.getElementById('deploy-submit').textContent = vercel ? 'Deploy to Vercel' : '⬇ Build & Download'
}

async function deployToVercel(appName) {
  const statusEl = document.getElementById('deploy-status')
  const statusTxt = document.getElementById('deploy-status-text')
  const submitBtn = document.getElementById('deploy-submit')
  const resultEl = document.getElementById('deploy-vercel-result')
  statusEl.classList.remove('hidden')
  resultEl.classList.add('hidden')
  statusTxt.textContent = 'Building and uploading to Vercel… this takes a minute or two'
  submitBtn.disabled = true
  try {
    const start = await apiFetch('/api/deploy/vercel', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ app_name: appName, prod: document.getElementById('deploy-prod').checked })
    })
    const s = await start.json()
    if (!s.success) throw new Error(s.error)
    let job
    for (;;) {
      await new Promise(r => setTimeout(r, 3000))
      job = await (await apiFetch('/api/deploy/vercel')).json()
      if (job.state !== 'running') break
    }
    if (job.state !== 'done') throw new Error(job.error || 'The deployment failed')
    statusEl.classList.add('hidden')
    const link = document.getElementById('deploy-vercel-url')
    link.href = job.url
    link.textContent = job.url
    resultEl.classList.remove('hidden')
    showToast('Deployed to Vercel', 'success')
  } catch (e) {
    statusEl.classList.add('hidden')
    await showIdeAlert('Deploy Failed', e.message, 'error')
  } finally {
    submitBtn.disabled = false
  }
}

function closeDeployModal() {
  document.getElementById('deploy-modal').classList.add('hidden')
}

async function submitDeploy() {
  const appName = document.getElementById('deploy-name').value.trim() || 'mcn-app'
  const target  = document.getElementById('deploy-target').value
  if (target === 'vercel') return deployToVercel(appName)

  const statusEl = document.getElementById('deploy-status')
  const statusTxt = document.getElementById('deploy-status-text')
  const resultEl  = document.getElementById('deploy-result')
  const submitBtn = document.getElementById('deploy-submit')

  statusEl.classList.remove('hidden')
  resultEl.classList.add('hidden')
  statusTxt.textContent = 'Building deployment package…'
  submitBtn.disabled = true

  try {
    const resp = await apiFetch('/api/deploy', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ app_name: appName, target })
    })

    const data = await resp.json()
    if (!resp.ok) throw new Error(data.error || resp.statusText)

    // Trigger browser download of the zip
    const zipBytes = Uint8Array.from(atob(data.zip_b64), c => c.charCodeAt(0))
    const blob = new Blob([zipBytes], { type: 'application/zip' })
    const url  = URL.createObjectURL(blob)
    const a    = document.createElement('a')
    a.href     = url
    a.download = `${appName}.zip`
    a.click()
    URL.revokeObjectURL(url)

    // Show result panel
    statusEl.classList.add('hidden')
    document.getElementById('deploy-docker-cmd').textContent = data.docker_cmd
    document.getElementById('deploy-files').textContent =
      (data.files_included || []).map(f => '• ' + f).join('\n')
    resultEl.classList.remove('hidden')
    submitBtn.disabled = false
    submitBtn.textContent = '⬇ Download Again'
    showToast(`Deployment package ${appName}.zip downloaded!`, 'success')
  } catch (e) {
    statusEl.classList.add('hidden')
    submitBtn.disabled = false
    await showIdeAlert('Deploy Failed', 'Deploy failed: ' + e.message, 'error')
  }
}

document.getElementById('deploy-modal').addEventListener('click', function(e) {
  if (e.target === this) closeDeployModal()
})

// ── Accounts ────────────────────────────────────────────────────────────────
// Installed Studio ("local") has no accounts of its own: Sign in connects the
// person's MCN account server through the browser, and the server keeps the
// token. Hosted Studio requires everyone to sign in here, and each person gets
// their own workspace.

let _studioMode = 'local'
let _accountInfo = null          // local: {signed_in, user, account_url, configured}
let _accountPoll = null          // local: the sign-in being waited on
let _authToken = localStorage.getItem('mcn_token') || ''
let _authUser  = null
let _authMode  = 'login'

try { _authUser = JSON.parse(localStorage.getItem('mcn_user') || 'null') } catch(e) {}

function _getAuthHeaders() {
  return (_studioMode === 'hosted' && _authToken) ? { 'Authorization': 'Bearer ' + _authToken } : {}
}

function _isStudioApi(url) {
  try {
    const u = new URL(typeof url === 'string' ? url : url.url, location.href)
    return u.origin === location.origin && u.pathname.startsWith('/api/')
  } catch (e) { return false }
}

// Every same-origin API call carries the hosted sign-in, and a "sign in first"
// answer opens the sign-in dialog.
const _nativeFetch = window.fetch.bind(window)
window.fetch = async function (url, opts = {}) {
  const api = _isStudioApi(url)
  if (api && _studioMode === 'hosted' && _authToken) {
    opts = Object.assign({}, opts, { headers: Object.assign({}, opts.headers || {}, _getAuthHeaders()) })
  }
  const res = await _nativeFetch(url, opts)
  if (api && res.status === 401 && _studioMode === 'hosted') {
    res.clone().json().then(d => { if (d && d.needs_login) _requireHostedSignIn() }).catch(() => {})
  }
  return res
}

// Kept for existing callers; fetch itself now adds the headers
async function apiFetch(url, opts = {}) {
  return fetch(url, opts)
}

function _setTokenCookie(token) {
  // Previews (iframes) and downloads can't send headers; hosted Studio reads this on GET only
  const secure = location.protocol === 'https:' ? '; Secure' : ''
  document.cookie = token
    ? `mcn_token=${encodeURIComponent(token)}; Path=/; SameSite=Strict${secure}`
    : 'mcn_token=; Path=/; Max-Age=0; SameSite=Strict'
}

function _requireHostedSignIn() {
  if (_authToken) {
    // The token expired or was revoked
    _authToken = ''; _authUser = null
    localStorage.removeItem('mcn_token'); localStorage.removeItem('mcn_user')
    _setTokenCookie('')
  }
  openAuthModal()
}

function openAuthModal() {
  const m = document.getElementById('auth-profile-modal');
  if (!m) return;
  m.classList.remove('hidden');
  renderAuthModalState();
}

function closeAuthModal() {
  if (_studioMode === 'hosted' && !_authToken) return;   // hosted Studio needs a sign-in
  const m = document.getElementById('auth-profile-modal');
  if (m) m.classList.add('hidden');
}

function setAuthMode(mode) {
  _authMode = mode;
  const loginTab = document.getElementById('auth-tab-btn-login');
  const regTab = document.getElementById('auth-tab-btn-register');
  const submitBtn = document.getElementById('btn-auth-submit');
  const msgEl = document.getElementById('auth-modal-msg');
  if (msgEl) msgEl.style.display = 'none';
  const on = mode === 'login' ? loginTab : regTab
  const off = mode === 'login' ? regTab : loginTab
  if (on) { on.style.color = 'var(--accent)'; on.style.borderBottomColor = 'var(--accent)' }
  if (off) { off.style.color = 'var(--muted)'; off.style.borderBottomColor = 'transparent' }
  if (submitBtn) submitBtn.textContent = mode === 'login' ? 'Sign In' : 'Create Account';
}

function _show(id, on, display = 'block') {
  const el = document.getElementById(id)
  if (el) el.style.display = on ? display : 'none'
}

function _setText(id, text) {
  const el = document.getElementById(id)
  if (el) el.textContent = text
}

function _setStatus(text, color) {
  const el = document.getElementById('status-tenant')
  if (el) { el.textContent = text; el.style.color = color || 'var(--muted)' }
}

async function renderAuthModalState() {
  const authLabel = document.getElementById('user-auth-label');
  const closeBtn = document.getElementById('auth-modal-close');

  if (_studioMode === 'local') {
    _show('auth-profile-view', false); _show('auth-form-view', false); _show('auth-device-view', true, 'flex')
    if (closeBtn) closeBtn.style.display = ''
    _setText('auth-modal-title', 'Your MCN account')
    _setText('auth-modal-sub', 'Optional: Studio works fully without signing in')
    const info = _accountInfo || {}
    const waiting = !!_accountPoll
    _show('acct-waiting', waiting)
    _show('acct-signed-in', !waiting && info.signed_in)
    _show('acct-signed-out', !waiting && !info.signed_in)
    if (info.signed_in) {
      const email = (info.user && info.user.email) || 'MCN account'
      _setText('acct-email', email)
      _setText('acct-server', (info.account_url || '').replace(/^https?:\/\//, '') + (info.offline ? ' · offline' : ''))
      if (authLabel) authLabel.textContent = email.split('@')[0]
      _setStatus(`Signed in (${email})`, '#10b981')
    } else {
      if (authLabel) authLabel.textContent = 'Sign In'
      _setStatus('Local workspace', 'var(--muted)')
      const btn = document.getElementById('btn-acct-login')
      if (btn) btn.disabled = info.configured === false
      _setText('acct-server-note', info.configured === false
        ? 'No account server is set. Run: mcn config set account_url https://…'
        : (info.account_url ? 'Account server: ' + info.account_url.replace(/^https?:\/\//, '') : ''))
    }
    return
  }

  // Hosted Studio
  _show('auth-device-view', false)
  _setText('auth-modal-title', 'Sign in to MCN Studio')
  if (_authToken && _authUser) {
    _show('auth-profile-view', true); _show('auth-form-view', false)
    if (closeBtn) closeBtn.style.display = ''
    _setText('auth-modal-sub', 'Your workspace on this Studio')
    _setText('profile-display-email', _authUser.email || 'Developer')
    _setText('profile-display-ws', `~/.mcn/workspaces/${_authUser.id || ''}`)
    if (authLabel) authLabel.textContent = (_authUser.email || 'Account').split('@')[0];
    _setStatus(`Workspace (${_authUser.email})`, '#10b981')
  } else {
    _show('auth-profile-view', false); _show('auth-form-view', true, 'flex')
    if (closeBtn) closeBtn.style.display = 'none'
    _setText('auth-modal-sub', 'Sign in or create an account to open your workspace')
    if (authLabel) authLabel.textContent = 'Sign In';
    _setStatus('Not signed in', 'var(--muted)')
  }
}

// ── Installed Studio: browser sign-in ───────────────────────────────────────

function _accountError(msg) {
  const el = document.getElementById('acct-msg')
  if (!el) return
  el.style.display = msg ? 'block' : 'none'
  el.textContent = msg || ''
}

async function refreshAccount(refresh = false) {
  try {
    const res = await fetch('/api/account' + (refresh ? '?refresh=1' : ''))
    if (res.ok) _accountInfo = await res.json()
    if (_accountInfo && _accountInfo.signed_out_remotely && typeof showToast === 'function') {
      showToast('This computer was signed out of your MCN account.', 'info')
    }
  } catch (e) {}
  renderAuthModalState()
}

async function accountStartLogin() {
  _accountError('')
  const btn = document.getElementById('btn-acct-login')
  if (btn) { btn.disabled = true; btn.textContent = 'Starting…' }
  try {
    const res = await fetch('/api/account/login', { method: 'POST' })
    const d = await res.json()
    if (!res.ok) throw new Error(d.error || 'Could not start sign-in')
    const link = d.verification_uri_complete || d.verification_uri
    _setText('acct-user-code', d.user_code)
    const a = document.getElementById('acct-verify-link'); if (a) a.href = link
    window.open(link, '_blank', 'noopener')
    _accountPoll = { device_code: d.device_code, until: Date.now() + (d.expires_in || 600) * 1000 }
    renderAuthModalState()
    _pollAccount(d.device_code, Math.max(2, d.interval || 3) * 1000)
  } catch (e) {
    _accountError(e.message)
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = 'Sign in with your browser' }
  }
}

async function _pollAccount(deviceCode, interval) {
  while (_accountPoll && _accountPoll.device_code === deviceCode) {
    await new Promise(r => setTimeout(r, interval))
    if (!_accountPoll || _accountPoll.device_code !== deviceCode) return
    if (Date.now() > _accountPoll.until) {
      _accountPoll = null; renderAuthModalState(); _accountError('The sign-in code expired. Try again.'); return
    }
    let d = {}
    try {
      const res = await fetch('/api/account/poll', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ device_code: deviceCode }),
      })
      d = await res.json()
    } catch (e) { continue }               // offline for a moment: keep waiting
    if (d.status === 'pending') continue
    _accountPoll = null
    if (d.status === 'approved') {
      _accountInfo = d
      renderAuthModalState()
      if (typeof showToast === 'function') showToast(`Signed in as ${(d.user && d.user.email) || 'your account'}`, 'success')
    } else {
      renderAuthModalState()
      _accountError(d.error || 'Sign-in did not complete.')
    }
    return
  }
}

function accountCancelLogin() {
  _accountPoll = null
  renderAuthModalState()
}

async function accountLogout() {
  try { await fetch('/api/account/logout', { method: 'POST' }) } catch (e) {}
  _accountInfo = Object.assign({}, _accountInfo || {}, { signed_in: false, user: null })
  renderAuthModalState()
  if (typeof showToast === 'function') showToast('Signed out of your MCN account on this computer.', 'info')
}

// ── Hosted Studio: email and password ───────────────────────────────────────

async function _reloadWorkspace() {
  // Each account has its own workspace: show its files, not the previous ones
  if (typeof _models !== 'undefined') {
    for (const model of _models.values()) model.dispose()
    _models.clear(); _tabState.clear(); _openTabs = []; _active = null
    if (typeof renderTabs === 'function') renderTabs()
  }
  if (typeof loadFileTree === 'function') await loadFileTree()
  if (typeof openFile === 'function') await openFile('backend/main.mcn')
  try {
    const info = await (await fetch('/api/workspace/info')).json()
    if (info.path) _setText('status-ws', info.path)
  } catch (e) {}
}

async function submitUserAuth() {
  const email = (document.getElementById('auth-inp-email')?.value || '').trim();
  const password = (document.getElementById('auth-inp-pwd')?.value || '').trim();
  const msgEl = document.getElementById('auth-modal-msg');
  const submitBtn = document.getElementById('btn-auth-submit');
  const showError = (text) => {
    if (!msgEl) return
    msgEl.style.display = 'block'; msgEl.style.background = '#fef2f2'; msgEl.style.color = '#dc2626'
    msgEl.textContent = text
  }

  if (!email || !password) return showError('Please enter both email and password.');

  if (submitBtn) {
    submitBtn.disabled = true;
    submitBtn.textContent = _authMode === 'login' ? 'Signing in…' : 'Creating account…';
  }
  try {
    const res = await fetch(_authMode === 'login' ? '/api/auth/login' : '/api/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    const d = await res.json();
    if (!res.ok || !d.success) throw new Error(d.error || 'Authentication failed');

    _authToken = d.token;
    _authUser = d.user;
    localStorage.setItem('mcn_token', d.token);
    localStorage.setItem('mcn_user', JSON.stringify(d.user));
    _setTokenCookie(d.token)

    renderAuthModalState();
    closeAuthModal();
    await _reloadWorkspace()
    if (typeof showToast === 'function') showToast(`Signed in as ${d.user.email}`, 'success');
  } catch (err) {
    showError(err.message)
  } finally {
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.textContent = _authMode === 'login' ? 'Sign In' : 'Create Account';
    }
  }
}

async function userLogout() {
  _authToken = '';
  _authUser = null;
  localStorage.removeItem('mcn_token');
  localStorage.removeItem('mcn_user');
  _setTokenCookie('')
  renderAuthModalState();
  openAuthModal();          // hosted Studio can't be used signed out
}

document.addEventListener('DOMContentLoaded', async () => {
  const m = document.getElementById('auth-profile-modal');
  if (m) {
    m.addEventListener('click', (e) => {
      if (e.target === m) closeAuthModal();
    });
  }
  try {
    const res = await _nativeFetch('/api/studio/mode')
    if (res.ok) _studioMode = (await res.json()).mode || 'local'
  } catch (e) {}

  if (_studioMode === 'local') {
    // Accounts made on an older local Studio aren't used any more
    localStorage.removeItem('mcn_token'); localStorage.removeItem('mcn_user')
    _authToken = ''; _authUser = null
    _setTokenCookie('')
    renderAuthModalState()
    refreshAccount(false)
    return
  }
  if (_authToken) _setTokenCookie(_authToken)
  renderAuthModalState()
  if (!_authToken) openAuthModal()
});
