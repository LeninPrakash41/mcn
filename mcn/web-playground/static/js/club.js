// ── MCN Developer Club panel ────────────────────────────────────────────────
// Join with your college or company, launch the app in this workspace for review,
// follow reviews and certificates, and (for reviewers) review projects, give awards
// and pick projects for funding, recognition or showcasing.

let _club = { info: null, me: null, view: 'mine', review: null }

function _cEl(html) {
  const t = document.createElement('template')
  t.innerHTML = html.trim()
  return t.content
}
const _cEsc = s => escapeHtml(s == null ? '' : String(s))
const _cDate = t => t ? new Date(t * 1000).toLocaleDateString() : ''
const _STATUS = { in_review: 'In review', approved: 'Approved', changes_requested: 'Changes requested',
  rejected: 'Not approved', withdrawn: 'Withdrawn' }

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

async function refreshClub() {
  const box = document.getElementById('club-body')
  if (!box) return
  box.innerHTML = '<div class="pane-empty">Loading…</div>'
  const info = await _clubApi('/api/club/info')
  _club.info = info.ok ? info.data : null
  if (!info.ok) {
    box.replaceChildren(_cEl(`<div class="pane-empty">${_cEsc(info.data.error || 'The club is unavailable')}
      ${info.status === 409 || info.status === 401 ? '<div style="margin-top:10px"><button class="btn btn-sm" onclick="openAuthModal()">Sign in</button></div>' : ''}</div>`))
    return
  }
  if (!_club.info.signed_in) {
    box.replaceChildren(_cEl(`<div class="pane-empty"><b>MCN Developer Club</b><br>Students and professionals build apps in MCN,
      launch them for review, and get certificates. Approved apps are listed in the
      <a href="${_cEsc(_clubUrl('/club'))}" target="_blank">marketplace</a>.
      <div style="margin-top:12px"><button class="btn btn-primary btn-sm" onclick="openAuthModal()">Sign in to join</button></div></div>`))
    return
  }
  const me = await _clubApi('/api/club/me')
  _club.me = me.ok ? me.data : null
  renderClub()
}

function renderClub() {
  const box = document.getElementById('club-body')
  const reviewer = _club.me && _club.me.is_reviewer
  const tabs = (_club.me && _club.me.member ? [['mine', 'My work'], ['launch', 'Launch for review']] : [['join', 'Join']])
    .concat(reviewer ? [['review', 'Review']] : [])
  const joined = !!(_club.me && _club.me.member)
  if (!joined && !reviewer) _club.view = 'join'
  else if (!joined && _club.view !== 'review' && _club.view !== 'join') _club.view = reviewer ? 'review' : 'join'
  const head = !joined && !reviewer ? '' : `<div class="club-tabs">${tabs.map(([k, l]) =>
    `<button class="ap-mode ${_club.view === k ? 'active' : ''}" onclick="_club.view='${k}'; renderClub()">${l}</button>`).join('')}
    <a class="club-market" href="${_cEsc(_clubUrl('/club'))}" target="_blank">Marketplace ↗</a></div>`
  box.innerHTML = head + '<div id="club-view"></div>'
  const view = !joined && (_club.view === 'mine' || _club.view === 'launch') ? 'join' : _club.view
  ;({ join: _clubJoin, mine: _clubMine, launch: _clubLaunch, review: _clubReview })[view]()
}

// ── Join ──────────────────────────────────────────────────────────────────

function _clubJoin() {
  const m = (_club.me && _club.me.member) || {}
  document.getElementById('club-view').innerHTML = `
    <div class="club-card">
      <div class="club-title">Join the MCN Developer Club</div>
      <div class="pane-sub">Build apps in MCN, launch them for review, and get a certificate. Approved apps go to the
        marketplace, where the best win awards and promising ones are picked for funding, recognition or showcasing.</div>
      <form class="club-form" onsubmit="event.preventDefault(); clubJoin(this)">
        <label>Your name<input name="name" required maxlength="80" value="${_cEsc(m.name)}"></label>
        <label>I am a
          <select name="kind" onchange="this.form.organization.previousSibling.textContent = this.value === 'student' ? 'College or university' : 'Company'">
            <option value="student" ${m.kind !== 'professional' ? 'selected' : ''}>Student</option>
            <option value="professional" ${m.kind === 'professional' ? 'selected' : ''}>Professional</option></select></label>
        <label>${m.kind === 'professional' ? 'Company' : 'College or university'}<input name="organization" required maxlength="120" value="${_cEsc(m.organization)}"></label>
        <label>Course and year, or job title <span class="pane-sub">(optional)</span><input name="title" maxlength="80" value="${_cEsc(m.title)}"></label>
        <label>Country <span class="pane-sub">(optional)</span><input name="country" maxlength="60" value="${_cEsc(m.country)}"></label>
        <div class="club-error" id="club-join-error"></div>
        <button class="btn btn-primary btn-sm">Join the club</button>
      </form>
    </div>`
}

