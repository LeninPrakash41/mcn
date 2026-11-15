// ── Virtual lab: draws lab("greenhouse") and lab("rover") worlds live in the IoT panel ──

let _labTimer = null
let _labBusy = false
const _LAB_SPEEDS = {
  greenhouse: [[60, '1 min/s'], [600, '10 min/s'], [3600, '1 h/s']],
  rover: [[0.5, '½×'], [1, '1×'], [2, '2×']],
}

function _labEsc(v) { return escapeHtml(v == null ? '' : String(v)) }

async function refreshLab() {
  const box = document.getElementById('iot-lab')
  const panel = document.getElementById('panel-iot-simulator')
  if (!box || !panel) return
  if (!panel.classList.contains('active')) { _stopLab(); return }
  if (_labBusy) return
  _labBusy = true
  try {
    const d = await (await apiFetch('/api/iot/lab')).json()
    const labs = Object.values((d.success && d.labs) || {})
    if (!labs.length) { box.innerHTML = ''; _stopLab(); return }
    box.innerHTML = labs.map(_labCard).join('')
    if (!_labTimer) _labTimer = setInterval(refreshLab, 350)
  } catch (e) {
    box.innerHTML = ''
  } finally {
    _labBusy = false
  }
}

function _stopLab() { if (_labTimer) { clearInterval(_labTimer); _labTimer = null } }

async function labControl(world, source, action, speed) {
  const r = await apiFetch('/api/iot/lab', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ world, source, action, speed })
  })
  const d = await r.json().catch(() => ({}))
  if (!d.success && d.error) appendLog('error', 'Lab: ' + d.error)
  refreshLab()
}

function _labCard(s) {
  const speeds = (_LAB_SPEEDS[s.world] || []).map(([v, l]) =>
    `<button class="lab-speed ${Math.abs(s.speed - v) < 1e-6 ? 'on' : ''}" onclick="labControl('${s.world}', '${s.source}', 'speed', ${v})">${l}</button>`).join('')
  const body = s.world === 'greenhouse' ? _labGreenhouse(s) : s.world === 'rover' ? _labRover(s) : ''
  const events = (s.events || []).slice(-3).reverse().map(e => `<div>${_labEsc(e.text)}</div>`).join('')
  return `<div class="lab-card">
    <div class="lab-head"><strong>🧪 ${_labEsc(s.title)} lab</strong>
      ${s.source === 'backend' ? '<span class="lab-tag">backend</span>' : ''}
      <span class="lab-speeds">${speeds}</span>
      <button class="btn btn-sm" onclick="labControl('${s.world}', '${s.source}', 'reset')">Reset</button></div>
    ${body}
    ${events ? `<div class="lab-events">${events}</div>` : ''}
  </div>`
}

function _labStat(label, value, warn) {
  return `<div class="lab-stat ${warn ? 'warn' : ''}"><b>${_labEsc(value)}</b><span>${_labEsc(label)}</span></div>`
}

