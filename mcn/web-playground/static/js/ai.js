// ── AI Studio Logic ───────────────────────────────────────────────────────────
let _customSubagents = [];
let _activeAgents = [];
let _activeDataSources = [];

function toggleSourcePayloadType() {
  const type = document.getElementById('ai-source-type').value;
  if (type === 'text') {
    document.getElementById('ai-payload-text-group').classList.remove('hidden');
    document.getElementById('ai-payload-file-group').classList.add('hidden');
  } else {
    document.getElementById('ai-payload-text-group').classList.add('hidden');
    document.getElementById('ai-payload-file-group').classList.remove('hidden');
  }
}

function addCustomSubagent() {
  const input = document.getElementById('ai-new-subagent');
  const val = input.value.trim();
  if (!val) return;
  input.value = '';
  
  if (!_customSubagents.includes(val)) {
    _customSubagents.push(val);
    renderSubagentsChecklist();
  }
}

function renderSubagentsChecklist() {
  const list = document.getElementById('ai-sub-agents-list');
  list.innerHTML = '';
  
  const allAgents = [...new Set([..._activeAgents, ..._customSubagents])];
  if (allAgents.length === 0) {
    list.innerHTML = '<div style="font-style:italic;color:var(--muted);font-size:12px;">No agents defined yet. Define standard agents in main.mcn or add sub-agents below.</div>';
    return;
  }
  
  for (const agent of allAgents) {
    const div = document.createElement('div');
    div.style.display = 'flex';
    div.style.alignItems = 'center';
    div.style.gap = '8px';
    div.innerHTML = `<input type="checkbox" value="${agent}" class="subagent-cb" id="cb-${agent}" /> <label for="cb-${agent}" style="color:var(--text);font-size:12px;">${agent}</label>`;
    list.appendChild(div);
  }
}

