// ── Community Registration & Feedback System ──────────────────────────────────
let _communityRegistered = false;
let _communityProfile = null;

async function checkCommunityStatus() {
  try {
    const r = await fetch('/api/telemetry/status');
    const d = await r.json();
    _communityRegistered = !!d.registered;
    _communityProfile = d.user || null;
    _updateCommunityUI();
  } catch (e) {
    _communityRegistered = false;
  }
}

function _updateCommunityUI() {
  const regBtn = document.getElementById('btn-register');
  const badgeEl = document.getElementById('registered-badge');
  if (regBtn && badgeEl) {
    if (_communityRegistered) {
      regBtn.style.display = 'none';
      badgeEl.style.display = 'inline-flex';
      const name = _communityProfile?.name || _communityProfile?.email || 'Registered';
      badgeEl.title = `Registered Community Member: ${name} (Click to manage profile)`;
    } else {
      regBtn.style.display = 'inline-flex';
      badgeEl.style.display = 'none';
    }
  }
}

let _commTab = 'register';

function switchCommunityTab(tab) {
  _commTab = tab;
  const regTab = document.getElementById('comm-tab-register');
  const feedTab = document.getElementById('comm-tab-feedback');
  const regBody = document.getElementById('comm-body-register');
  const feedBody = document.getElementById('comm-body-feedback');

  if (tab === 'register') {
    regTab.style.color = 'var(--accent)';
    regTab.style.borderBottomColor = 'var(--accent)';
    feedTab.style.color = 'var(--muted)';
    feedTab.style.borderBottomColor = 'transparent';
    regBody.style.display = 'flex';
    feedBody.style.display = 'none';
  } else {
    regTab.style.color = 'var(--muted)';
    regTab.style.borderBottomColor = 'transparent';
    feedTab.style.color = 'var(--accent)';
    feedTab.style.borderBottomColor = 'var(--accent)';
    regBody.style.display = 'none';
    feedBody.style.display = 'flex';
  }
}

function openCommunityModal(initialTab = 'register') {
  document.getElementById('community-modal').classList.remove('hidden');
  if (_communityProfile && _communityProfile.email) {
    document.getElementById('comm-reg-email').value = _communityProfile.email || '';
    document.getElementById('comm-reg-name').value = _communityProfile.name || '';
    document.getElementById('comm-reg-org').value = _communityProfile.organization || '';
  }
  switchCommunityTab(initialTab);
}

function openFeedbackModal() {
  openCommunityModal('feedback');
  setTimeout(() => document.getElementById('comm-feed-msg').focus(), 50);
}

function closeCommunityModal() {
  document.getElementById('community-modal').classList.add('hidden');
}

async function submitCommunityRegistration() {
  const email = document.getElementById('comm-reg-email').value.trim();
  const name = document.getElementById('comm-reg-name').value.trim();
  const organization = document.getElementById('comm-reg-org').value.trim();
  const optin = document.getElementById('comm-reg-optin').checked;
  const msgEl = document.getElementById('comm-reg-msg');
  const btn = document.getElementById('btn-comm-reg-submit');

  if (!email || !email.includes('@')) {
    msgEl.style.display = '';
    msgEl.style.background = '#fef2f2';
    msgEl.style.color = '#dc2626';
    msgEl.textContent = 'Please enter a valid email address.';
    return;
  }

  btn.disabled = true;
  btn.textContent = 'Registering…';
  msgEl.style.display = 'none';

  try {
    const isDesktop = !!(window.mcnDesktop || window.__MCN_DESKTOP__);
    const r = await fetch('/api/telemetry/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email,
        name,
        organization,
        newsletter_opt_in: optin,
        platform: isDesktop ? 'desktop_mac' : 'web',
        app_version: '3.0.0'
      })
    });
    const d = await r.json();
    if (!r.ok || d.error) throw new Error(d.error || 'Registration failed');

    _communityRegistered = true;
    _communityProfile = d.profile;
    _updateCommunityUI();

    msgEl.style.display = '';
    msgEl.style.background = '#f0fdf4';
    msgEl.style.color = '#16a34a';
    msgEl.textContent = '✓ ' + (d.message || 'Registration complete.');

    setTimeout(() => {
      closeCommunityModal();
      msgEl.style.display = 'none';
      appendLog('info', `✓ Registered installation as ${email}`);
    }, 1200);
  } catch (e) {
    msgEl.style.display = '';
    msgEl.style.background = '#fef2f2';
    msgEl.style.color = '#dc2626';
    msgEl.textContent = e.message;
  } finally {
    btn.disabled = false;
    btn.textContent = 'Register Installation';
  }
}

async function submitCommunityFeedback() {
  const type = document.getElementById('comm-feed-type').value;
  const subject = document.getElementById('comm-feed-subject').value.trim();
  const message = document.getElementById('comm-feed-msg').value.trim();
  const attachLogs = document.getElementById('comm-feed-logs').checked;
  const statusEl = document.getElementById('comm-feed-status');
  const btn = document.getElementById('btn-comm-feed-submit');

  if (!message) {
    statusEl.style.display = '';
    statusEl.style.background = '#fef2f2';
    statusEl.style.color = '#dc2626';
    statusEl.textContent = 'Please enter a description or message.';
    return;
  }

  btn.disabled = true;
  btn.textContent = 'Submitting…';
  statusEl.style.display = 'none';

  let logs = '';
  if (attachLogs) {
    const termEl = document.getElementById('output-log');
    if (termEl) logs = termEl.innerText.slice(-2000);
  }

  try {
    const isDesktop = !!(window.mcnDesktop || window.__MCN_DESKTOP__);
    const r = await fetch('/api/telemetry/feedback', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        feedback_type: type,
        subject,
        message,
        error_logs: logs,
        platform: isDesktop ? 'desktop_mac' : 'web',
        app_version: '3.0.0'
      })
    });
    const d = await r.json();
    if (!r.ok || d.error) throw new Error(d.error || 'Submission failed');

    statusEl.style.display = '';
    statusEl.style.background = '#f0fdf4';
    statusEl.style.color = '#16a34a';
    statusEl.textContent = '✓ ' + d.message;

    setTimeout(() => {
      closeCommunityModal();
      document.getElementById('comm-feed-msg').value = '';
      document.getElementById('comm-feed-subject').value = '';
      statusEl.style.display = 'none';
      appendLog('info', d.delivered ? `✓ Feedback (${type}) sent to the MCN team` : `✓ Feedback (${type}) saved locally (not sent: no reachable feedback endpoint)`);
    }, 1200);
  } catch (e) {
    statusEl.style.display = '';
    statusEl.style.background = '#fef2f2';
    statusEl.style.color = '#dc2626';
    statusEl.textContent = e.message;
  } finally {
    btn.disabled = false;
    btn.textContent = 'Submit Feedback';
  }
}

document.getElementById('community-modal').addEventListener('click', function(e) {
  if (e.target === this) closeCommunityModal();
});

// Check community status on load
checkCommunityStatus();