function _labGreenhouse(s) {
  const o = s.outputs || {}
  const sun = s.sun || 0
  const night = 1 - Math.min(1, sun * 2.2)
  const sky = `rgb(${Math.round(30 + 150 * (1 - night))}, ${Math.round(45 + 160 * (1 - night))}, ${Math.round(90 + 150 * (1 - night))})`
  // Sun or moon on an arc across the sky by the hour
  const h = s.hour || 0
  const dayT = Math.min(1, Math.max(0, (h - 6) / 12))
  const isDay = h >= 6 && h <= 18
  const t = isDay ? dayT : ((h + 6) % 24) / 12
  const bx = 20 + t * 280, by = 70 - Math.sin(t * Math.PI) * 50
  const soil = s.soil_moisture || 0
  const soilColor = `rgb(${Math.round(150 - soil)}, ${Math.round(105 - soil * 0.55)}, ${Math.round(70 - soil * 0.4)})`
  const health = (s.plant || 0) / 100
  const leaf = `rgb(${Math.round(190 - 150 * health)}, ${Math.round(150 + 40 * health)}, ${Math.round(60 - 20 * health)})`
  const plant = (x) => `<g transform="translate(${x},150)">
      <path d="M0 0 C0 -18 0 -30 0 -38" stroke="${leaf}" stroke-width="3" fill="none"/>
      <ellipse cx="-9" cy="-22" rx="10" ry="5" fill="${leaf}" transform="rotate(-25 -9 -22)"/>
      <ellipse cx="9" cy="-30" rx="10" ry="5" fill="${leaf}" transform="rotate(25 9 -30)"/>
      <circle cx="0" cy="-40" r="5" fill="${health > 0.5 ? '#f472b6' : leaf}"/></g>`
  const drops = o.pump ? [0, 1, 2, 3, 4].map(i => `<circle class="lab-drop" style="animation-delay:${i * 0.12}s" cx="${110 + i * 25}" cy="96" r="2.2" fill="#38bdf8"/>`).join('') : ''
  const vent = Math.min(180, Math.max(0, Number(o.vent) || 0))
  const svg = `<svg viewBox="0 0 320 190" class="lab-svg" role="img" aria-label="Greenhouse at ${_labEsc(s.time)}">
    <rect width="320" height="190" fill="${sky}"/>
    ${isDay ? `<circle cx="${bx}" cy="${by}" r="11" fill="#fde047"/>` : `<circle cx="${bx}" cy="${by}" r="8" fill="#e2e8f0"/><circle cx="${bx + 4}" cy="${by - 3}" r="7" fill="${sky}"/>`}
    <rect x="0" y="160" width="320" height="30" fill="#4d7c0f"/>
    <path d="M70 160 L70 95 L160 55 L250 95 L250 160 Z" fill="rgba(255,255,255,0.18)" stroke="#e2e8f0" stroke-width="2"/>
    <line x1="160" y1="55" x2="160" y2="160" stroke="rgba(226,232,240,.5)"/>
    <g transform="rotate(${-vent / 3} 205 75)"><rect x="185" y="73" width="40" height="5" rx="2" fill="#cbd5e1"/></g>
    ${o.grow_light ? '<rect x="95" y="92" width="130" height="5" rx="2" fill="#c084fc"/><path d="M95 97 L225 97 L240 150 L80 150 Z" fill="rgba(192,132,252,.18)"/>' : '<rect x="95" y="92" width="130" height="5" rx="2" fill="#64748b"/>'}
    <rect x="85" y="148" width="150" height="12" rx="3" fill="${soilColor}"/>
    ${plant(115)}${plant(160)}${plant(205)}
    ${drops}
    <g transform="translate(232 128)"><circle r="11" fill="#1e293b" opacity=".6"/>
      <g class="${o.fan ? 'lab-spin' : ''}"><path d="M0 0 L0 -9 A4 4 0 0 1 4 -2 Z M0 0 L8 5 A4 4 0 0 1 0 6 Z M0 0 L-8 4 A4 4 0 0 1 -4 -3 Z" fill="#e2e8f0"/></g></g>
    <text x="10" y="18" fill="#fff" font-size="12" font-weight="700">Day ${_labEsc(s.day)} · ${_labEsc(s.time)}</text>
  </svg>`
  return svg + `<div class="lab-stats">
    ${_labStat('soil', soil + '%', soil < 30 || soil > 75)}
    ${_labStat('temperature', s.temperature + '°C', s.temperature > 30 || s.temperature < 15)}
    ${_labStat('humidity', s.humidity + '%')}
    ${_labStat('light', s.light + ' lux')}
    ${_labStat('water used', s.water_used + ' L')}
    ${_labStat('plant health', s.plant + '%', s.plant < 50)}
  </div>`
}