async function refreshAIStudioGUI() {
  try {
    // Read main.mcn backend file content and search for agent/datasource declarations
    const r = await apiFetch('/api/workspace/file?path=backend/main.mcn');
    if (r.ok) {
      const d = await r.json();
      const code = d.content;
      
      // Basic regex parsing to extract defined agents and datasources
      const agentRegex = /agent\(\s*["']([^"']+)["']|create_agent\(\s*["']([^"']+)["']/g;
      const dsRegex = /datasource\(\s*["']create["']\s*,\s*["']([^"']+)["']/g;
      
      let match;
      _activeAgents = [];
      while ((match = agentRegex.exec(code)) !== null) {
        _activeAgents.push(match[1] || match[2]);
      }
      
      _activeDataSources = [];
      while ((match = dsRegex.exec(code)) !== null) {
        _activeDataSources.push(match[1]);
      }
      
      _activeAgents = [...new Set(_activeAgents)];
      _activeDataSources = [...new Set(_activeDataSources)];
    }
  } catch (e) {}
  
  renderSubagentsChecklist();
  renderConnectedDataSources();
  updateSelectors();
}

function renderConnectedDataSources() {
  const container = document.getElementById('ai-data-sources-list');
  container.innerHTML = '';
  
  if (_activeDataSources.length === 0) {
    container.innerHTML = '<div style="grid-column:1/-1;text-align:center;padding:16px;color:var(--muted);font-style:italic;">No knowledge sources active in memory. Use the form above to ingest documents.</div>';
    return;
  }
  
  for (const ds of _activeDataSources) {
    const card = document.createElement('div');
    card.className = 'ai-card';
    card.style.borderRadius = '8px';
    card.style.padding = '12px';
    card.style.display = 'flex';
    card.style.flexDirection = 'column';
    card.style.gap = '6px';
    card.innerHTML = `
      <div style="font-weight:bold;color:#818cf8;font-size:13px;display:flex;align-items:center;justify-content:space-between;">
        <span>${ds}</span>
        <span class="ai-badge" style="font-size:9px;padding:1px 4px;">RAG Ready</span>
      </div>
      <div style="font-size:11px;color:var(--muted)">Connected to vector search pipeline.</div>
    `;
    container.appendChild(card);
  }
}

function updateSelectors() {
  // Update Agent Selector in dialogue box
  const chatSel = document.getElementById('chat-agent-selector');
  const originalChatVal = chatSel.value;
  chatSel.innerHTML = '<option value="">(Select Agent)</option>';
  
  // Include custom and discovered agents
  const allAgents = [...new Set([..._activeAgents, ..._customSubagents])];
  for (const agent of allAgents) {
    const opt = document.createElement('option');
    opt.value = agent;
    opt.textContent = agent;
    chatSel.appendChild(opt);
  }
  chatSel.value = originalChatVal;

  // Update Datasource Selector in dialogue box
  const dsSel = document.getElementById('search-ds-selector');
  const originalDsVal = dsSel.value;
  dsSel.innerHTML = '<option value="">(Select Source)</option>';
  
  for (const ds of _activeDataSources) {
    const opt = document.createElement('option');
    opt.value = ds;
    opt.textContent = ds;
    dsSel.appendChild(opt);
  }
  dsSel.value = originalDsVal;
}

async function createMultiAgent() {
  const name = document.getElementById('ai-agent-name').value.trim();
  const prompt = document.getElementById('ai-agent-prompt').value.trim();
  
  if (!name || !prompt) {
    await showIdeAlert("Missing Information", "Please enter both an agent name and coordinator prompt.", "warn");
    return;
  }
  
  // Get checked sub-agents
  const subAgents = [];
  document.querySelectorAll('.subagent-cb:checked').forEach(cb => {
    subAgents.push(cb.value);
  });
  
  const mcnCode = `\n// Multi-Agent coordinator created via AI Agent Studio\nagent("create_multi", "${name}", ${JSON.stringify(subAgents)}, "${prompt.replace(/"/g, '\\"')}")\nagent("activate", "${name}")\n`;
  
  try {
    // Append to main.mcn backend file
    const getRes = await apiFetch('/api/workspace/file?path=backend/main.mcn');
    if (getRes.ok) {
      const getD = await getRes.json();
      const updatedCode = getD.content + mcnCode;
      await apiFetch('/api/workspace/file', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: 'backend/main.mcn', content: updatedCode })
      });
      
      // Execute the statement immediately to register in server session
      await apiFetch('/api/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code: mcnCode })
      });
      
      showToast(`Multi-Agent Coordinator '${name}' registered successfully!`, 'success');
      appendLog('success', `✓ Multi-Agent Coordinator '${name}' registered successfully!`);
      document.getElementById('ai-agent-name').value = '';
      document.getElementById('ai-agent-prompt').value = '';
      document.querySelectorAll('.subagent-cb').forEach(cb => cb.checked = false);
      
      await refreshAIStudioGUI();
      await loadFileTree();
    }
  } catch (err) {
    appendLog('error', `✗ Failed to create Multi-Agent: ${err.message}`);
    await showIdeAlert('Registration Error', 'Failed to create Multi-Agent: ' + err.message, 'error');
  }
}

async function createDataSource() {
  const name = document.getElementById('ai-source-name').value.trim();
  const type = document.getElementById('ai-source-type').value;
  let payload = '';
  
  if (type === 'text') {
    payload = document.getElementById('ai-source-payload-text').value.trim();
  } else {
    payload = document.getElementById('ai-source-payload-file').value.trim();
  }
  
  if (!name || !payload) {
    await showIdeAlert("Missing Information", "Please fill in source name and data details.", "warn");
    return;
  }
  
  const mcnCode = `\n// Knowledge source ingested via AI Agent Studio\ndatasource("create", "${name}", "${type}", "${payload.replace(/\n/g, '\\n').replace(/"/g, '\\"')}")\n`;
  
  try {
    // Append to main.mcn backend file
    const getRes = await apiFetch('/api/workspace/file?path=backend/main.mcn');
    if (getRes.ok) {
      const getD = await getRes.json();
      const updatedCode = getD.content + mcnCode;
      await apiFetch('/api/workspace/file', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: 'backend/main.mcn', content: updatedCode })
      });
      
      // Execute to update memory
      await apiFetch('/api/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code: mcnCode })
      });
      
      appendLog('success', `✓ Knowledge Base '${name}' indexed successfully!`);
      document.getElementById('ai-source-name').value = '';
      document.getElementById('ai-source-payload-text').value = '';
      document.getElementById('ai-source-payload-file').value = '';
      
      await refreshAIStudioGUI();
      await loadFileTree();
    }
  } catch (err) {
    appendLog('error', `✗ Failed to create knowledge source: ${err.message}`);
  }
}

