// ── Design panel: brand colour, font, corners, buttons and mode for the app ──
// Each choice is one line in ui/app.mcn's app block (brand "violet", font "Poppins", ...),
// so the code stays the source of truth; the preview reloads as soon as it's written.

const _DESIGN_SWATCHES = [
  ['violet', '#7c3aed'], ['indigo', '#4f46e5'], ['blue', '#2563eb'], ['sky', '#0284c7'], ['teal', '#0d9488'],
  ['emerald', '#059669'], ['green', '#16a34a'], ['amber', '#d97706'], ['orange', '#ea580c'], ['rose', '#e11d48'],
  ['pink', '#db2777'], ['slate', '#334155'], ['black', '#111111'],
]
let _design = null
let _designOpts = null

async function toggleDesignPanel() {
  const box = document.getElementById('design-panel')
  if (!box) return
  const open = box.classList.toggle('open')
  document.getElementById('btn-design')?.classList.toggle('on', open)
  if (open) await loadDesign()
}

async function loadDesign() {
  const d = await (await apiFetch('/api/design')).json().catch(() => ({}))
  if (!d.success) return
  _design = d.design
  _designOpts = d
  renderDesign()
}

function _designSeg(key, values) {
  return `<div class="dz-seg">${values.map(v => `<button class="${(_design[key] || '') === v ? 'on' : ''}" onclick="setDesign('${key}', '${v}')">${v[0].toUpperCase() + v.slice(1)}</button>`).join('')}</div>`
}

function renderDesign() {
  const box = document.getElementById('design-panel')
  if (!box || !_design) return
  if (!_designOpts.has_app) {
    box.innerHTML = '<div class="dz-note">Add an <code>app</code> block to <code>ui/app.mcn</code> to set its design.</div>'
    return
  }
  const brand = (_design.brand || '').toLowerCase()
  const custom = brand.startsWith('#') ? brand : (_DESIGN_SWATCHES.find(([n]) => n === brand) || [, '#7c3aed'])[1]
  box.innerHTML = `
    <div class="dz-row"><label>Brand colour</label>
      <div class="dz-swatches">
        ${_DESIGN_SWATCHES.map(([name, hex]) => `<button class="dz-swatch ${brand === name || (!brand && name === 'violet') ? 'on' : ''}" title="${name}" style="background:${hex}" onclick="setDesign('brand', '${name}')"></button>`).join('')}
        <label class="dz-custom" title="Any colour"><input type="color" value="${custom}" onchange="setDesign('brand', this.value)">Custom</label>
      </div></div>
    <div class="dz-row"><label>Font</label>
      <select onchange="setDesign('font', this.value)">${_designOpts.fonts.map(f => `<option ${_design.font === f ? 'selected' : ''}>${f}</option>`).join('')}</select></div>
    <div class="dz-row"><label>Corners</label>${_designSeg('corners', _designOpts.corners)}</div>
    <div class="dz-row"><label>Buttons</label>${_designSeg('buttons', _designOpts.buttons)}</div>
    <div class="dz-row"><label>Mode</label>${_designSeg('mode', _designOpts.modes)}</div>
    <div class="dz-head">Phone app</div>
    <div class="dz-row"><label>Navigation</label>${_designSeg('navbar', _designOpts.mobile.navbar)}</div>
    <div class="dz-row"><label>Header</label>${_designSeg('header', _designOpts.mobile.header)}</div>
    <div class="dz-row"><label>Cards</label>${_designSeg('cards', _designOpts.mobile.cards)}</div>
    <div class="dz-row"><label>Toasts</label>${_designSeg('toasts', _designOpts.mobile.toasts)}</div>
    <div class="dz-note">Saved as code in <code>ui/app.mcn</code>: <code>${_designLines()}</code></div>`
}

function _designLines() {
  const out = []
  if (_design.brand) out.push(`brand "${_design.brand}"`)
  if (_design.font && _design.font !== 'Inter') out.push(`font "${_design.font}"`)
  if (_design.corners !== 'round') out.push(`corners "${_design.corners}"`)
  if (_design.buttons !== 'rounded') out.push(`buttons "${_design.buttons}"`)
  if (_design.mode !== 'auto') out.push(`mode "${_design.mode}"`)
  for (const [key, values] of Object.entries((_designOpts && _designOpts.mobile) || {}))
    if (_design[key] && _design[key] !== values[0]) out.push(`${key} "${_design[key]}"`)
  return escapeHtml(out.join(' · ') || 'the defaults')
}

async function setDesign(key, value) {
  const r = await apiFetch('/api/design', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ [key]: value })
  })
  const d = await r.json().catch(() => ({}))
  if (!d.success) { showToast(d.error || 'Could not save the design', 'error'); return }
  _design = d.design
  renderDesign()
  // Keep the editor in step with the file, without marking it as having unsaved changes
  const path = 'ui/app.mcn'
  if (typeof _models !== 'undefined' && _models.has(path)) {
    _models.get(path).setValue(d.content)
    if (_tabState.has(path)) _tabState.get(path).dirty = false
    if (typeof renderTabs === 'function') renderTabs()
  }
  // A mode chosen here should show in the preview, not the last one picked in the app
  if (key === 'mode') { try { localStorage.removeItem('mcn-theme') } catch (e) {} }
  _reloadLivePreview()
  // The phone app is compiled: rebuild its preview if one is showing (the web preview updates at once)
  const phone = document.getElementById('mobile-preview-frame')
  if (phone && !phone.hidden && phone.src && typeof renderFlutterSimulator === 'function') {
    showToast('Rebuilding the phone preview with the new design…', 'info')
    renderFlutterSimulator(true)
  }
}

function _reloadLivePreview() {
  const iframe = document.getElementById('preview-iframe')
  if (!iframe || iframe.classList.contains('hidden') || !iframe.src || iframe.src === 'about:blank') return
  try { iframe.contentWindow.localStorage.removeItem('mcn-theme') } catch (e) {}
  const url = iframe.src.split('?')[0]
  iframe.src = url + '?t=' + Date.now()
}
