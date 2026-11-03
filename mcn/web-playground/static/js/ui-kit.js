// ── Desktop Environment Detection ──────────────────────────────────────────
(function checkDesktopEnvironment() {
  const isDesktop = !!(window.mcnDesktop || window.__MCN_DESKTOP__ || /Electron/i.test(navigator.userAgent));
  const isMac = /(Mac|iPhone|iPod|iPad)/i.test(navigator.platform || navigator.userAgent);
  if (isDesktop) {
    document.documentElement.classList.add('is-desktop');
    if (isMac) {
      document.documentElement.classList.add('is-mac-desktop');
    }
  }
})();

// ── Toast Notification System ───────────────────────────────────────────────
function showToast(message, type = 'info', duration = 3500) {
  const container = document.getElementById('toast-container')
  if (!container) return

  const toast = document.createElement('div')
  toast.className = `toast toast-${type}`
  
  const iconMap = {
    info: 'ℹ',
    success: '✓',
    warn: '⚠',
    error: '✕'
  }
  const titleMap = {
    info: 'Information',
    success: 'Success',
    warn: 'Warning',
    error: 'Error'
  }

  const icon = iconMap[type] || 'ℹ'
  const title = titleMap[type] || 'Notice'

  toast.innerHTML = `
    <div class="toast-icon-wrap">${icon}</div>
    <div class="toast-body">
      <div class="toast-title">${title}</div>
      <div class="toast-msg">${escapeHtml(message)}</div>
    </div>
    <button class="toast-close" title="Dismiss">&times;</button>
    <div class="toast-progress" style="animation-duration: ${duration}ms;"></div>
  `

  const closeBtn = toast.querySelector('.toast-close')
  let timer = null

  const removeToast = () => {
    if (timer) clearTimeout(timer)
    toast.classList.add('toast-out')
    setTimeout(() => {
      if (toast.parentNode) toast.parentNode.removeChild(toast)
    }, 250)
  }

  closeBtn.onclick = removeToast
  timer = setTimeout(removeToast, duration)

  container.appendChild(toast)
}

function escapeHtml(str) {
  if (!str) return ''
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;')
}

// ── Universal IDE Dialog System ─────────────────────────────────────────────
let _ideDialogResolver = null

function showIdeAlert(title, message, type = 'info') {
  return new Promise((resolve) => {
    _ideDialogResolver = () => resolve(true)
    
    const modal = document.getElementById('ide-dialog-modal')
    const iconEl = document.getElementById('ide-dialog-icon')
    const titleEl = document.getElementById('ide-dialog-title')
    const subEl = document.getElementById('ide-dialog-sub')
    const msgEl = document.getElementById('ide-dialog-message')
    const inputWrap = document.getElementById('ide-dialog-input-wrap')
    const cancelBtn = document.getElementById('ide-dialog-cancel')
    const confirmBtn = document.getElementById('ide-dialog-confirm')

    iconEl.className = `dialog-icon-circle dialog-icon-${type}`
    iconEl.textContent = type === 'success' ? '✓' : (type === 'warn' ? '⚠' : (type === 'error' || type === 'danger' ? '✕' : 'ℹ'))
    titleEl.textContent = title
    subEl.textContent = 'MCN Studio Dialog'
    msgEl.innerHTML = escapeHtml(message).replace(/\n/g, '<br/>')
    
    inputWrap.classList.add('hidden')
    cancelBtn.classList.add('hidden')
    confirmBtn.textContent = 'OK'
    confirmBtn.className = 'btn btn-primary'

    modal.classList.remove('hidden')
    confirmBtn.focus()
  })
}

function showIdeConfirm(title, message, options = {}) {
  return new Promise((resolve) => {
    _ideDialogResolver = (confirmed) => resolve(!!confirmed)

    const isDanger = options.danger || false
    const type = isDanger ? 'danger' : (options.type || 'info')
    const confirmText = options.confirmText || (isDanger ? 'Delete' : 'Confirm')
    const cancelText = options.cancelText || 'Cancel'

    const modal = document.getElementById('ide-dialog-modal')
    const iconEl = document.getElementById('ide-dialog-icon')
    const titleEl = document.getElementById('ide-dialog-title')
    const subEl = document.getElementById('ide-dialog-sub')
    const msgEl = document.getElementById('ide-dialog-message')
    const inputWrap = document.getElementById('ide-dialog-input-wrap')
    const cancelBtn = document.getElementById('ide-dialog-cancel')
    const confirmBtn = document.getElementById('ide-dialog-confirm')

    iconEl.className = `dialog-icon-circle dialog-icon-${type}`
    iconEl.textContent = isDanger ? '⚠' : '?'
    titleEl.textContent = title
    subEl.textContent = options.subtitle || 'Confirmation required'
    msgEl.innerHTML = escapeHtml(message).replace(/\n/g, '<br/>')

    inputWrap.classList.add('hidden')
    cancelBtn.classList.remove('hidden')
    cancelBtn.textContent = cancelText
    confirmBtn.textContent = confirmText
    confirmBtn.className = isDanger ? 'btn btn-danger' : 'btn btn-primary'

    modal.classList.remove('hidden')
    confirmBtn.focus()
  })
}