function updateSelectedAgentChat() {
  const agent = document.getElementById('chat-agent-selector').value;
  const msgs = document.getElementById('chat-sandbox-messages');
  msgs.innerHTML = '';
  if (agent) {
    const welcome = document.createElement('div');
    welcome.style.color = '#a78bfa';
    welcome.style.fontStyle = 'italic';
    welcome.textContent = `Dialogue active with agent '${agent}'. Send a prompt below.`;
    msgs.appendChild(welcome);
  } else {
    msgs.innerHTML = '<div style="color:#64748b;font-style:italic;">Choose an agent from the dropdown to start chatting.</div>';
  }
}

async function sendChatSandboxMsg() {
  const agent = document.getElementById('chat-agent-selector').value;
  const input = document.getElementById('chat-sandbox-input');
  const prompt = input.value.trim();
  
  if (!agent || !prompt) return;
  input.value = '';
  
  const msgs = document.getElementById('chat-sandbox-messages');
  
  // Render user prompt
  const userEl = document.createElement('div');
  userEl.style.color = '#f3f4f6';
  userEl.innerHTML = `<span style="font-weight:bold;color:#94a3b8;">User:</span> ${prompt}`;
  msgs.appendChild(userEl);
  
  const code = `agent("think", "${agent}", "${prompt.replace(/"/g, '\\"')}")`;
  
  try {
    const r = await apiFetch('/api/execute', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code })
    });
    const d = await r.json();
    
    const botEl = document.createElement('div');
    if (d.success && d.result) {
      botEl.style.color = '#a78bfa';
      botEl.innerHTML = `<span style="font-weight:bold;color:#c084fc;">${agent}:</span> ${d.result}`;
    } else {
      botEl.style.color = '#ef4444';
      botEl.textContent = `Agent Error: ${d.error || 'Empty response'}`;
    }
    msgs.appendChild(botEl);
  } catch (err) {
    const botEl = document.createElement('div');
    botEl.style.color = '#ef4444';
    botEl.textContent = `Connection Error: ${err.message}`;
    msgs.appendChild(botEl);
  }
  msgs.scrollTop = msgs.scrollHeight;
}

function handleChatSandboxKey(e) {
  if (e.key === 'Enter') sendChatSandboxMsg();
}

async function querySearchSandbox() {
  const ds = document.getElementById('search-ds-selector').value;
  const input = document.getElementById('search-sandbox-input');
  const query = input.value.trim();
  
  if (!ds || !query) return;
  input.value = '';
  
  const results = document.getElementById('search-sandbox-results');
  results.textContent = 'Searching vector storage index...';
  
  const code = `rag("query_datasource", "${query.replace(/"/g, '\\"')}", "${ds}")`;
  
  try {
    const r = await apiFetch('/api/execute', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code })
    });
    const d = await r.json();
    
    if (d.success && d.result) {
      results.style.color = '#f8fafc';
      results.textContent = d.result;
    } else {
      results.style.color = '#fca5a5';
      results.textContent = `Search Error: ${d.error || 'No results'}`;
    }
  } catch (err) {
    results.style.color = '#fca5a5';
    results.textContent = `Connection Error: ${err.message}`;
  }
}

function handleSearchSandboxKey(e) {
  if (e.key === 'Enter') querySearchSandbox();
}

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

// ── Generate modal & Attachments ──────────────────────────────────────────
let _genAttachments = []

