// ── MCN Developer Club: publishing from Studio ──────────────────────────────
// Studio only publishes the app in this workspace. Everything else (your projects,
// certificates, reviewing, seasons and awards) is on the club's site, /club.

let _club = { info: null, me: null, resubmit: null }

const _cEsc = s => escapeHtml(s == null ? '' : String(s))
const _cDate = t => t ? new Date(t * 1000).toLocaleDateString() : ''

async function _clubApi(path, body) {
  const r = await apiFetch(path, body === undefined ? {} : {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body)
  })
  const data = await r.json().catch(() => ({}))
  return { ok: r.ok, status: r.status, data }
}

function _clubUrl(path) {
  const base = (_club.info && _club.info.club_url) || (location.origin + '/club')
  return base.replace(/\/club\/?$/, '') + path
}

// Opens the club's site in a new tab (path like '/club', '/club/me', '/club/review')
function openClubSite(path = '/club') {
  window.open(_clubUrl(path), '_blank', 'noopener')
}

function _clubModal() {
  let m = document.getElementById('club-modal')
  if (!m) {
    m = document.createElement('div')
    m.className = 'modal-overlay hidden'
    m.id = 'club-modal'
    m.innerHTML = `<div class="modal-card club-modal">
      <div class="modal-hdr club-modal-hdr"><div><div class="modal-title">Publish to the Developer Club</div>
        <div class="modal-sub">Launch this app for review. Approved apps are listed in the marketplace.</div></div>
        <a href="#" class="club-site-link" onclick="openClubSite('/club/me'); return false">Open the club ↗</a></div>
      <div class="modal-body club" id="club-body"></div></div>`
    m.addEventListener('click', e => { if (e.target === m) m.classList.add('hidden') })
    document.body.appendChild(m)
  }
  return m
}

function _clubSet(html) { document.getElementById('club-body').innerHTML = html }

// openClub('launch', projectId?): the publish dialog. Other views open the club's site.
async function openClub(view = 'launch', projectId = '') {
  if (view === 'mine') return openClubSite('/club/me')
  if (view === 'review') return openClubSite('/club/review')
  _clubModal().classList.remove('hidden')
  _clubSet('<div class="pane-empty">Loading…</div>')
  const info = await _clubApi('/api/club/info')
  _club.info = info.ok ? info.data : null
  if (!info.ok) {
    _clubSet(`<div class="pane-empty">${_cEsc(info.data.error || 'The club is unavailable')}
      ${info.status === 409 || info.status === 401 ? '<div style="margin-top:10px"><button class="btn btn-sm" onclick="closeModal(\'club-modal\'); openAuthModal()">Sign in</button></div>' : ''}</div>`)
    return
  }
  if (!_club.info.signed_in) {
    _clubSet(`<div class="pane-empty">Sign in with your MCN account to publish this app to the club.
      <div style="margin-top:12px"><button class="btn btn-primary btn-sm" onclick="closeModal('club-modal'); openAuthModal()">Sign in</button></div></div>`)
    return
  }
  const me = await _clubApi('/api/club/me')
  _club.me = me.ok ? me.data : null
  _club.resubmit = projectId && _club.me ? (_club.me.projects || []).find(p => p.id === projectId) || null : null
  if (!(_club.me && _club.me.member)) _clubJoin()
  else _clubLaunch()
}

// ── Join (first time only) ────────────────────────────────────────────────

function _clubJoin() {
  _clubSet(`
    <div class="pane-sub">First, join the club. Students join with their college, professionals with their company.</div>
    <form class="club-form" onsubmit="event.preventDefault(); clubJoin(this)">
      <label>Your name<input name="name" required maxlength="80"></label>
      <div class="club-two">
        <label>I am a<select name="kind" onchange="document.getElementById('club-org-label').textContent = this.value === 'student' ? 'College or university' : 'Company'">
          <option value="student">Student</option><option value="professional">Professional</option></select></label>
        <label><span id="club-org-label">College or university</span><input name="organization" required maxlength="120"></label>
      </div>
      <div class="club-two">
        <label><span>Course and year, or job title <span class="pane-sub">(optional)</span></span><input name="title" maxlength="80"></label>
        <label><span>Country <span class="pane-sub">(optional)</span></span><input name="country" maxlength="60"></label>
      </div>
      <div class="club-error" id="club-join-error"></div>
      <div class="club-actions"><button class="btn btn-primary btn-sm">Join and continue</button></div>
    </form>`)
}