function showIdePrompt(title, message, defaultValue = '', placeholder = '', options = {}) {
  return new Promise((resolve) => {
    const modal = document.getElementById('ide-dialog-modal')
    const iconEl = document.getElementById('ide-dialog-icon')
    const titleEl = document.getElementById('ide-dialog-title')
    const subEl = document.getElementById('ide-dialog-sub')
    const msgEl = document.getElementById('ide-dialog-message')
    const inputWrap = document.getElementById('ide-dialog-input-wrap')
    const inputEl = document.getElementById('ide-dialog-input')
    const suggEl = document.getElementById('ide-dialog-suggestions')
    const cancelBtn = document.getElementById('ide-dialog-cancel')
    const confirmBtn = document.getElementById('ide-dialog-confirm')

    _ideDialogResolver = (confirmed) => {
      if (confirmed) {
        resolve(inputEl.value.trim())
      } else {
        resolve(null)
      }
    }

    iconEl.className = 'dialog-icon-circle dialog-icon-prompt'
    iconEl.textContent = '✏'
    titleEl.textContent = title
    subEl.textContent = options.subtitle || 'Enter value'
    msgEl.innerHTML = escapeHtml(message).replace(/\n/g, '<br/>')

    inputWrap.classList.remove('hidden')
    inputEl.value = defaultValue
    inputEl.placeholder = placeholder || 'Enter value...'

    // Suggestions chips
    if (options.suggestions && options.suggestions.length > 0) {
      suggEl.innerHTML = ''
      suggEl.classList.remove('hidden')
      options.suggestions.forEach(sug => {
        const chip = document.createElement('div')
        chip.className = 'dialog-chip'
        chip.textContent = sug
        chip.onclick = () => {
          inputEl.value = sug
          inputEl.focus()
        }
        suggEl.appendChild(chip)
      })
    } else {
      suggEl.classList.add('hidden')
    }

    cancelBtn.classList.remove('hidden')
    cancelBtn.textContent = options.cancelText || 'Cancel'
    confirmBtn.textContent = options.confirmText || 'Create'
    confirmBtn.className = 'btn btn-primary'

    modal.classList.remove('hidden')
    setTimeout(() => {
      inputEl.focus()
      inputEl.select()
    }, 50)
  })
}

function closeIdeDialog(confirmed) {
  const modal = document.getElementById('ide-dialog-modal')
  modal.classList.add('hidden')
  if (_ideDialogResolver) {
    const cb = _ideDialogResolver
    _ideDialogResolver = null
    cb(confirmed)
  }
}

// Dialog keyboard hotkeys (Enter / Escape)
document.addEventListener('keydown', (e) => {
  const modal = document.getElementById('ide-dialog-modal')
  if (!modal || modal.classList.contains('hidden')) return

  if (e.key === 'Enter') {
    e.preventDefault()
    closeIdeDialog(true)
  } else if (e.key === 'Escape') {
    e.preventDefault()
    closeIdeDialog(false)
  }
})

// ── AI Copilot & Agent Modal Helpers ────────────────────────────────────────
function switchAgentMode(mode) {
  const modeVal = document.getElementById('agent-mode-val')
  if (modeVal) modeVal.value = mode
  const btnMcn = document.getElementById('agent-mode-mcn')
  const btnCompiled = document.getElementById('agent-mode-compiled')
  if (btnMcn) btnMcn.classList.toggle('active', mode === 'mcn')
  if (btnCompiled) btnCompiled.classList.toggle('active', mode === 'compiled')
}

function setAgentPreset(mode, promptText) {
  switchAgentMode(mode)
  const promptEl = document.getElementById('agent-prompt')
  if (promptEl) {
    promptEl.value = promptText
    promptEl.focus()
  }
}

function switchBackendMode(mode) {
  const modeVal = document.getElementById('backend-mode-val')
  if (modeVal) modeVal.value = mode
  const btnEnhance = document.getElementById('backend-mode-enhance')
  const btnScratch = document.getElementById('backend-mode-scratch')
  if (btnEnhance) btnEnhance.classList.toggle('active', mode === 'backend')
  if (btnScratch) btnScratch.classList.toggle('active', mode === 'generate_backend')
}

function setBackendPreset(mode, promptText) {
  switchBackendMode(mode)
  const promptEl = document.getElementById('backend-prompt')
  if (promptEl) {
    promptEl.value = promptText
    promptEl.focus()
  }
}

function setGenPreset(promptText) {
  const descEl = document.getElementById('gen-desc')
  if (descEl) {
    descEl.value = promptText
    descEl.focus()
  }
}