function formatFileSize(bytes) {
  if (!bytes) return '0 B'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

function handleGenFileSelect(fileList) {
  if (!fileList || fileList.length === 0) return
  const maxFiles = 6
  const maxBytes = 15 * 1024 * 1024 // 15MB

  for (let i = 0; i < fileList.length; i++) {
    const file = fileList[i]
    if (_genAttachments.length >= maxFiles) {
      showToast(`Maximum ${maxFiles} attachments allowed`, 'warn')
      break
    }
    if (file.size > maxBytes) {
      showToast(`File "${file.name}" exceeds 15MB limit`, 'warn')
      continue
    }

    const reader = new FileReader()
    reader.onload = (e) => {
      const dataUrl = e.target.result
      const isImg = file.type.startsWith('image/') || /\.(png|jpe?g|webp|gif|svg)$/i.test(file.name)
      const isPdf = file.type === 'application/pdf' || /\.pdf$/i.test(file.name)
      
      _genAttachments.push({
        name: file.name,
        type: file.type || (isPdf ? 'application/pdf' : isImg ? 'image/png' : 'text/plain'),
        size: file.size,
        data: dataUrl,
        isImg: isImg,
        isPdf: isPdf
      })
      renderGenAttachments()
    }
    reader.readAsDataURL(file)
  }
  const input = document.getElementById('gen-file-input')
  if (input) input.value = ''
}

function removeGenAttachment(index) {
  _genAttachments.splice(index, 1)
  renderGenAttachments()
}

function renderGenAttachments() {
  const container = document.getElementById('gen-attachments-list')
  const countSpan = document.getElementById('gen-att-count')
  if (!container) return

  if (_genAttachments.length === 0) {
    container.innerHTML = ''
    if (countSpan) countSpan.textContent = ''
    return
  }

  if (countSpan) countSpan.textContent = `${_genAttachments.length} file(s) attached`

  container.innerHTML = _genAttachments.map((att, idx) => {
    let iconHtml = ''
    if (att.isImg) {
      iconHtml = `<img src="${att.data}" class="copilot-att-thumb" alt="${att.name}" />`
    } else if (att.isPdf) {
      iconHtml = `<div class="copilot-att-icon" style="background:rgba(239,68,68,0.15); color:#ef4444;">📄</div>`
    } else {
      iconHtml = `<div class="copilot-att-icon">📋</div>`
    }

    const safeName = att.name.replace(/</g, '&lt;').replace(/>/g, '&gt;')
    return `
      <div class="copilot-att-chip">
        ${iconHtml}
        <div class="copilot-att-info">
          <span class="copilot-att-name" title="${safeName}">${safeName}</span>
          <span class="copilot-att-size">${formatFileSize(att.size)}</span>
        </div>
        <button type="button" class="copilot-att-remove" onclick="removeGenAttachment(${idx})" title="Remove attachment">&times;</button>
      </div>
    `
  }).join('')
}

function setupDropzone() {
  const dz = document.getElementById('gen-dropzone')
  if (!dz || dz._dzInit) return
  dz._dzInit = true
  ;['dragenter', 'dragover'].forEach(eventName => {
    dz.addEventListener(eventName, (e) => {
      e.preventDefault(); e.stopPropagation()
      dz.classList.add('dragover')
    }, false)
  })
  ;['dragleave', 'drop'].forEach(eventName => {
    dz.addEventListener(eventName, (e) => {
      e.preventDefault(); e.stopPropagation()
      dz.classList.remove('dragover')
    }, false)
  })
  dz.addEventListener('drop', (e) => {
    e.preventDefault(); e.stopPropagation()
    const dt = e.dataTransfer
    if (dt && dt.files && dt.files.length) {
      handleGenFileSelect(dt.files)
    }
  }, false)
}

function openGenerateModal() {
  document.getElementById('gen-modal').classList.remove('hidden')
  document.getElementById('gen-desc').focus()
  const successCard = document.getElementById('gen-success-card')
  if (successCard) successCard.classList.add('hidden')
  setupDropzone()
}

function closeGenerateModal() {
  document.getElementById('gen-modal').classList.add('hidden')
  document.getElementById('gen-stream').textContent = ''
  document.getElementById('gen-stream').classList.add('hidden')
  document.getElementById('gen-status').classList.add('hidden')
  const successCard = document.getElementById('gen-success-card')
  if (successCard) successCard.classList.add('hidden')
  document.getElementById('gen-submit').disabled = false
  _genAttachments = []
  renderGenAttachments()
}

// ── Agent team progress ─────────────────────────────────────────────────────

const TEAM_ROLES = [
  ['researcher', 'Researcher', 'Works out what this kind of app needs'],
  ['architect', 'Architect', 'Plans the data, endpoints and screens'],
  ['designer', 'Designer', 'Designs each screen'],
  ['builder', 'Builder', 'Writes backend/main.mcn and ui/app.mcn, one builder per module at the same time'],
  ['qa', 'QA lead', 'Tests every endpoint and screen in a browser'],
]
let _teamState = {}
let _teamModules = {}        // modules the builders are writing at the same time

function renderTeamPanel() {
  const panel = document.getElementById('team-panel')
  const on = document.getElementById('gen-team')?.checked
  if (!panel) return
  panel.classList.toggle('hidden', !on)
  const btn = document.getElementById('gen-submit')
  if (btn) btn.textContent = on ? 'Build with the Agent Team' : 'Generate Full-Stack App'
  panel.innerHTML = ''
  TEAM_ROLES.forEach(([role, name, about], i) => {
    const st = _teamState[role] || {}
    const li = document.createElement('li')
    li.className = 'team-step'
    li.dataset.status = st.status || 'waiting'
    const dot = document.createElement('span')
    dot.className = 'dot'
    dot.textContent = st.status === 'done' ? '✓' : st.status === 'failed' ? '!' : String(i + 1)
    const body = document.createElement('div')
    const title = document.createElement('div')
    title.className = 'team-step-role'
    title.textContent = name
    const summary = document.createElement('div')
    summary.className = 'team-step-summary'
    summary.textContent = st.summary || (st.status === 'working' ? 'Working…' : about)
    body.append(title, summary)
    if (role === 'builder' && Object.keys(_teamModules).length) {
      const ul = document.createElement('ul')
      ul.className = 'team-step-fixes team-step-modules'
      Object.entries(_teamModules).forEach(([name, m]) => {
        const item = document.createElement('li')
        const mark = m.status === 'done' ? '✓ ' : m.status === 'failed' ? '! ' : '… '
        item.textContent = mark + name + (m.summary ? ': ' + m.summary : '')
        ul.appendChild(item)
      })
      body.appendChild(ul)
    }
    if (st.fixes && st.fixes.length) {
      const ol = document.createElement('ol')
      ol.className = 'team-step-fixes'
      st.fixes.slice(0, 6).forEach(f => { const item = document.createElement('li'); item.textContent = f; ol.appendChild(item) })
      body.appendChild(ol)
    }
    li.append(dot, body)
    panel.appendChild(li)
  })
}

async function submitGenerate() {
  const desc   = document.getElementById('gen-desc').value.trim()
  const apiKey = document.getElementById('gen-key').value.trim()
  if (!desc && _genAttachments.length === 0) {
    await showIdeAlert('Specification Required', 'Please enter a description or attach design/specification files (BRDs, Flowcharts, Figma mockups) to generate your application.', 'warn')
    return
  }

  const payload = {
    description: desc,
    api_key: apiKey,
    attachments: _genAttachments.map(a => ({
      name: a.name,
      type: a.type,
      size: a.size,
      data: a.data
    }))
  }

  document.getElementById('gen-submit').disabled = true
  const successCard = document.getElementById('gen-success-card')
  if (successCard) successCard.classList.add('hidden')
  document.getElementById('gen-status').classList.remove('hidden')
  document.getElementById('gen-stream').classList.remove('hidden')
  document.getElementById('gen-stream').textContent = ''
  document.getElementById('gen-status-text').textContent = _genAttachments.length > 0
    ? `Analyzing ${_genAttachments.length} design attachment(s) & generating…`
    : 'Connecting…'

  const useTeam = !!document.getElementById('gen-team')?.checked
  _teamState = {}
  _teamModules = {}
  if (useTeam) renderTeamPanel()

  try {
    const r = await apiFetch(useTeam ? '/api/agent/team' : '/api/generate', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
    if (!r.ok) {
      const err = await r.json()
      await showIdeAlert('Generation Failed', err.error || 'Full-stack generation failed', 'error')
      document.getElementById('gen-submit').disabled = false
      document.getElementById('gen-status').classList.add('hidden')
      return
    }

    const reader  = r.body.getReader()
    const decoder = new TextDecoder()
    let   buf     = ''
    document.getElementById('gen-status-text').textContent = 'Generating full-stack code…'

    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      buf += decoder.decode(value, { stream: true })
      const parts = buf.split('\n\n')
      buf = parts.pop()
      for (const part of parts) {
        if (!part.startsWith('data:')) continue
        const ev = JSON.parse(part.slice(5).trim())
        if (ev.type === 'token') {
          const s = document.getElementById('gen-stream')
          s.textContent += ev.text
          s.scrollTop = s.scrollHeight
        } else if (ev.type === 'agent') {
          _teamState[ev.role] = { status: ev.status, summary: ev.summary, fixes: ev.fixes }
          const label = (TEAM_ROLES.find(r => r[0] === ev.role) || [])[1] || ev.role
          document.getElementById('gen-status-text').textContent =
            ev.status === 'working' ? `${label}: ${ev.summary || 'working…'}` : `${label}: ${ev.summary || ev.status}`
          renderTeamPanel()
        } else if (ev.type === 'module') {
          _teamModules[ev.name] = { status: ev.status, summary: ev.summary }
          renderTeamPanel()
        } else if (ev.type === 'qa') {
          appendLog('info', `QA round ${ev.round}: ` + JSON.stringify(ev.report).slice(0, 400))
        } else if (ev.type === 'status') {
          document.getElementById('gen-status-text').textContent = ev.text
        } else if (ev.type === 'done') {
          document.getElementById('gen-status').classList.add('hidden')
          document.getElementById('gen-submit').disabled = false
          showToast(ev.verdict === 'fix'
            ? 'The team built the app; QA still had notes (see the log)'
            : 'AI Application generated successfully from requirements & designs!', ev.verdict === 'fix' ? 'warning' : 'success')
          if (ev.backend) {
            await apiFetch('/api/workspace/file', {
              method: 'POST', headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ path: 'backend/main.mcn', content: ev.backend })
            })
            if (_models.has('backend/main.mcn')) {
              _models.get('backend/main.mcn').setValue(ev.backend)
              if (_tabState.has('backend/main.mcn')) _tabState.get('backend/main.mcn').dirty = false
            }
          }
          if (ev.ui) {
            await apiFetch('/api/workspace/file', {
              method: 'POST', headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ path: 'ui/app.mcn', content: ev.ui })
            })
            if (_models.has('ui/app.mcn')) {
              _models.get('ui/app.mcn').setValue(ev.ui)
              if (_tabState.has('ui/app.mcn')) _tabState.get('ui/app.mcn').dirty = false
            }
          }
          await loadFileTree()
          if (successCard) successCard.classList.remove('hidden')
        } else if (ev.type === 'error') {
          appendLog('error', '✗ Generation error: ' + ev.message)
          await showIdeAlert('Generation Error', 'Error: ' + ev.message, 'error')
          document.getElementById('gen-submit').disabled = false
          document.getElementById('gen-status').classList.add('hidden')
        }
      }
    }
  } catch (e) {
    appendLog('error', '✗ ' + e.message)
    await showIdeAlert('Generation Error', 'Error: ' + e.message, 'error')
    document.getElementById('gen-submit').disabled = false
    document.getElementById('gen-status').classList.add('hidden')
  }
}