function _labRover(s) {
  const k = 50                      // px per metre
  const W = s.width * k, H = s.height * k
  const o = s.outputs || {}
  const obstacles = (s.obstacles || []).map(([x, y, w, h]) =>
    `<rect x="${x * k}" y="${y * k}" width="${w * k}" height="${h * k}" rx="3" fill="#475569"/>`).join('')
  const [px, py, pr] = s.pad || [0, 0, 0]
  const trail = (s.trail || []).map(([x, y]) => `${(x * k).toFixed(1)},${(y * k).toFixed(1)}`).join(' ')
  const sensors = s.sensors || {}
  const rays = [['front_distance', 0], ['left_distance', -45], ['right_distance', 45]].map(([key, off]) => {
    const d = (sensors[key] || 0) / 100 * k
    const color = sensors[key] < 30 ? '#ef4444' : sensors[key] < 80 ? '#f59e0b' : '#22c55e'
    return `<line x1="8" y1="0" x2="${8 + d * Math.cos(off * Math.PI / 180)}" y2="${d * Math.sin(off * Math.PI / 180)}" stroke="${color}" stroke-width="1.5" stroke-dasharray="3 3" opacity=".9"/>`
  }).join('')
  const svg = `<svg viewBox="0 0 ${W} ${H}" class="lab-svg lab-room" role="img" aria-label="Rover in a room">
    <rect width="${W}" height="${H}" fill="#0f172a"/>
    ${[...Array(Math.floor(s.width))].map((_, i) => `<line x1="${(i + 1) * k}" y1="0" x2="${(i + 1) * k}" y2="${H}" stroke="#1e293b"/>`).join('')}
    ${[...Array(Math.floor(s.height))].map((_, i) => `<line x1="0" y1="${(i + 1) * k}" x2="${W}" y2="${(i + 1) * k}" stroke="#1e293b"/>`).join('')}
    <circle cx="${px * k}" cy="${py * k}" r="${pr * k}" fill="${s.reached ? 'rgba(34,197,94,.45)' : 'rgba(34,197,94,.18)'}" stroke="#22c55e" stroke-dasharray="4 3"/>
    <text x="${px * k}" y="${py * k + 4}" text-anchor="middle" font-size="10" fill="#86efac">⚡</text>
    ${obstacles}
    ${trail ? `<polyline points="${trail}" fill="none" stroke="#38bdf8" stroke-width="1.5" opacity=".5"/>` : ''}
    <g transform="translate(${s.x * k} ${s.y * k}) rotate(${s.heading})">
      ${rays}
      ${o.headlight ? '<path d="M8 0 L40 -14 L40 14 Z" fill="rgba(253,224,71,.25)"/>' : ''}
      <rect x="-9" y="-7" width="18" height="14" rx="3" fill="${s.bumper ? '#ef4444' : '#e2e8f0'}"/>
      <path d="M9 -5 L14 0 L9 5 Z" fill="${s.bumper ? '#ef4444' : '#38bdf8'}"/>
    </g>
  </svg>`
  return svg + `<div class="lab-stats">
    ${_labStat('front', sensors.front_distance + ' cm', sensors.front_distance < 30)}
    ${_labStat('left', sensors.left_distance + ' cm', sensors.left_distance < 30)}
    ${_labStat('right', sensors.right_distance + ' cm', sensors.right_distance < 30)}
    ${_labStat('drive', (o.drive || 0) + '%')}
    ${_labStat('steering', (o.steering ?? 90) + '°')}
    ${_labStat(s.reached ? 'reached the pad ✓' : 'travelled', s.distance_m + ' m', s.bumper)}
  </div>`
}


// ── Control policies: the STOP button, the emergency-stop banner and approvals ──

let _policyState = { stopped: false, pending: [] }

async function refreshPolicy() {
  const box = document.getElementById('iot-policy')
  if (!box) return
  try {
    const d = await (await apiFetch('/api/iot/policy')).json()
    if (!d.success) return
    _policyState = d
    const btn = document.getElementById('iot-stop-btn')
    if (btn) { btn.textContent = d.stopped ? 'Release' : 'STOP'; btn.classList.toggle('released', !!d.stopped) }
    const banner = d.stopped ? `<div class="iot-estop">⛔ Emergency stop is on. Every output is in its safe state and changes are refused.
        <button class="btn btn-sm" onclick="iotEmergencyStop(false)">Release</button></div>` : ''
    const approvals = (d.pending || []).map(p => `<div class="iot-approval">
        <div><b>${_labEsc(p.device)}</b> → ${_labEsc(p.value)} <span class="pane-sub">(now ${_labEsc(p.current)}, asked by ${_labEsc({code: 'the program', simulator: 'Studio'}[p.source] || p.source)}${p.origin === 'backend' ? ', backend' : ''})</span></div>
        <div class="iot-approval-actions">
          <button class="btn btn-primary btn-sm" onclick="iotApprove('${_labEsc(p.id)}', '${p.origin}', true)">Approve</button>
          <button class="btn btn-sm" onclick="iotApprove('${_labEsc(p.id)}', '${p.origin}', false)">Reject</button></div></div>`).join('')
    box.innerHTML = banner + (approvals ? `<div class="pane-label">Waiting for approval</div>${approvals}` : '')
  } catch (e) {}
}

async function iotEmergencyStop(on) {
  const stop = on === undefined ? !_policyState.stopped : on
  const r = await apiFetch('/api/iot/estop', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ on: stop })
  })
  const d = await r.json().catch(() => ({}))
  if (d.success) showToast(stop ? `Emergency stop: ${(d.made_safe || []).length} output(s) made safe` : 'Emergency stop released', stop ? 'warning' : 'success')
  refreshIoTSimulator()
}

async function iotApprove(id, origin, approve) {
  const r = await apiFetch('/api/iot/approval', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id, origin, approve })
  })
  const d = await r.json().catch(() => ({}))
  if (!d.success && d.error) appendLog('error', 'Approval: ' + d.error)
  refreshIoTSimulator()
}