async function clubJoin(form) {
  const body = Object.fromEntries(new FormData(form).entries())
  const res = await _clubApi('/api/club/join', body)
  if (!res.ok) { document.getElementById('club-join-error').textContent = res.data.error; return }
  showToast('Welcome to the MCN Developer Club', 'success')
  _club.view = 'launch'
  await refreshClub()
}

// ── My work ───────────────────────────────────────────────────────────────

function _clubMine() {
  const { member, projects = [], certificates = [] } = _club.me
  document.getElementById('club-view').innerHTML = `
    <div class="club-card club-me">
      <div><div class="club-title">${_cEsc(member.name)}</div>
        <div class="pane-sub">${_cEsc(member.kind === 'student' ? 'Student' : 'Professional')} · ${_cEsc(member.organization)}${member.title ? ' · ' + _cEsc(member.title) : ''}</div></div>
      <button class="btn btn-sm" onclick="_club.view='join'; renderClub()">Edit profile</button>
    </div>
    <div class="pane-label club-label">My projects</div>
    ${projects.length ? projects.map(p => `
      <div class="club-card">
        <div class="club-row"><b>${_cEsc(p.title)}</b><span class="club-status s-${p.status}">${_STATUS[p.status] || p.status}</span></div>
        <div class="pane-sub">Version ${p.version} · sent ${_cDate(p.submitted_at)}${p.awards.length ? ' · 🏆 ' + p.awards.map(a => _cEsc(a.label)).join(', ') : ''}${p.spotlight_label ? ' · ' + _cEsc(p.spotlight_label) : ''}</div>
        ${p.review_notes ? `<div class="club-notes"><b>Reviewer:</b> ${_cEsc(p.review_notes)}</div>` : ''}
        <div class="club-actions">
          ${['changes_requested', 'rejected', 'withdrawn', 'approved'].includes(p.status) ? `<button class="btn btn-sm" onclick="clubResubmit('${p.id}')">Send this workspace as a new version</button>` : ''}
          ${p.status === 'approved' ? `<a class="btn btn-sm" target="_blank" href="${_cEsc(_clubUrl('/club/project/' + p.id))}">View in marketplace</a>` : ''}
          ${['in_review', 'changes_requested', 'approved'].includes(p.status) ? `<button class="btn btn-sm" onclick="clubWithdraw('${p.id}')">Withdraw</button>` : ''}
        </div>
      </div>`).join('') : '<div class="pane-empty">No projects yet. Build an app, then use Launch for review.</div>'}
    <div class="pane-label club-label">My certificates</div>
    ${certificates.length ? certificates.map(c => `
      <a class="club-card club-cert" target="_blank" href="${_cEsc(_clubUrl('/club/certificate/' + c.code))}">
        <span>🎓 ${_cEsc(c.title)}</span><span class="pane-sub">${_cDate(c.issued_at)} · ${_cEsc(c.code)}</span></a>`).join('')
      : '<div class="pane-empty">Your first certificate arrives when you launch a project for review.</div>'}`
}

async function clubResubmit(id) {
  _club.resubmit = _club.me.projects.find(p => p.id === id)
  _club.view = 'launch'
  renderClub()
}

async function clubWithdraw(id) {
  if (!(await showIdeConfirm('Withdraw this project?', 'It leaves the review queue or the marketplace. You can send it again later.', { confirmText: 'Withdraw' }))) return
  const res = await _clubApi(`/api/club/projects/${id}/withdraw`, {})
  if (!res.ok) { showToast(res.data.error, 'error'); return }
  await refreshClub()
}

// ── Launch for review ─────────────────────────────────────────────────────