document.getElementById('gen-modal').addEventListener('click', function(e) {
  if (e.target === this) closeGenerateModal()
})

// ── AI Agent Studio ─────────────────────────────────────────────────────────

let _agentSuccessTarget = 'ui/app.mcn';

function openAgentStudioModal() {
  document.getElementById('agent-studio-modal').classList.remove('hidden')
  document.getElementById('agent-prompt').focus()
  const successCard = document.getElementById('agent-success-card')
  if (successCard) successCard.classList.add('hidden')
}

function closeAgentStudioModal() {
  document.getElementById('agent-studio-modal').classList.add('hidden')
  document.getElementById('agent-status').classList.add('hidden')
  const successCard = document.getElementById('agent-success-card')
  if (successCard) successCard.classList.add('hidden')
  document.getElementById('agent-submit').disabled = false
}

async function submitAgentEnhance() {
  const prompt  = document.getElementById('agent-prompt').value.trim()
  const apiKey  = document.getElementById('agent-key').value.trim()
  const modeVal = document.getElementById('agent-mode-val')
  const mode    = modeVal ? modeVal.value : 'mcn'

  if (!prompt) {
    await showIdeAlert('Prompt Required', 'Please enter instructions for the AI Coding Agent.', 'warn');
    return
  }

  // Determine the target file path
  let targetPath = ''
  if (mode === 'mcn') {
    // Default to the active MCN UI file
    targetPath = _activeFile || 'ui/app.mcn'
  } else {
    // For compiled mode, target the generated App.tsx
    targetPath = 'frontend/src/App.tsx'
  }
  _agentSuccessTarget = targetPath

  if (mode === 'mcn') {
    // MCN changes go through the agent interface: a checked patch you approve
    _agentSuccessTarget = 'ui/app.mcn'
    return runChangeAgent('agent', prompt, apiKey, 'ui')
  }

  document.getElementById('agent-submit').disabled = true
  const successCard = document.getElementById('agent-success-card')
  if (successCard) successCard.classList.add('hidden')
  document.getElementById('agent-status').classList.remove('hidden')
  document.getElementById('agent-status-text').textContent = 'AI Coding Agent analyzing interface…'

  try {
    const r = await apiFetch('/api/agent/enhance', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: targetPath, prompt, mode, api_key: apiKey })
    })
    const data = await r.json()

    if (!data.success) {
      document.getElementById('agent-status-text').textContent = '✗ ' + (data.error || 'Enhancement failed')
      document.getElementById('agent-submit').disabled = false
      await showIdeAlert('Enhancement Failed', data.error || 'Enhancement failed', 'error');
      return
    }

    // Update Monaco editor if the file is already open
    if (data.content && _models.has(targetPath)) {
      _models.get(targetPath).setValue(data.content)
      if (_tabState.has(targetPath)) _tabState.get(targetPath).dirty = false
    }

    await loadFileTree()
    document.getElementById('agent-status').classList.add('hidden')
    document.getElementById('agent-submit').disabled = false
    showToast(data.message || 'UI Enhancement applied successfully!', 'success')
    
    const badge = document.getElementById('agent-success-badge')
    if (badge) badge.textContent = `✓ ${targetPath}`
    if (successCard) successCard.classList.remove('hidden')

  } catch (e) {
    document.getElementById('agent-status-text').textContent = '✗ Error: ' + e.message
    document.getElementById('agent-submit').disabled = false
    await showIdeAlert('Enhancement Error', 'Error: ' + e.message, 'error')
  }
}

