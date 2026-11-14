// ── Agent panel ─────────────────────────────────────────────────────────────
// A chat beside the editor, like Cursor's and Claude's:
//   Change   the agent edits the app through the agent interface and returns a patch to review
//   Ask      the agent answers questions using only the read-only operations
//   New app  the agent team plans, builds and tests a whole app
// Cmd/Ctrl+L opens it. An API key typed here is kept in memory only; any model with tool calling works.

const AP_MODES = {
  change: {
    placeholder: 'Describe a change to your app…',
    hint: 'Changes come back as a patch you review before anything is written',
    suggestions: [
      'Add a search box to the main table',
      'Check the customer exists before creating an order',
      'Add a test for every endpoint that has none',
    ],
  },
  ask: {
    placeholder: 'Ask about your app…',
    hint: 'Answers come from your code; nothing is changed',
    suggestions: [
      'What happens when someone creates an order?',
      'Which endpoints have no tests?',
      'Which screens use the customers table?',
    ],
  },
  build: {
    placeholder: 'Describe the app to build…',
    hint: 'The agent team plans, builds and tests a new app in this workspace',
    suggestions: [
      'An HR portal with leave approvals and an audit trail',
      'A clinic booking app with reminders',
      'An inventory tracker with low-stock alerts',
    ],
  },
}

let _apMode = 'change'
let _apBusy = false
let _apKey = ''
let _apFiles = []            // attachments for New app: {name, type, size, data}

function addAgentFiles(list) {
  for (const file of list || []) {
    if (_apFiles.length >= 6) { showToast('You can attach up to 6 files', 'warn'); break }
    if (file.size > 15 * 1024 * 1024) { showToast(`${file.name} is over 15 MB`, 'warn'); continue }
    const reader = new FileReader()
    reader.onload = e => {
      _apFiles.push({ name: file.name, type: file.type || 'text/plain', size: file.size, data: e.target.result })
      _apRenderFiles()
    }
    reader.readAsDataURL(file)
  }
  document.getElementById('ap-file').value = ''
}

function _apRenderFiles() {
  const box = document.getElementById('ap-files')
  box.replaceChildren(..._apFiles.map((f, i) => {
    const chip = _el('span', 'ap-file', f.name)
    const x = _el('button', 'ap-file-x', '×')
    x.title = 'Remove'
    x.onclick = () => { _apFiles.splice(i, 1); _apRenderFiles() }
    chip.appendChild(x)
    return chip
  }))
}

function openAgentPanel(mode) {
  const panel = document.querySelector('.preview-panel')
  if (panel && panel.classList.contains('collapsed')) toggleRightPanel()
  switchPanel('agent')
  if (mode) setAgentMode(mode)
  setTimeout(() => document.getElementById('ap-input')?.focus(), 30)
}

function setAgentMode(mode) {
  _apMode = mode
  document.querySelectorAll('.ap-mode').forEach(b => b.classList.toggle('active', b.dataset.mode === mode))
  const cfg = AP_MODES[mode]
  document.getElementById('ap-input').placeholder = cfg.placeholder
  document.getElementById('ap-hint').textContent = cfg.hint
  document.getElementById('ap-attach').classList.toggle('hidden', mode !== 'build')
  if (mode !== 'build') { _apFiles = []; _apRenderFiles() }
  if (!document.querySelector('#ap-thread .ap-msg')) renderAgentWelcome()
}

function agentNewChat() {
  if (_apBusy) return
  renderAgentWelcome()
  document.getElementById('ap-input').focus()
}

function renderAgentWelcome() {
  const thread = document.getElementById('ap-thread')
  thread.replaceChildren()
  const box = _el('div', 'ap-welcome')
  box.appendChild(_el('div', 'ap-welcome-title', {
    change: 'What should change?', ask: 'Ask about this app', build: 'What should the team build?',
  }[_apMode]))
  box.appendChild(_el('div', 'ap-welcome-sub', AP_MODES[_apMode].hint + '.'))
  const list = _el('div', 'ap-suggestions')
  AP_MODES[_apMode].suggestions.forEach(text => {
    const b = _el('button', 'ap-suggestion', text)
    b.onclick = () => { const i = document.getElementById('ap-input'); i.value = text; _apResize(); i.focus() }
    list.appendChild(b)
  })
  box.appendChild(list)
  thread.appendChild(box)
}

function _apResize() {
  const i = document.getElementById('ap-input')
  i.style.height = 'auto'
  i.style.height = Math.min(i.scrollHeight, 180) + 'px'
}

function _apScroll() {
  const t = document.getElementById('ap-thread')
  t.scrollTop = t.scrollHeight
}