async function clubJoin(form) {
  const res = await _clubApi('/api/club/join', Object.fromEntries(new FormData(form).entries()))
  if (!res.ok) { document.getElementById('club-join-error').textContent = res.data.error; return }
  showToast('Welcome to the MCN Developer Club', 'success')
  const me = await _clubApi('/api/club/me')
  _club.me = me.ok ? me.data : _club.me
  _clubLaunch()
}

// ── Launch for review ─────────────────────────────────────────────────────

function _clubSeasonPicker() {
  const open = (_club.info && _club.info.open_seasons) || []
  if (!open.length) return ''
  return `<label>Season<select name="season_id">${open.map(se => `<option value="${se.id}">${_cEsc(se.name)}${se.theme ? ': ' + _cEsc(se.theme) : ''} (entries close ${_cDate(se.ends_at)})</option>`).join('')}
    <option value="">No season (year-round)</option></select></label>`
}

function _clubLaunch() {
  const p = _club.resubmit || {}
  _clubSet(`
    <div id="club-precheck" class="club-check"><div class="pane-sub">Checking this workspace's app…</div></div>
    <form class="club-form" onsubmit="event.preventDefault(); clubLaunch(this)">
      ${p.id ? `<div class="club-title">New version of ${_cEsc(p.title)}</div>` : ''}
      <div class="club-two">
        <label>Title<input name="title" required maxlength="80" placeholder="e.g. Clinic Booking" value="${_cEsc(p.title)}"></label>
        <label>Category<select name="category">${['AI', 'Business', 'Education', 'Health', 'Finance', 'IoT', 'Social good', 'Tools', 'Other']
          .map(c => `<option ${p.category === c ? 'selected' : ''}>${c}</option>`).join('')}</select></label>
      </div>
      <label>One line about it<input name="tagline" maxlength="140" placeholder="Who it's for and what it does" value="${_cEsc(p.tagline)}"></label>
      ${p.id ? (p.season ? `<div class="pane-sub">Entered in ${_cEsc(p.season.name)}</div>` : '') : _clubSeasonPicker()}
      <label>What it does and who it's for<textarea name="description" rows="4" maxlength="4000" placeholder="The problem, who uses it, and how">${_cEsc(p.description)}</textarea></label>
      <div class="pane-sub">Sends backend/main.mcn and ui/app.mcn from this workspace. The code is checked, never run, on the club's server.</div>
      <div class="club-error" id="club-launch-error"></div>
      <div class="club-actions club-end">
        <button type="button" class="btn btn-sm" onclick="closeModal('club-modal')">Cancel</button>
        <button class="btn btn-primary btn-sm" id="club-launch-btn" disabled>${p.id ? 'Send new version' : 'Launch for review'}</button>
      </div>
    </form>`)
  _clubPrecheck()
}

async function _clubPrecheck() {
  await saveAllTabs()
  const res = await _clubApi('/api/club/precheck', {})
  const box = document.getElementById('club-precheck')
  if (!box) return
  const d = res.data
  if (!d.checks) { box.innerHTML = `<div class="club-item bad">✗ ${_cEsc(d.error || 'Could not check the app')}</div>`; return }
  const c = d.checks
  const item = (ok, text) => `<div class="club-item ${ok === true ? 'ok' : ok === false ? 'bad' : 'tip'}">${ok === true ? '✓' : ok === false ? '✗' : '💡'} ${text}</div>`
  const tips = []
  if (!c.tests) tips.push(item(null, 'Add a <code>test</code> block: reviewers look for tests, and it helps toward Best Technical Implementation'))
  if (!c.uses_ai) tips.push(item(null, 'Apps that use AI (<code>ai()</code>, <code>agent_run()</code>) can win Best AI-Powered Application'))
  if (c.screens < 2) tips.push(item(null, 'More than one screen with navigation makes the app easier to try'))
  box.innerHTML = item(!c.parse_errors.length, c.parse_errors.length ? 'Doesn\'t parse: ' + _cEsc(c.parse_errors[0]) : 'Parses')
    + item(!c.type_errors.length, c.type_errors.length ? `${c.type_errors.length} type error(s): ${_cEsc(c.type_errors[0])}` : 'No type errors')
    + item(!c.issues.length, c.issues.length ? `${c.issues.length} app map problem(s): ${_cEsc(c.issues[0])}` : 'No app map problems')
    + item(true, `${c.screens} screens · ${c.endpoints} endpoints · ${c.tables} tables · ${c.tests} tests${c.uses_ai ? ' · uses AI' : ''}`)
    + tips.join('')
  const btn = document.getElementById('club-launch-btn')
  if (btn) btn.disabled = !d.ready
}