document.getElementById('agent-studio-modal').addEventListener('click', function(e) {
  if (e.target === this) closeAgentStudioModal()
})

// ── Changes through the agent interface ─────────────────────────────────────
// The agent inspects, finds and explains, then builds a patch of create / modify /
// remove operations and validates and tests it. Nothing is written until Apply.

const OP_LABELS = {
  inspect: 'Reading the app', find: 'Finding', explain: 'Looking at', create: 'Adding', modify: 'Changing',
  remove: 'Removing', validate: 'Checking the patch', test: 'Running the tests',
}

function _changeEl(prefix) {
  let box = document.getElementById(`${prefix}-review`)
  if (!box) {
    box = document.createElement('div')
    box.id = `${prefix}-review`
    box.className = 'change-review hidden'
    const card = document.getElementById(`${prefix}-success-card`)
    card.parentNode.insertBefore(box, card)
  }
  return box
}

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
  if (ev.summary) box.appendChild(_el('p', 'change-summary', ev.summary))
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
    box.classList.add('hidden')
    const badge = document.getElementById(`${prefix}-success-badge`)
    if (badge) badge.textContent = '✓ ' + data.files.join(', ')
    const summary = document.getElementById(`${prefix}-success-summary`)
    if (summary) summary.textContent = ev.summary || 'Applied the reviewed change.'
    document.getElementById(`${prefix}-success-card`).classList.remove('hidden')
    showToast('Change applied to ' + data.files.join(', '), 'success')
  } catch (e) {
    button.disabled = false
    await showIdeAlert('Not Applied', 'Error: ' + e.message, 'error')
  }
}

