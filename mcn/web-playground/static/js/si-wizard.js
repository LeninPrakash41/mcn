// ── SI Wizard ──────────────────────────────────────────────────────────────────────────────────────
let _siStep    = 1
let _siTrigger = ''
let _siSources = []
let _siActions = []

const _SI_SOURCE_TYPES = [
  { value: 'api',      label: 'REST API' },
  { value: 'database', label: 'Database query' },
  { value: 'file',     label: 'Read file' },
  { value: 'ai',       label: 'AI / LLM call' },
  { value: 'mcp',      label: 'MCP tool' },
]
const _SI_ACTION_TYPES = [
  { value: 'save_db',    label: 'Save to database' },
  { value: 'call_api',   label: 'Call an API' },
  { value: 'notify',     label: 'Send notification' },
  { value: 'slack',      label: 'Post to Slack' },
  { value: 'email',      label: 'Send email' },
  { value: 'ai',         label: 'AI processing' },
  { value: 'write_file', label: 'Write to file' },
]

function openSIModal() {
  _siStep = 1; _siTrigger = ''; _siSources = []; _siActions = []
  document.getElementById('si-modal').classList.remove('hidden')
  siRenderStep()
  siRenderSources()
  siRenderActions()
  document.getElementById('si-process-desc').value = ''
  document.getElementById('si-trigger-detail').style.display = 'none'
  document.querySelectorAll('.si-trigger-card').forEach(c => c.classList.remove('selected'))
  document.getElementById('si-gen-status').classList.add('hidden')
  document.getElementById('si-gen-stream').classList.add('hidden')
  document.getElementById('si-gen-stream').textContent = ''
  const successCard = document.getElementById('si-success-card')
  if (successCard) successCard.classList.add('hidden')
  document.getElementById('si-error').style.display = 'none'
  document.getElementById('si-error').textContent = ''
}

function closeSIModal() {
  document.getElementById('si-modal').classList.add('hidden')
  document.getElementById('si-gen-status').classList.add('hidden')
  document.getElementById('si-gen-stream').classList.add('hidden')
  const successCard = document.getElementById('si-success-card')
  if (successCard) successCard.classList.add('hidden')
}

function siSelectTrigger(card) {
  document.querySelectorAll('.si-trigger-card').forEach(c => c.classList.remove('selected'))
  card.classList.add('selected')
  _siTrigger = card.dataset.trigger
  const detail = document.getElementById('si-trigger-detail')
  const label  = document.getElementById('si-trigger-detail-label')
  const input  = document.getElementById('si-trigger-detail-input')
  const configs = {
    webhook:  { label: 'Endpoint path',      placeholder: '/api/order-placed' },
    schedule: { label: 'Run every',          placeholder: 'e.g. 1h, 30m, daily at 9am' },
    manual:   { label: 'Button label',       placeholder: 'e.g. Sync Now' },
    event:    { label: 'Event / queue name', placeholder: 'e.g. order.created' },
  }
  const cfg = configs[_siTrigger]
  if (cfg) { label.textContent = cfg.label; input.placeholder = cfg.placeholder; detail.style.display = '' }
}

function siRenderSources() {
  const ct = document.getElementById('si-sources-list')
  ct.innerHTML = ''
  _siSources.forEach((src, i) => {
    const row = document.createElement('div')
    row.className = 'si-row'
    row.style.marginBottom = '8px'
    row.innerHTML = `
      <select class="form-input" style="flex:0 0 140px" onchange="_siSources[${i}].type=this.value">
        ${_SI_SOURCE_TYPES.map(t => `<option value="${t.value}" ${src.type===t.value?'selected':''}>${t.label}</option>`).join('')}
      </select>
      <input class="form-input" placeholder="URL, table name, prompt, or tool name"
        value="${src.value}" oninput="_siSources[${i}].value=this.value" />
      <button class="si-remove-btn" onclick="siRemoveSource(${i})">&#x2715;</button>`
    ct.appendChild(row)
  })
}

function siAddSource()    { _siSources.push({ type: 'api', value: '' }); siRenderSources() }
function siAddQuickSource(type, val) { _siSources.push({ type, value: val }); siRenderSources() }
function siRemoveSource(i){ _siSources.splice(i, 1); siRenderSources() }

function siRenderActions() {
  const ct = document.getElementById('si-actions-list')
  ct.innerHTML = ''
  _siActions.forEach((act, i) => {
    const row = document.createElement('div')
    row.className = 'si-row'
    row.style.marginBottom = '8px'
    row.innerHTML = `
      <select class="form-input" style="flex:0 0 160px" onchange="_siActions[${i}].type=this.value">
        ${_SI_ACTION_TYPES.map(t => `<option value="${t.value}" ${act.type===t.value?'selected':''}>${t.label}</option>`).join('')}
      </select>
      <input class="form-input" placeholder="Destination, message, or details"
        value="${act.value}" oninput="_siActions[${i}].value=this.value" />
      <button class="si-remove-btn" onclick="siRemoveAction(${i})">&#x2715;</button>`
    ct.appendChild(row)
  })
}

function siAddAction()    { _siActions.push({ type: 'save_db', value: '' }); siRenderActions() }
function siAddQuickAction(type, val) { _siActions.push({ type, value: val }); siRenderActions() }
function siRemoveAction(i){ _siActions.splice(i, 1); siRenderActions() }

function siRenderStep() {
  for (let n = 1; n <= 3; n++) {
    const tab  = document.getElementById(`si-tab-${n}`)
    const page = document.getElementById(`si-page-${n}`)
    tab.classList.toggle('active', n === _siStep)
    tab.classList.toggle('done',   n < _siStep)
    page.classList.toggle('active', n === _siStep)
  }
  document.getElementById('si-btn-back').style.display = _siStep > 1 ? '' : 'none'
  const nextBtn = document.getElementById('si-btn-next')
  nextBtn.textContent = _siStep === 3 ? 'Generate MCN' : 'Next →'
  nextBtn.className   = _siStep === 3 ? 'btn btn-gradient' : 'btn btn-si'
}