function _clubLaunch() {
  const p = _club.resubmit || {}
  document.getElementById('club-view').innerHTML = `
    <div class="club-card">
      <div class="club-title">${p.id ? 'Send a new version of ' + _cEsc(p.title) : 'Launch this app for review'}</div>
      <div class="pane-sub">Sends backend/main.mcn and ui/app.mcn from this workspace. It must parse; reviewers also see
        its type check and app map. Approved apps are listed in the marketplace.</div>
      <form class="club-form" onsubmit="event.preventDefault(); clubLaunch(this)">
        <label>Title<input name="title" required maxlength="80" value="${_cEsc(p.title)}"></label>
        <label>One line about it<input name="tagline" maxlength="140" value="${_cEsc(p.tagline)}"></label>
        <label>Category<select name="category">${['AI', 'Business', 'Education', 'Health', 'Finance', 'IoT', 'Social good', 'Tools', 'Other']
          .map(c => `<option ${p.category === c ? 'selected' : ''}>${c}</option>`).join('')}</select></label>
        <label>What it does and who it's for<textarea name="description" rows="5" maxlength="4000">${_cEsc(p.description)}</textarea></label>
        <div class="club-error" id="club-launch-error"></div>
        <div class="club-actions">
          <button class="btn btn-primary btn-sm">${p.id ? 'Send new version' : 'Launch for review'}</button>
          ${p.id ? '<button type="button" class="btn btn-sm" onclick="_club.resubmit=null; renderClub()">Cancel</button>' : ''}
        </div>
      </form>
    </div>`
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
  showToast(`Launched for review: ${c.screens} screens, ${c.endpoints} endpoints, ${c.tests} tests`, 'success')
  _club.view = 'mine'
  await refreshClub()
}

// ── Review (reviewers) ────────────────────────────────────────────────────

async function _clubReview() {
  const view = document.getElementById('club-view')
  const res = await _clubApi('/api/club/review')
  if (!res.ok) { view.innerHTML = `<div class="pane-empty">${_cEsc(res.data.error)}</div>`; return }
  const { queue, stats } = res.data
  const market = (await _clubApi('/api/club/marketplace')).data.projects || []
  const order = _club.info.order || {}
  const pick = g => (order[g] || Object.keys(_club.info[g])).map(k => [k, _club.info[g][k]])
  const awards = Object.fromEntries(pick('awards')), spots = Object.fromEntries(pick('spotlights'))
  const s = stats.projects_by_status
  view.innerHTML = `
    <div class="club-stats">
      ${[['Members', stats.members], ['In review', s.in_review], ['Approved', s.approved], ['Certificates', stats.certificates],
         ['Students', stats.members_by_kind.student], ['Professionals', stats.members_by_kind.professional],
         ['Approved using AI', stats.approved_using_ai]].map(([l, n]) => `<div><b>${n || 0}</b><span>${l}</span></div>`).join('')}
    </div>
    <div class="pane-label club-label">Awards and spotlights</div>
    <div class="club-tally">${Object.entries(awards).map(([k, l]) => `<span>🏆 ${_cEsc(l)} <b>${stats.awards[k] || 0}</b></span>`).join('')}
      ${Object.entries(spots).map(([k, l]) => `<span>${_cEsc(l)} <b>${stats.spotlights[k] || 0}</b></span>`).join('')}</div>
    ${stats.top_organizations.length ? `<div class="pane-label club-label">Top colleges and companies</div>
      <div class="club-tally">${stats.top_organizations.map(o => `<span>${_cEsc(o.organization)} <b>${o.approved}</b></span>`).join('')}</div>` : ''}
    <div class="pane-label club-label">Waiting for review (${queue.length})</div>
    ${queue.length ? queue.map(p => `<div class="club-card club-click" onclick="clubOpenReview('${p.id}')">
        <div class="club-row"><b>${_cEsc(p.title)}</b><span class="pane-sub">v${p.version}</span></div>
        <div class="pane-sub">${_cEsc(p.author)} · ${_cEsc(p.author_org)} · ${p.stats.screens} screens, ${p.stats.endpoints} endpoints, ${p.stats.tests} tests${p.stats.uses_ai ? ', uses AI' : ''}</div></div>`).join('')
      : '<div class="pane-empty">Nothing waiting.</div>'}
    <div id="club-review-detail"></div>
    <div class="pane-label club-label">Marketplace: awards and spotlights</div>
    ${market.length ? market.map(p => `<div class="club-card">
        <div class="club-row"><b>${_cEsc(p.title)}</b><span class="pane-sub">${_cEsc(p.author_org)}</span></div>
        <div class="club-awards">${Object.entries(awards).map(([k, l]) => {
          const has = p.awards.some(a => a.category === k)
          return `<button class="chip-btn ${has ? 'on' : ''}" onclick="clubAward('${p.id}', '${k}', ${has})">🏆 ${_cEsc(l)}</button>`
        }).join('')}</div>
        <label class="club-inline">Spotlight <select onchange="clubSpotlight('${p.id}', this.value)">
          <option value="">None</option>${Object.entries(spots).map(([k, l]) => `<option value="${k}" ${p.spotlight === k ? 'selected' : ''}>${_cEsc(l)}</option>`).join('')}
        </select></label></div>`).join('') : '<div class="pane-empty">No approved projects yet.</div>'}`
}

