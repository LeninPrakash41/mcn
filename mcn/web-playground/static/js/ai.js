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

  try {
    const r = await apiFetch('/api/generate', {
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
        } else if (ev.type === 'status') {
          document.getElementById('gen-status-text').textContent = ev.text
        } else if (ev.type === 'done') {
          document.getElementById('gen-status').classList.add('hidden')
          document.getElementById('gen-submit').disabled = false
          showToast('AI Application generated successfully from requirements & designs!', 'success')
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

// ── Auth ────────────────────────────────────────────────────────────────────

let _authToken = localStorage.getItem('mcn_token') || ''
let _authUser  = null
let _authGuest = false

try { _authUser = JSON.parse(localStorage.getItem('mcn_user') || 'null') } catch(e) {}


function _getAuthHeaders() {
  return _authToken ? { 'Authorization': 'Bearer ' + _authToken } : {}
}

// Thin wrapper — adds auth headers to every API call automatically
async function apiFetch(url, opts = {}) {
  opts.headers = Object.assign({}, opts.headers || {}, _getAuthHeaders())
  return fetch(url, opts)
}

