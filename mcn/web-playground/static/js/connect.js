// ── Connect panel: Google Sheets, HubSpot, SQL databases, Slack, WhatsApp ... ──
// Shows each connector, whether it's connected, a form for its settings (saved as
// workspace secrets, which code reads through env), a Test button, and an example
// to insert into the code.

let _connectors = []
let _connectOpen = null

async function refreshConnect() {
  const box = document.getElementById('connect-list')
  if (!box) return
  const d = await (await apiFetch('/api/connectors')).json().catch(() => ({}))
  if (!d.success) { box.innerHTML = '<div class="pane-empty">Couldn\'t load the connectors.</div>'; return }
  _connectors = d.connectors
  box.innerHTML = (d.hosted ? '<div class="cx-note">On hosted Studio, connectors run with sample data here; add their settings to your deployment\'s environment.</div>' : '')
    + _connectors.map(_connectCard).join('')
}

function _connectCard(c) {
  const open = _connectOpen === c.name
  const status = c.connected ? '<span class="cx-pill on">Connected</span>' : '<span class="cx-pill">Sample data</span>'
  return `<div class="cx-card ${open ? 'open' : ''}">
    <button class="cx-head" onclick="toggleConnector('${c.name}')">
      <span class="cx-mono">${escapeHtml(c.title.slice(0, 2))}</span>
      <span class="cx-title"><b>${escapeHtml(c.title)}</b><span>${escapeHtml(c.what)}</span></span>
      ${status}
    </button>
    ${open ? `<div class="cx-body">
      ${c.settings.length ? `<form class="cx-form" onsubmit="event.preventDefault(); saveConnector('${c.name}', this)">
        ${c.settings.map(s => `<label>${escapeHtml(s.label)}
          ${s.key === 'GOOGLE_SERVICE_ACCOUNT'
            ? `<textarea name="${s.key}" rows="3" placeholder="${s.set ? 'Saved. Paste a new one to replace it' : 'Paste the JSON key file contents'}"></textarea>`
            : `<input name="${s.key}" type="${s.secret ? 'password' : 'text'}" autocomplete="off" placeholder="${s.set ? 'Saved. Type to replace' : s.key}">`}</label>`).join('')}
        <div class="cx-actions"><button class="btn btn-primary btn-sm">Save</button>
          ${c.testable ? `<button type="button" class="btn btn-sm" onclick="testConnector('${c.name}')">Test</button>` : ''}
          <span class="cx-result" id="cx-result-${c.name}"></span></div>
      </form>` : '<div class="cx-note">Nothing to set up: it works with files in your workspace.</div>'}
      ${c.install ? `<div class="cx-note">Needs <code>mcn add ${escapeHtml(c.install)}</code> on your computer (it installs the library this connector uses).</div>` : ''}
      <div class="cx-example"><div class="cx-row"><span>Example</span>
        <button class="btn btn-sm" onclick="insertConnectorExample('${c.name}')">Insert into code</button></div>
        <pre>${escapeHtml(c.example)}</pre></div>
      <div class="cx-note">Functions: ${c.functions.map(f => `<code>${escapeHtml(f)}</code>`).join(' ')}</div>
    </div>` : ''}
  </div>`
}

function toggleConnector(name) {
  _connectOpen = _connectOpen === name ? null : name
  document.getElementById('connect-list').innerHTML = _connectors.map(_connectCard).join('')
}

async function saveConnector(name, form) {
  const values = {}
  for (const el of form.querySelectorAll('input, textarea')) if (el.value.trim()) values[el.name] = el.value.trim()
  if (!Object.keys(values).length) { _connectResult(name, 'Type a value to save', false); return }
  const r = await apiFetch(`/api/connectors/${name}/settings`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(values)
  })
  const d = await r.json().catch(() => ({}))
  if (!d.success) { _connectResult(name, d.error || 'Couldn\'t save', false); return }
  showToast(`${d.connector.title} settings saved`, 'success')
  await refreshConnect()
}

async function testConnector(name) {
  _connectResult(name, 'Trying…')
  const d = await (await apiFetch(`/api/connectors/${name}/test`, { method: 'POST' })).json().catch(() => ({}))
  _connectResult(name, d.message || (d.success ? 'It works' : 'It didn\'t work'), d.sample ? undefined : d.success)
}

function _connectResult(name, text, ok) {
  const el = document.getElementById('cx-result-' + name)
  if (el) { el.textContent = text; el.className = 'cx-result' + (ok === true ? ' ok' : ok === false ? ' bad' : '') }
}

function insertConnectorExample(name) {
  const c = _connectors.find(x => x.name === name)
  const ed = window._editor
  if (!c || !ed) return
  const sel = ed.getSelection()
  ed.executeEdits('connect', [{ range: sel, text: c.example + '\n', forceMoveMarkers: true }])
  ed.focus()
  showToast(`Inserted the ${c.title} example`, 'success')
}
