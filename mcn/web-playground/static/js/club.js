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

function openClub(view) {
  const panel = document.querySelector('.preview-panel')
  if (panel && panel.classList.contains('collapsed')) toggleRightPanel()
  if (view) _club.view = view
  switchPanel('club')
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
    ${_clubSteps(0)}
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
    ${projects.length ? '' : _clubSteps(1)}
    <div class="pane-label club-label">My projects</div>
    ${projects.length ? projects.map(p => `
      <div class="club-card">
        <div class="club-row"><b>${_cEsc(p.title)}</b><span class="club-status s-${p.status}">${_STATUS[p.status] || p.status}</span></div>
        ${p.season ? `<div class="pane-sub">🏁 ${_cEsc(p.season.name)} · ${_cEsc(p.season.status_label)}</div>` : ''}
        ${_clubScoreLine(p.scores)}
        ${p.status === 'approved' ? `<div class="club-usage"><span><b>${p.usage.uses}</b> members using it</span><span><b>${p.usage.likes}</b> likes</span><span><b>${p.usage.views}</b> views</span></div>` : ''}
        <div class="pane-sub">Version ${p.version} · sent ${_cDate(p.submitted_at)}${p.awards.length ? ' · 🏆 ' + p.awards.map(a => _cEsc(a.label)).join(', ') : ''}${p.spotlight_label ? ' · ' + _cEsc(p.spotlight_label) : ''}</div>
        ${p.review_notes ? `<div class="club-notes"><b>Reviewer:</b> ${_cEsc(p.review_notes)}</div>` : ''}
        <div class="club-actions">
          ${['changes_requested', 'rejected', 'withdrawn', 'approved'].includes(p.status) ? `<button class="btn btn-sm" onclick="clubResubmit('${p.id}')">Send this workspace as a new version</button>` : ''}
          ${p.status === 'approved' ? `<a class="btn btn-sm" target="_blank" href="${_cEsc(_clubUrl('/club/project/' + p.id))}">View in marketplace</a>` : ''}
          ${['in_review', 'changes_requested', 'approved'].includes(p.status) ? `<button class="btn btn-sm" onclick="clubWithdraw('${p.id}')">Withdraw</button>` : ''}
        </div>
      </div>`).join('') : '<div class="pane-empty">No projects yet. Build an app (a template or the Agent is a quick start), then <a href="#" onclick="openClub(\'launch\'); return false">launch it for review</a>.</div>'}
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

function _clubSeasonPicker() {
  const open = (_club.info && _club.info.open_seasons) || []
  if (!open.length) return ''
  return `<label>Season<select name="season_id">${open.map(se => `<option value="${se.id}">${_cEsc(se.name)}${se.theme ? ': ' + _cEsc(se.theme) : ''} (entries close ${_cDate(se.ends_at)})</option>`).join('')}
    <option value="">No season (year-round)</option></select></label>`
}

const _cScore = v => v == null ? '–' : (Math.round(v * 10) / 10).toString()
// The rubric in its intended order (server JSON comes back with sorted keys)
const _rubric = () => ((_club.info.order || {}).rubric || Object.keys(_club.info.rubric || {})).map(k => [k, _club.info.rubric[k]])

function _clubScoreLine(scores) {
  if (!scores || !scores.reviewers) return ''
  if (!_club.info || !_club.info.rubric) return ''
  return `<div class="club-scores">${_rubric().map(([k, l]) => `<span>${_cEsc(l)} <b>${_cScore(scores.averages[k])}</b></span>`).join('')}
    <span>Overall <b>${_cScore(scores.total)}</b>/5 from ${scores.reviewers} reviewer${scores.reviewers === 1 ? '' : 's'}</span></div>`
}

function _clubSteps(active) {
  const steps = ['Join', 'Build', 'Launch for review', 'Listed and certified']
  return `<ol class="club-steps">${steps.map((t, i) => `<li class="${i < active ? 'done' : i === active ? 'now' : ''}"><i>${i < active ? '✓' : i + 1}</i>${t}</li>`).join('')}</ol>`
}

function _clubLaunch() {
  const p = _club.resubmit || {}
  document.getElementById('club-view').innerHTML = `
    ${_clubSteps(2)}
    <div class="club-card">
      <div class="club-title">Before you launch</div>
      <div id="club-precheck" class="club-check"><div class="pane-sub">Checking this workspace's app…</div></div>
    </div>
    <div class="club-card">
      <div class="club-title">${p.id ? 'Send a new version of ' + _cEsc(p.title) : 'Launch this app for review'}</div>
      <div class="pane-sub">Sends backend/main.mcn and ui/app.mcn from this workspace. You get a certificate when you launch,
        another when it's approved, and it's listed in the marketplace.</div>
      <form class="club-form" onsubmit="event.preventDefault(); clubLaunch(this)">
        <label>Title<input name="title" required maxlength="80" placeholder="e.g. Clinic Booking" value="${_cEsc(p.title)}"></label>
        <label>One line about it<input name="tagline" maxlength="140" placeholder="Who it's for and what it does" value="${_cEsc(p.tagline)}"></label>
        <label>Category<select name="category">${['AI', 'Business', 'Education', 'Health', 'Finance', 'IoT', 'Social good', 'Tools', 'Other']
          .map(c => `<option ${p.category === c ? 'selected' : ''}>${c}</option>`).join('')}</select></label>
        ${p.id ? (p.season ? `<div class="pane-sub">Entered in ${_cEsc(p.season.name)}</div>` : '') : _clubSeasonPicker()}
        <label>What it does and who it's for<textarea name="description" rows="5" maxlength="4000" placeholder="The problem, who uses it, and how">${_cEsc(p.description)}</textarea></label>
        <div class="club-error" id="club-launch-error"></div>
        <div class="club-actions">
          <button class="btn btn-primary btn-sm" id="club-launch-btn">${p.id ? 'Send new version' : 'Launch for review'}</button>
          ${p.id ? '<button type="button" class="btn btn-sm" onclick="_club.resubmit=null; renderClub()">Cancel</button>' : ''}
        </div>
      </form>
    </div>`
  _clubPrecheck()
}

async function _clubPrecheck() {
  await saveAllTabs()
  const box = document.getElementById('club-precheck')
  const res = await _clubApi('/api/club/precheck', {})
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
    <div class="pane-label club-label">Seasons</div>
    <div id="club-seasons"></div>
    <div id="club-standings"></div>
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
        <div class="club-actions"><button class="btn btn-sm" onclick="clubOpenReview('${p.id}')">Score</button></div>
        <label class="club-inline">Spotlight <select onchange="clubSpotlight('${p.id}', this.value)">
          <option value="">None</option>${Object.entries(spots).map(([k, l]) => `<option value="${k}" ${p.spotlight === k ? 'selected' : ''}>${_cEsc(l)}</option>`).join('')}
        </select></label></div>`).join('') : '<div class="pane-empty">No approved projects yet.</div>'}`
  _clubSeasons()
}

async function _clubSeasons() {
  const box = document.getElementById('club-seasons')
  if (!box) return
  const list = (await _clubApi('/api/club/seasons')).data.seasons || []
  const admin = _club.info.is_admin
  box.innerHTML = (list.length ? list.map(se => `<div class="club-card">
      <div class="club-row"><b>🏁 ${_cEsc(se.name)}</b><span class="club-status s-${se.status === 'open' ? 'approved' : se.status === 'judging' ? 'in_review' : ''}">${_cEsc(se.status_label)}</span></div>
      <div class="pane-sub">${se.theme ? _cEsc(se.theme) + ' · ' : ''}${_cDate(se.starts_at)} to ${_cDate(se.ends_at)} · ${se.entries} entries, ${se.approved} approved</div>
      <div class="club-actions"><button class="btn btn-sm" onclick="clubStandings('${se.id}')">Standings and suggestions</button>
        ${admin ? `<button class="btn btn-sm" onclick="clubPublishResults('${se.id}', ${se.status !== 'closed'})">${se.status === 'closed' ? 'Hide results' : 'Publish results'}</button>` : ''}</div>
    </div>`).join('') : '<div class="pane-empty">No seasons yet.</div>')
    + (admin ? `<details class="club-card"><summary><b>New season</b></summary>
      <form class="club-form" onsubmit="event.preventDefault(); clubCreateSeason(this)">
        <label>Name<input name="name" required maxlength="60" placeholder="e.g. Spring 2027"></label>
        <label>Theme <span class="pane-sub">(optional)</span><input name="theme" maxlength="120" placeholder="e.g. AI for healthcare"></label>
        <label>Opens<input name="starts" type="date" required></label>
        <label>Entries close<input name="ends" type="date" required></label>
        <label>About it <span class="pane-sub">(optional)</span><textarea name="description" rows="3" maxlength="2000"></textarea></label>
        <button class="btn btn-primary btn-sm">Create season</button></form></details>` : '')
}

async function clubCreateSeason(form) {
  const f = Object.fromEntries(new FormData(form).entries())
  const res = await _clubApi('/api/club/seasons', { name: f.name, theme: f.theme, description: f.description,
    starts_at: new Date(f.starts + 'T00:00:00').getTime() / 1000, ends_at: new Date(f.ends + 'T23:59:59').getTime() / 1000 })
  if (!res.ok) { showToast(res.data.error, 'error'); return }
  showToast(`${res.data.season.name} created`, 'success')
  await refreshClub()
}

async function clubPublishResults(id, publish) {
  if (publish && !(await showIdeConfirm('Publish the results?', 'The season closes and its winners appear on its public page.', { confirmText: 'Publish results' }))) return
  const res = await _clubApi('/api/club/seasons/' + id, { results_published: publish })
  if (!res.ok) { showToast(res.data.error, 'error'); return }
  _clubSeasons()
}

async function clubStandings(id) {
  const box = document.getElementById('club-standings')
  const res = await _clubApi(`/api/club/seasons/${id}/standings`)
  if (!res.ok) { box.innerHTML = `<div class="pane-empty">${_cEsc(res.data.error)}</div>`; return }
  const d = res.data, r = _club.info.rubric, awards = _club.info.awards
  box.innerHTML = `<div class="club-card club-detail">
    <div class="club-row"><b>Standings: ${_cEsc(d.season.name)}</b><button class="btn btn-sm" onclick="document.getElementById('club-standings').innerHTML=''">Close</button></div>
    ${d.ranked.length ? `<div class="club-table"><table><thead><tr><th>#</th><th>App</th>${_rubric().map(([k, l]) => `<th title="${_cEsc(l)}">${_cEsc((_club.info.rubric_short || {})[k] || l)}</th>`).join('')}<th>Avg</th><th>Using</th></tr></thead>
      <tbody>${d.ranked.map((p, i) => `<tr><td>${i + 1}</td><td><a href="#" onclick="clubOpenReview('${p.id}'); return false">${_cEsc(p.title)}</a><div class="pane-sub">${_cEsc(p.author_org)} · ${p.scores.reviewers} reviewer(s)</div></td>
        ${_rubric().map(([k]) => `<td>${_cScore(p.scores.averages[k])}</td>`).join('')}<td><b>${_cScore(p.scores.total)}</b></td><td>${p.usage.uses}</td></tr>`).join('')}</tbody></table></div>`
      : '<div class="pane-empty">No approved entries in this season yet.</div>'}
    <div class="pane-label club-label">Suggested winners</div>
    ${Object.entries(d.suggestions).map(([award, sug]) => {
      const entry = d.ranked.find(p => p.id === sug.project_id)
      const has = entry && entry.awards.some(a => a.category === award)
      return `<div class="club-row club-sug"><span>🏆 ${_cEsc(awards[award])}: <b>${_cEsc(sug.title)}</b> <span class="pane-sub">(${_cScore(sug.score)}/5)</span></span>
        ${has ? '<span class="club-status s-approved">Awarded</span>' : `<button class="btn btn-sm" onclick="clubAward('${sug.project_id}', '${award}', false)">Give award</button>`}</div>`
    }).join('') || '<div class="pane-sub">Score the entries to see suggestions.</div>'}
    ${d.peoples_choice ? `<div class="club-row club-sug"><span>❤ People's Choice (most used): <b>${_cEsc(d.peoples_choice.title)}</b> <span class="pane-sub">(${d.peoples_choice.uses} members)</span></span>
      <button class="btn btn-sm" onclick="clubSpotlight('${d.peoples_choice.project_id}', 'recognition').then(() => showToast('Spotlighted for recognition', 'success'))">Spotlight it</button></div>` : ''}
  </div>`
  box.scrollIntoView({ behavior: 'smooth', block: 'start' })
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
    ${_clubRubricForm(p, res.data.mine)}
    <textarea id="club-review-notes" rows="3" placeholder="Notes for the developer (needed to request changes or reject)"></textarea>
    <div class="club-error" id="club-review-error"></div>
    <div class="club-actions">
      <button class="btn btn-primary btn-sm" onclick="clubDecide('${p.id}', 'approve')">Approve</button>
      <button class="btn btn-sm" onclick="clubDecide('${p.id}', 'changes')">Request changes</button>
      <button class="btn btn-sm" onclick="clubDecide('${p.id}', 'reject')">Reject</button>
    </div></div>`
  box.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function _clubRubricForm(p, mine) {
  const r = _club.info.rubric, help = _club.info.rubric_help, have = (mine && mine.scores) || {}
  return `<div class="club-rubric" id="club-rubric">
    <div class="club-row"><b>Score it</b>${p.season ? `<span class="pane-sub">🏁 ${_cEsc(p.season.name)}</span>` : ''}</div>
    ${_rubric().map(([k, label]) => `<div class="club-crit">
      <div><div>${_cEsc(label)}</div><div class="pane-sub">${_cEsc(help[k])}</div></div>
      <div class="club-dots" role="radiogroup" aria-label="${_cEsc(label)}">
        ${[1, 2, 3, 4, 5].map(n => `<label><input type="radio" name="crit-${k}" value="${n}" ${have[k] === n ? 'checked' : ''}><span>${n}</span></label>`).join('')}
        ${k === 'ai' ? `<label><input type="radio" name="crit-${k}" value="na" ${k in have && have[k] == null ? 'checked' : ''}><span>N/A</span></label>` : ''}
      </div></div>`).join('')}
    <input id="club-score-note" placeholder="A note for other reviewers (optional)" value="${_cEsc((mine && mine.note) || '')}">
    <div class="club-actions"><button class="btn btn-sm" onclick="clubScore('${p.id}')">Save scores</button>
      <span class="pane-sub" id="club-score-summary">${p.scores && p.scores.reviewers ? `Average ${_cScore(p.scores.total)}/5 from ${p.scores.reviewers} reviewer(s)` : 'Not scored yet'}</span></div>
  </div>`
}

async function clubScore(id) {
  const scores = {}
  for (const [k] of _rubric()) {
    const picked = document.querySelector(`input[name="crit-${k}"]:checked`)
    scores[k] = picked ? picked.value : null
  }
  const res = await _clubApi(`/api/club/review/${id}/score`, { scores, note: document.getElementById('club-score-note').value })
  if (!res.ok) { showToast(res.data.error, 'error'); return }
  const sc = res.data.project.scores
  document.getElementById('club-score-summary').textContent = `Average ${_cScore(sc.total)}/5 from ${sc.reviewers} reviewer(s)`
  showToast('Scores saved', 'success')
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

// A dot on the Club tab, and a toast, when a review decision comes in
async function _clubNotify() {
  const res = await _clubApi('/api/club/me')
  if (!res.ok || !res.data.projects) return
  let seen = {}
  try { seen = JSON.parse(localStorage.getItem('mcn_club_seen') || '{}') } catch {}
  const words = { approved: 'was approved and is in the marketplace', changes_requested: 'needs changes', rejected: 'was not approved' }
  let changed = false
  for (const p of res.data.projects) {
    if (seen[p.id] && seen[p.id] !== p.status && words[p.status]) {
      showToast(`${p.title} ${words[p.status]}`, p.status === 'approved' ? 'success' : 'warning', 6000)
      changed = true
    }
    seen[p.id] = p.status
  }
  try { localStorage.setItem('mcn_club_seen', JSON.stringify(seen)) } catch {}
  if (changed) document.getElementById('tab-club')?.classList.add('has-news')
}

function _clubFromLink() {
  const params = new URLSearchParams(location.search)
  if (params.get('club')) {
    const view = params.get('club')
    history.replaceState(null, '', location.pathname)
    openClub(['launch', 'mine', 'review', 'join'].includes(view) ? view : 'mine')
  }
}

window.addEventListener('load', () => setTimeout(() => { _clubOpenFromLink(); _clubFromLink(); _clubNotify() }, 1500))
document.addEventListener('click', e => { if (e.target.id === 'tab-club') e.target.classList.remove('has-news') })