async function runChangeAgent(prefix, prompt, apiKey, area) {
  const submit = document.getElementById(`${prefix}-submit`)
  const status = document.getElementById(`${prefix}-status`)
  const statusText = document.getElementById(`${prefix}-status-text`)
  const box = _changeEl(prefix)
  submit.disabled = true
  document.getElementById(`${prefix}-success-card`).classList.add('hidden')
  box.replaceChildren()
  box.classList.remove('hidden')
  const ops = _el('ol', 'change-ops')
  box.appendChild(ops)
  status.classList.remove('hidden')
  statusText.textContent = 'Saving open files…'
  const finish = () => { status.classList.add('hidden'); submit.disabled = false }
  try {
    await saveAllTabs()                 // the agent reads the files on disk
    statusText.textContent = 'The agent is reading the app…'
    const r = await apiFetch('/api/agent/change', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt, api_key: apiKey, area })
    })
    if (!r.ok) {
      const err = await r.json().catch(() => ({}))
      finish(); box.classList.add('hidden')
      await showIdeAlert('Agent Failed', err.error || 'The agent could not start', 'error')
      return
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
      for (const part of parts) {
        if (!part.startsWith('data:')) continue
        const ev = JSON.parse(part.slice(5).trim())
        if (ev.type === 'operation') {
          const detail = ev.input.target || ev.input.query || ev.input.kind || ''
          const text = `${OP_LABELS[ev.name] || ev.name} ${detail}`.trim()
          statusText.textContent = text + '…'
          ops.appendChild(_el('li', '', text))
        } else if (ev.type === 'result' && ev.error) {
          const last = ops.lastElementChild
          if (last) last.appendChild(_el('div', 'change-op-error', ev.error))
        } else if (ev.type === 'done') {
          finish()
          _renderReview(prefix, ev, box)
        } else if (ev.type === 'error') {
          finish()
          box.replaceChildren(_el('p', 'change-line bad', '✗ ' + ev.message))
        }
      }
    }
  } catch (e) {
    finish()
    box.replaceChildren(_el('p', 'change-line bad', '✗ ' + e.message))
  } finally {
    submit.disabled = false
  }
}