// Plain text with `code`, **bold** and "- " lists, built safely.
function _apRichText(text) {
  const wrap = _el('div', 'ap-text')
  let list = null
  const inline = (parent, line) => {
    line.split(/(`[^`]+`|\*\*[^*]+\*\*)/g).forEach(part => {
      if (!part) return
      if (part.startsWith('`') && part.endsWith('`')) parent.appendChild(_el('code', '', part.slice(1, -1)))
      else if (part.startsWith('**') && part.endsWith('**')) parent.appendChild(_el('strong', '', part.slice(2, -2)))
      else parent.appendChild(document.createTextNode(part))
    })
  }
  text.split('\n').forEach(line => {
    const item = line.match(/^\s*(?:[-*]|\d+[.)])\s+(.*)/)
    if (item) {
      if (!list) { list = _el('ul'); wrap.appendChild(list) }
      const li = _el('li'); inline(li, item[1]); list.appendChild(li)
      return
    }
    list = null
    if (line.trim()) { const p = _el('p'); inline(p, line); wrap.appendChild(p) }
  })
  return wrap
}

function _apMessage(role) {
  const thread = document.getElementById('ap-thread')
  thread.querySelector('.ap-welcome')?.remove()
  const msg = _el('div', `ap-msg ap-${role}`)
  thread.appendChild(msg)
  return msg
}

function _apSteps(msg) {
  const steps = _el('details', 'ap-steps')
  steps.open = true
  const summary = _el('summary', '', 'Working…')
  steps.append(summary, _el('ol'))
  msg.appendChild(steps)
  return {
    add(text) { steps.querySelector('ol').appendChild(_el('li', '', text)); summary.textContent = text + '…'; _apScroll() },
    note(text, cls) { const last = steps.querySelector('ol').lastElementChild; if (last) last.appendChild(_el('div', cls || 'ap-step-note', text)) },
    finish() {
      const n = steps.querySelector('ol').children.length
      summary.textContent = n ? `${n} step${n === 1 ? '' : 's'}` : 'Done'
      steps.open = false
      if (!n) steps.remove()
    },
  }
}

async function _apStream(url, body, onEvent) {
  const r = await apiFetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
  if (!r.ok) {
    const err = await r.json().catch(() => ({}))
    throw Object.assign(new Error(err.error || `The request failed (${r.status})`), { status: r.status })
  }
  const reader = r.body.getReader()
  const decoder = new TextDecoder()
  let buf = ''
  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buf += decoder.decode(value, { stream: true })
    const parts = buf.split('\n\n')
    buf = parts.pop()
    for (const part of parts) if (part.startsWith('data:')) await onEvent(JSON.parse(part.slice(5).trim()))
  }
}

function _apSetBusy(busy) {
  _apBusy = busy
  const send = document.getElementById('ap-send')
  send.disabled = busy
  send.classList.toggle('busy', busy)
  document.querySelectorAll('.ap-mode').forEach(b => { b.disabled = busy })
}

async function sendAgentMessage() {
  const input = document.getElementById('ap-input')
  const text = input.value.trim()
  if ((!text && !(_apMode === 'build' && _apFiles.length)) || _apBusy) return
  const keyInput = document.getElementById('ap-key')
  if (keyInput && keyInput.value.trim()) _apKey = keyInput.value.trim()
  if (_apMode === 'build') {
    const hasApp = document.querySelectorAll('#file-tree [data-path$=".mcn"]').length > 0
    if (hasApp && !(await showIdeConfirm('Replace this app?', 'The agent team writes a new backend/main.mcn and ui/app.mcn in this workspace.', { confirmText: 'Build new app' }))) return
  }
  input.value = ''
  _apResize()
  const userMsg = _apMessage('user')
  userMsg.appendChild(_apRichText(text || 'Build the app described in the attached files.'))
  if (_apMode === 'build' && _apFiles.length) userMsg.appendChild(_el('div', 'ap-user-files', '📎 ' + _apFiles.map(f => f.name).join(', ')))
  const msg = _apMessage('assistant')
  const steps = _apSteps(msg)
  _apSetBusy(true)
  _apScroll()
  try {
    await saveAllTabs()                         // the agent reads the files on disk
    if (_apMode === 'build') await _apBuild(text, msg, steps)
    else await _apChange(text, msg, steps)
  } catch (e) {
    steps.finish()
    if (e.status === 400 && /API key|No AI model/i.test(e.message)) {
      document.getElementById('ap-key-row').classList.remove('hidden')
      msg.appendChild(_el('div', 'ap-error', 'Add an API key below (Claude, OpenAI, Gemini or OpenRouter), then send again. To use a local model, set it up with mcn config set ai_provider ollama.'))
      input.value = text
      _apResize()
    } else {
      msg.appendChild(_el('div', 'ap-error', e.message))
    }
  } finally {
    _apSetBusy(false)
    _apScroll()
  }
}

const AP_OP_LABELS = {
  inspect: 'Read the app', find: 'Searched for', explain: 'Looked at', create: 'Added', modify: 'Changed',
  remove: 'Removed', validate: 'Checked the patch', test: 'Ran the tests',
}

async function _apChange(text, msg, steps) {
  await _apStream('/api/agent/change', { prompt: text, mode: _apMode === 'ask' ? 'ask' : 'change', api_key: _apKey }, ev => {
    if (ev.type === 'operation') {
      const detail = ev.input.target || ev.input.query || ev.input.kind || ''
      steps.add(`${AP_OP_LABELS[ev.name] || ev.name} ${detail}`.trim())
    } else if (ev.type === 'result' && ev.error) {
      steps.note(ev.error, 'ap-step-error')
    } else if (ev.type === 'done') {
      steps.finish()
      if (ev.mode === 'ask' || !ev.patch) {
        msg.appendChild(_apRichText(ev.summary || (ev.mode === 'ask' ? 'No answer.' : 'No change was made.')))
        return
      }
      const box = _el('div', 'change-review ap-review')
      msg.appendChild(box)
      _renderReview('ap', ev, box)
      const actions = box.querySelector('.change-actions')
      const discard = actions && actions.querySelector('.btn:not(.btn-primary)')
      if (discard) discard.onclick = () => actions.replaceWith(_el('div', 'change-line', 'Discarded; nothing was written'))
    } else if (ev.type === 'error') {
      steps.finish()
      msg.appendChild(_el('div', 'ap-error', ev.message))
    }
  })
}

const AP_ROLE_NAMES = { researcher: 'Researcher', architect: 'Architect', designer: 'Designer', builder: 'Builder', qa: 'QA lead' }

async function _apBuild(text, msg, steps) {
  const attachments = _apFiles.map(({ name, type, size, data }) => ({ name, type, size, data }))
  _apFiles = []
  _apRenderFiles()
  await _apStream('/api/agent/team', { description: text, attachments, api_key: _apKey }, async ev => {
    if (ev.type === 'agent' && ev.status !== 'working') {
      steps.add(`${AP_ROLE_NAMES[ev.role] || ev.role}: ${ev.summary || ev.status}`)
      ;(ev.fixes || []).slice(0, 6).forEach(f => steps.note(f))
    } else if (ev.type === 'agent') {
      document.querySelector('.ap-steps summary').textContent = `${AP_ROLE_NAMES[ev.role] || ev.role} is working…`
    } else if (ev.type === 'module') {
      if (ev.status !== 'working') steps.add(`Module ${ev.name}: ${ev.summary || ev.status}`)
    } else if (ev.type === 'done') {
      steps.finish()
      for (const [path, content] of [['backend/main.mcn', ev.backend], ['ui/app.mcn', ev.ui]]) {
        if (content && _models.has(path)) {
          _models.get(path).setValue(content)
          if (_tabState.has(path)) _tabState.get(path).dirty = false
        }
      }
      await loadFileTree()
      msg.appendChild(_apRichText(ev.verdict === 'pass'
        ? 'The team built the app and QA approved it.'
        : 'The team built the app. QA still had notes after two rounds of fixes; they are in the steps above.'))
      const actions = _el('div', 'change-actions')
      const open = _el('button', 'btn btn-sm', 'Open ui/app.mcn')
      open.onclick = () => openFile('ui/app.mcn')
      const preview = _el('button', 'btn btn-primary btn-sm', 'Preview')
      preview.onclick = () => buildAndLaunchPreview()
      actions.append(open, preview)
      msg.appendChild(actions)
    } else if (ev.type === 'error') {
      steps.finish()
      msg.appendChild(_el('div', 'ap-error', ev.message))
    }
  })
}

document.addEventListener('DOMContentLoaded', initAgentPanel)
if (document.readyState !== 'loading') initAgentPanel()

function initAgentPanel() {
  const input = document.getElementById('ap-input')
  if (!input || input.dataset.ready) return
  input.dataset.ready = '1'
  input.addEventListener('input', _apResize)
  input.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); sendAgentMessage() }
  })
  document.querySelectorAll('.ap-mode').forEach(b => { b.onclick = () => setAgentMode(b.dataset.mode) })
  setAgentMode('change')
  window.addEventListener('keydown', e => {
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'l') { e.preventDefault(); openAgentPanel() }
  })
}