async function clubOpenReview(id) {
  const res = await _clubApi('/api/club/review/' + id)
  const box = document.getElementById('club-review-detail')
  if (!res.ok) { box.innerHTML = `<div class="pane-empty">${_cEsc(res.data.error)}</div>`; return }
  const p = res.data.project, c = res.data.checks
  const list = (title, items) => items.length ? `<div class="club-notes"><b>${title}</b><ul>${items.slice(0, 8).map(i => `<li>${_cEsc(i)}</li>`).join('')}</ul></div>` : ''
  box.innerHTML = `<div class="club-card club-detail">
    <div class="club-title">${_cEsc(p.title)}</div>
    <div class="pane-sub">${_cEsc(p.tagline || '')}</div>
    <div class="pane-sub">${_cEsc(p.author)} · ${_cEsc(p.author_kind === 'student' ? 'Student' : 'Professional')} · ${_cEsc(p.author_org)} · ${_cEsc(p.category || '')}</div>
    ${p.description ? `<p class="club-desc">${_cEsc(p.description)}</p>` : ''}
    <div class="pane-sub">Checks: ${c.screens} screens, ${c.endpoints} endpoints, ${c.tables} tables, ${c.tests} tests${c.uses_ai ? ', uses AI' : ''}
      ${!c.type_errors.length && !c.issues.length ? ' · no problems found' : ''}</div>
    ${list('Type errors', c.type_errors)}${list('App map problems', c.issues)}
    <details><summary>backend/main.mcn</summary><pre class="club-code">${_cEsc(p.backend || '')}</pre></details>
    <details><summary>ui/app.mcn</summary><pre class="club-code">${_cEsc(p.ui || '')}</pre></details>
    <textarea id="club-review-notes" rows="3" placeholder="Notes for the developer (needed to request changes or reject)"></textarea>
    <div class="club-error" id="club-review-error"></div>
    <div class="club-actions">
      <button class="btn btn-primary btn-sm" onclick="clubDecide('${p.id}', 'approve')">Approve</button>
      <button class="btn btn-sm" onclick="clubDecide('${p.id}', 'changes')">Request changes</button>
      <button class="btn btn-sm" onclick="clubDecide('${p.id}', 'reject')">Reject</button>
    </div></div>`
  box.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

async function clubDecide(id, decision) {
  const notes = document.getElementById('club-review-notes').value
  const res = await _clubApi('/api/club/review/' + id, { decision, notes })
  if (!res.ok) { document.getElementById('club-review-error').textContent = res.data.error; return }
  showToast(decision === 'approve' ? 'Approved: it is in the marketplace and the developer has a certificate' : 'Sent back to the developer', 'success')
  renderClub()
}

async function clubAward(id, category, remove) {
  const note = remove ? '' : await showIdePrompt('Give this award', 'A line on why (shown on the project page):', '', 'Optional')
  if (note === null) return
  const res = await _clubApi(`/api/club/review/${id}/award`, { category, note, remove })
  if (!res.ok) { showToast(res.data.error, 'error'); return }
  renderClub()
}

async function clubSpotlight(id, spotlight) {
  const res = await _clubApi(`/api/club/review/${id}/spotlight`, { spotlight })
  if (!res.ok) showToast(res.data.error, 'error')
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

window.addEventListener('load', () => setTimeout(_clubOpenFromLink, 1500))
