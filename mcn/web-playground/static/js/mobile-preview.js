// ── Mobile preview ──────────────────────────────────────────────────────────
// The App view's phone frame shows the real app: the Flutter project generated
// from ui/app.mcn, built for the web (when Flutter is installed), or the same
// components rendered at phone size (when it isn't).

let _currentExample = null
let _mobileRoute = 'home'
let _mobileBuilding = false

function _mobileStatus(text, { spinner = false, button = false } = {}) {
  document.getElementById('mobile-preview-frame').hidden = true
  const box = document.getElementById('mobile-preview-status')
  box.style.display = 'flex'
  document.getElementById('mobile-preview-text').innerHTML = text
  document.getElementById('mobile-preview-spinner').hidden = !spinner
  document.getElementById('mobile-preview-build').hidden = !button
}

function _mobileShow(url, note) {
  const frame = document.getElementById('mobile-preview-frame')
  if (frame) {
    frame.src = url
    frame.hidden = false
  }
  const status = document.getElementById('mobile-preview-status')
  if (status) status.style.display = 'none'
  const noteEl = document.getElementById('mobile-preview-note')
  if (noteEl) {
    noteEl.hidden = !note
    noteEl.textContent = note || ''
  }
}

function openMobilePreviewFullscreen() {
  const frame = document.getElementById('mobile-preview-frame')
  if (frame && frame.src && frame.src !== 'about:blank' && !frame.hidden) {
    window.open(frame.src, '_blank')
  } else {
    window.open('/preview-mobile/', '_blank')
  }
}

// Called when the App view opens (build = false: show what's there) or on App Preview / ↺ (build = true)
async function renderFlutterSimulator(build = false) {
  if (!build) {
    const frame = document.getElementById('mobile-preview-frame')
    if (frame && !frame.hidden) return
    if (!_mobileBuilding) _mobileStatus('Press <b style="color:#E2E8F0;">App Preview</b> to build the Flutter app from <code>ui/app.mcn</code> and run it here.', { button: true })
    return
  }
  if (_mobileBuilding) return
  _mobileBuilding = true
  _mobileStatus('Generating the Flutter app…', { spinner: true })
  try {
    if (typeof saveAllTabs === 'function') await saveAllTabs()
    const start = await (await apiFetch('/api/mobile/preview', { method: 'POST' })).json()
    if (!start.success) throw new Error(start.error)
    if (typeof loadFileTree === 'function') loadFileTree()
    if (start.mode === 'web') {
      _mobileShow(start.url, start.note)
      return
    }
    let job = start
    while (job.state === 'running') {
      _mobileStatus(escapeHtml(job.step || 'Building the Flutter app…'), { spinner: true })
      await new Promise(r => setTimeout(r, 1500))
      job = await (await apiFetch('/api/mobile/preview')).json()
    }
    if (job.state !== 'done') throw new Error(job.error || 'The Flutter build failed')
    _mobileShow(job.url, 'Your Flutter app, built for the web and talking to your backend. Export it to run on Android and iOS.')
    if (typeof appendLog === 'function') appendLog('success', 'Flutter app built and running in the phone preview')
  } catch (e) {
    _mobileStatus(`<span style="color:#F87171;">${escapeHtml(e.message).replace(/\n/g, '<br>')}</span>`, { button: true })
    if (typeof appendLog === 'function') appendLog('error', 'App preview: ' + e.message)
  } finally {
    _mobileBuilding = false
  }
}