function siBack() { if (_siStep > 1) { _siStep--; siRenderStep() } }

async function siNext() {
  if (_siStep === 1) {
    if (!_siTrigger) {
      await showIdeAlert('Trigger Required', 'Please select a trigger for your system integration process.', 'warn');
      return;
    }
    if (!document.getElementById('si-process-desc').value.trim()) {
      await showIdeAlert('Description Required', 'Please describe what this process does.', 'warn');
      return;
    }
    _siStep = 2; siRenderStep(); return;
  }
  if (_siStep === 2) {
    _siStep = 3; siRenderStep();
    if (_siActions.length === 0) siAddAction();
    return;
  }
  await siGenerate();
}

function siBuildPrompt() {
  const desc   = document.getElementById('si-process-desc').value.trim()
  const detail = document.getElementById('si-trigger-detail-input').value.trim()
  const triggerLabels = { webhook: 'Webhook', schedule: 'Schedule', manual: 'Manual button', event: 'Event/queue', cdc: 'Database CDC', file: 'File Ingestion' }
  const triggerStr  = (triggerLabels[_siTrigger] || _siTrigger) + (detail ? ` (${detail})` : '')
  const sourcesStr  = _siSources.length
    ? _siSources.map(s => `- ${s.type}: ${s.value || '(unspecified)'}`).join('\n')
    : '- No external data sources'
  const actionsStr  = _siActions.length
    ? _siActions.map(a => `- ${a.type}: ${a.value || '(unspecified)'}`).join('\n')
    : '- No specific actions'
  return `Build a complete MCN application for the following integration process.

Process description: ${desc}
Trigger: ${triggerStr}

Data sources / tools needed:
${sourcesStr}

Actions to perform:
${actionsStr}

IMPORTANT: You MUST output exactly two XML blocks:
<backend>...backend/main.mcn content here...</backend>
<ui>...ui/app.mcn content here...</ui>

Requirements:
- backend/main.mcn: use agent and service blocks for the integration logic
- ui/app.mcn: simple UI to trigger and monitor the process with status display
- Keep code minimal and readable for a non-developer
- Use descriptive variable names matching the business domain
- Add brief inline comments explaining each step in plain English`
}

async function siGenerate() {
  const apiKey = document.getElementById('si-api-key').value.trim()
  const prompt = siBuildPrompt()
  const errEl  = document.getElementById('si-error')
  errEl.style.display = 'none'
  document.getElementById('si-btn-next').disabled = true
  const successCard = document.getElementById('si-success-card')
  if (successCard) successCard.classList.add('hidden')
  document.getElementById('si-gen-status').classList.remove('hidden')
  document.getElementById('si-gen-stream').classList.remove('hidden')
  document.getElementById('si-gen-stream').textContent = ''
  document.getElementById('si-gen-status-text').textContent = 'Generating your MCN integration…'
  try {
    const r = await apiFetch('/api/generate', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ description: prompt, api_key: apiKey })
    })
    if (!r.ok) {
      const e = await r.json()
      errEl.textContent = e.error || 'Generation failed'
      errEl.style.display = ''
      document.getElementById('si-gen-status').classList.add('hidden')
      document.getElementById('si-gen-stream').classList.add('hidden')
      document.getElementById('si-btn-next').disabled = false
      return
    }
    const reader = r.body.getReader()
    const decoder = new TextDecoder()
    let buf = ''
    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      buf += decoder.decode(value, { stream: true })
      const parts = buf.split('\n\n'); buf = parts.pop()
      for (const part of parts) {
        if (!part.startsWith('data:')) continue
        const ev = JSON.parse(part.slice(5).trim())
        if (ev.type === 'token') {
          const s = document.getElementById('si-gen-stream')
          s.textContent += ev.text; s.scrollTop = s.scrollHeight
        } else if (ev.type === 'status') {
          document.getElementById('si-gen-status-text').textContent = ev.text
        } else if (ev.type === 'done') {
          document.getElementById('si-gen-status').classList.add('hidden')
          const writes = []
          if (ev.backend) writes.push(apiFetch('/api/workspace/file', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ path: 'backend/main.mcn', content: ev.backend }) }))
          if (ev.ui)      writes.push(apiFetch('/api/workspace/file', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ path: 'ui/app.mcn',       content: ev.ui      }) }))
          await Promise.all(writes)
          if (ev.backend && _models.has('backend/main.mcn')) { _models.get('backend/main.mcn').setValue(ev.backend); if (_tabState.has('backend/main.mcn')) _tabState.get('backend/main.mcn').dirty = false }
          if (ev.ui      && _models.has('ui/app.mcn'))       { _models.get('ui/app.mcn').setValue(ev.ui);           if (_tabState.has('ui/app.mcn'))       _tabState.get('ui/app.mcn').dirty       = false }
          await loadFileTree()
          showToast('MCN Integration process wired and generated!', 'success')
          if (successCard) successCard.classList.remove('hidden')
        } else if (ev.type === 'error') {
          errEl.textContent = ev.message || 'Generation error'
          errEl.style.display = ''
          document.getElementById('si-gen-status').classList.add('hidden')
        }
      }
    }
  } catch (e) {
    errEl.textContent = e.message
    errEl.style.display = ''
    document.getElementById('si-gen-status').classList.add('hidden')
  }
  finally { document.getElementById('si-btn-next').disabled = false }
}

document.getElementById('si-modal').addEventListener('click', function(e) {
  if (e.target === this) closeSIModal()
})