async function clubLaunch(form) {
  await saveAllTabs()
  const body = Object.fromEntries(new FormData(form).entries())
  if (_club.resubmit) body.project_id = _club.resubmit.id
  const res = await _clubApi('/api/club/submit', body)
  if (!res.ok) {
    const checks = res.data.checks
    document.getElementById('club-launch-error').textContent = res.data.error +
      (checks && checks.type_errors && checks.type_errors.length ? ' Type errors: ' + checks.type_errors.slice(0, 2).join('; ') : '')
    return
  }
  _club.resubmit = null
  const c = res.data.checks
  _clubSet(`<div class="club-done">
    <div class="club-done-mark">✓</div>
    <div class="club-title">${_cEsc(body.title)} is in review</div>
    <div class="pane-sub">${c.screens} screens, ${c.endpoints} endpoints, ${c.tests} tests. Your certificate is ready, and Studio will tell you when a reviewer decides.</div>
    <div class="club-actions">
      <button class="btn btn-primary btn-sm" onclick="openClubSite('/club/me')">See it in My club ↗</button>
      <button class="btn btn-sm" onclick="closeModal('club-modal')">Done</button>
    </div></div>`)
}

// ── "Open in Studio" from the marketplace ────────────────────────────────────

async function _clubOpenFromLink() {
  const id = new URLSearchParams(location.search).get('club_open')
  if (!id) return
  history.replaceState(null, '', location.pathname)
  if (!(await showIdeConfirm('Open this marketplace app?', 'Its backend/main.mcn and ui/app.mcn replace the ones in this workspace.', { confirmText: 'Open it' }))) return
  const res = await _clubApi(`/api/club/projects/${encodeURIComponent(id)}/open`, {})
  if (!res.ok) { showToast(res.data.error || 'Could not open it', 'error'); return }
  for (const path of res.data.files) {
    if (_models.has(path)) {
      const file = await apiFetch('/api/workspace/file?path=' + encodeURIComponent(path)).then(r => r.json())
      _models.get(path).setValue(file.content || '')
      if (_tabState.has(path)) _tabState.get(path).dirty = false
    }
  }
  await loadFileTree()
  showToast(`Opened ${res.data.title}`, 'success')
}

// A toast when a review decision comes in
async function _clubNotify() {
  const res = await _clubApi('/api/club/me')
  if (!res.ok || !res.data.projects) return
  let seen = {}
  try { seen = JSON.parse(localStorage.getItem('mcn_club_seen') || '{}') } catch {}
  const words = { approved: 'was approved and is in the marketplace', changes_requested: 'needs changes', rejected: 'was not approved' }
  for (const p of res.data.projects) {
    if (seen[p.id] && seen[p.id] !== p.status && words[p.status]) {
      showToast(`${p.title} ${words[p.status]}. See My club on the club's site.`, p.status === 'approved' ? 'success' : 'warning', 6000)
    }
    seen[p.id] = p.status
  }
  try { localStorage.setItem('mcn_club_seen', JSON.stringify(seen)) } catch {}
}

// Links from the club's site: /?club=launch[&project=<id>], /?signin=club
function _clubFromLink() {
  const params = new URLSearchParams(location.search)
  const view = params.get('club'), project = params.get('project') || ''
  const signin = params.get('signin')
  if (!view && !signin) return
  history.replaceState(null, '', location.pathname)
  if (signin) { if (typeof openAuthModal === 'function') openAuthModal(); return }
  openClub(view, project)
}

window.addEventListener('load', () => setTimeout(() => { _clubOpenFromLink(); _clubFromLink(); _clubNotify() }, 1500))