// ── Backend Agent ────────────────────────────────────────────────────────────

function openBackendAgentModal() {
  document.getElementById('backend-agent-modal').classList.remove('hidden')
  document.getElementById('backend-prompt').focus()
  const successCard = document.getElementById('backend-success-card')
  if (successCard) successCard.classList.add('hidden')
}

function closeBackendAgentModal() {
  document.getElementById('backend-agent-modal').classList.add('hidden')
  document.getElementById('backend-status').classList.add('hidden')
  const successCard = document.getElementById('backend-success-card')
  if (successCard) successCard.classList.add('hidden')
  document.getElementById('backend-submit').disabled = false
}

async function submitBackendAgent() {
  const prompt = document.getElementById('backend-prompt').value.trim()
  const apiKey = document.getElementById('backend-key').value.trim()
  const modeVal = document.getElementById('backend-mode-val')
  const mode   = modeVal ? modeVal.value : 'backend'

  if (!prompt) {
    await showIdeAlert('Prompt Required', 'Please enter a prompt for the Backend Agent.', 'warn');
    return
  }

  // Target file: always backend/main.mcn
  const targetPath = 'backend/main.mcn'
  if (mode === 'backend') return runChangeAgent('backend', prompt, apiKey, 'backend')

  document.getElementById('backend-submit').disabled = true
  const successCard = document.getElementById('backend-success-card')
  if (successCard) successCard.classList.add('hidden')
  document.getElementById('backend-status').classList.remove('hidden')
  document.getElementById('backend-status-text').textContent = 'Backend Agent synthesizing code…'

  try {
    const r = await apiFetch('/api/agent/enhance', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: targetPath, prompt, mode, api_key: apiKey })
    })
    const data = await r.json()

    if (!data.success) {
      document.getElementById('backend-status-text').textContent = '✗ ' + (data.error || 'Backend Agent failed')
      document.getElementById('backend-submit').disabled = false
      await showIdeAlert('Backend Agent Failed', data.error || 'Backend Agent failed', 'error');
      return
    }

    // Reflect changes in Monaco editor if the file is already loaded
    const writtenPath = data.path || targetPath
    if (data.content && _models.has(writtenPath)) {
      _models.get(writtenPath).setValue(data.content)
      if (_tabState.has(writtenPath)) _tabState.get(writtenPath).dirty = false
    }

    await loadFileTree()
    document.getElementById('backend-status').classList.add('hidden')
    document.getElementById('backend-submit').disabled = false
    showToast(data.message || 'Backend architecture updated!', 'success')

    if (successCard) successCard.classList.remove('hidden')

  } catch (e) {
    document.getElementById('backend-status-text').textContent = '✗ Error: ' + e.message
    document.getElementById('backend-submit').disabled = false
    await showIdeAlert('Backend Error', 'Error: ' + e.message, 'error')
  }
}

document.getElementById('backend-agent-modal').addEventListener('click', function(e) {
  if (e.target === this) closeBackendAgentModal()
})

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
