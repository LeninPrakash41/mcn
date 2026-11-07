// ── MCN Studio Admin Console ──────────────────────────────────────────────────
let _adminToken = localStorage.getItem('mcn_admin_token') || localStorage.getItem('mcn_token') || '';
let _adminProfile = null;
try {
  _adminProfile = JSON.parse(localStorage.getItem('mcn_admin_profile') || 'null');
} catch (e) {}

function openAdminModal() {
  const modal = document.getElementById('admin-modal');
  if (!modal) return;
  modal.classList.remove('hidden');
  _checkAdminAuthAndRender();
}

function closeAdminModal() {
  const modal = document.getElementById('admin-modal');
  if (modal) modal.classList.add('hidden');
}

function switchAdminTab(tab) {
  const tabs = ['overview', 'users', 'feedback', 'broadcast'];
  tabs.forEach(t => {
    const btn = document.getElementById(`admin-tab-${t}`);
    const body = document.getElementById(`admin-body-${t}`);
    if (btn) {
      if (t === tab) {
        btn.style.color = 'var(--accent)';
        btn.style.borderBottomColor = 'var(--accent)';
      } else {
        btn.style.color = 'var(--muted)';
        btn.style.borderBottomColor = 'transparent';
      }
    }
    if (body) {
      body.style.display = (t === tab) ? 'flex' : 'none';
    }
  });

  if (tab === 'overview') loadAdminOverview();
  if (tab === 'users') loadAdminUsers();
  if (tab === 'feedback') loadAdminFeedback();
  if (tab === 'broadcast') loadAdminBroadcasts();
}

function _adminHeaders() {
  const t = _adminToken || localStorage.getItem('mcn_token') || '';
  return t ? { 'Authorization': `Bearer ${t}`, 'Content-Type': 'application/json' } : { 'Content-Type': 'application/json' };
}

async function _checkAdminAuthAndRender() {
  const loginCard = document.getElementById('admin-login-view');
  const mainCard = document.getElementById('admin-main-view');

  // Attempt to probe admin status
  try {
    const res = await fetch('/api/admin/overview', { headers: _adminHeaders() });
    if (res.ok) {
      if (loginCard) loginCard.style.display = 'none';
      if (mainCard) mainCard.style.display = 'block';
      switchAdminTab('overview');
      return;
    }
  } catch (e) {}

  if (loginCard) loginCard.style.display = 'flex';
  if (mainCard) mainCard.style.display = 'none';
}

async function submitAdminLogin() {
  const emailInput = document.getElementById('admin-login-email');
  const passInput = document.getElementById('admin-login-password');
  const msgEl = document.getElementById('admin-login-msg');
  const btn = document.getElementById('btn-admin-login');

  const email = (emailInput?.value || '').trim();
  const password = (passInput?.value || '').trim();

  if (!email || !password) {
    if (msgEl) {
      msgEl.style.display = '';
      msgEl.style.background = '#fef2f2';
      msgEl.style.color = '#dc2626';
      msgEl.textContent = 'Please enter both admin email and password.';
    }
    return;
  }

  if (btn) {
    btn.disabled = true;
    btn.textContent = 'Signing in…';
  }

  try {
    const res = await fetch('/api/admin/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    const d = await res.json();
    if (!res.ok || !d.success) {
      throw new Error(d.error || 'Invalid admin credentials');
    }

    _adminToken = d.token;
    _adminProfile = d.user;
    localStorage.setItem('mcn_admin_token', d.token);
    localStorage.setItem('mcn_admin_profile', JSON.stringify(d.user));

    if (msgEl) msgEl.style.display = 'none';
    const loginCard = document.getElementById('admin-login-view');
    const mainCard = document.getElementById('admin-main-view');
    if (loginCard) loginCard.style.display = 'none';
    if (mainCard) mainCard.style.display = 'block';

    switchAdminTab('overview');
  } catch (err) {
    if (msgEl) {
      msgEl.style.display = '';
      msgEl.style.background = '#fef2f2';
      msgEl.style.color = '#dc2626';
      msgEl.textContent = err.message || 'Login failed';
    }
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = 'Sign In to Console';
    }
  }
}

function adminLogout() {
  _adminToken = '';
  _adminProfile = null;
  localStorage.removeItem('mcn_admin_token');
  localStorage.removeItem('mcn_admin_profile');
  _checkAdminAuthAndRender();
}

async function loadAdminOverview() {
  try {
    const res = await fetch('/api/admin/overview', { headers: _adminHeaders() });
    const d = await res.json();
    if (!res.ok) throw new Error(d.error || 'Failed to fetch overview');

    const m = d.metrics || {};
    document.getElementById('adm-stat-users').textContent = m.total_users ?? 0;
    document.getElementById('adm-stat-admins').textContent = m.admin_users ?? 0;
    document.getElementById('adm-stat-workspaces').textContent = m.isolated_workspaces ?? 0;
    document.getElementById('adm-stat-optins').textContent = m.opt_in_subscribers ?? 0;
    document.getElementById('adm-stat-feedback').textContent = m.total_feedback ?? 0;

    // Load health details
    const healthRes = await fetch('/api/admin/health', { headers: _adminHeaders() });
    const hd = await healthRes.json();
    const hEl = document.getElementById('adm-health-details');
    if (hEl && hd.health) {
      const h = hd.health;
      hEl.innerHTML = `
        <div style="font-family:var(--font-mono);font-size:11.5px;color:var(--text);line-height:1.7;">
          <div><b>Status:</b> <span style="color:#10b981;">Operational</span></div>
          <div><b>Platform:</b> ${h.platform} (Python ${d.system?.python_version || '3.x'})</div>
          <div><b>Auth DB:</b> ${h.auth_db?.path} (${h.auth_db?.size_bytes} bytes)</div>
          <div><b>Workspaces Root:</b> ${h.workspaces_dir?.path}</div>
          <div><b>Outbox Diagnostics:</b> ${h.outbox_file?.size_bytes} bytes queued</div>
        </div>
      `;
    }
  } catch (e) {
    console.error('Failed to load overview:', e);
  }
}

async function loadAdminUsers() {
  const tbody = document.getElementById('adm-users-table');
  if (!tbody) return;
  tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;padding:16px;color:var(--muted);">Loading users…</td></tr>';

  try {
    const res = await fetch('/api/admin/users', { headers: _adminHeaders() });
    const d = await res.json();
    if (!res.ok) throw new Error(d.error || 'Failed to fetch users');

    const users = d.users || [];
    if (users.length === 0) {
      tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;padding:16px;color:var(--muted);">No users found.</td></tr>';
      return;
    }

    tbody.innerHTML = users.map(u => {
      const isAdmin = (u.roles || []).includes('admin');
      const actionLabel = isAdmin ? 'Revoke Admin' : 'Make Admin';
      const actionType = isAdmin ? 'revoke' : 'assign';
      return `
        <tr style="border-bottom:1px solid var(--border);">
          <td style="padding:10px 12px;font-size:12.5px;font-weight:600;color:var(--text);">${u.email}</td>
          <td style="padding:10px 12px;font-size:12px;">
            <span style="display:inline-block;padding:2px 8px;border-radius:12px;font-size:11px;font-weight:600;background:${isAdmin ? '#e0e7ff;color:#3730a3;' : 'var(--bg-card);color:var(--muted);'}">
              ${(u.roles || []).join(', ') || 'user'}
            </span>
          </td>
          <td style="padding:10px 12px;font-size:11.5px;color:var(--muted);font-family:var(--font-mono);">${u.has_workspace ? 'Active Workspace' : 'None'}</td>
          <td style="padding:10px 12px;text-align:right;">
            <button class="btn btn-secondary" style="font-size:11px;padding:4px 8px;" onclick="toggleUserRole('${u.id}', '${actionType}')">${actionLabel}</button>
          </td>
        </tr>
      `;
    }).join('');
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="4" style="text-align:center;padding:16px;color:#dc2626;">Error: ${e.message}</td></tr>`;
  }
}

async function toggleUserRole(userId, action) {
  try {
    const res = await fetch('/api/admin/users/role', {
      method: 'POST',
      headers: _adminHeaders(),
      body: JSON.stringify({ user_id: userId, role: 'admin', action: action }),
    });
    if (res.ok) {
      loadAdminUsers();
      loadAdminOverview();
    }
  } catch (e) {
    alert('Failed to update user role: ' + e.message);
  }
}

async function loadAdminFeedback() {
  const container = document.getElementById('adm-feedback-list');
  if (!container) return;
  container.innerHTML = '<div style="text-align:center;padding:20px;color:var(--muted);">Loading feedback submissions…</div>';

  try {
    const res = await fetch('/api/admin/feedback', { headers: _adminHeaders() });
    const d = await res.json();
    if (!res.ok) throw new Error(d.error || 'Failed to fetch feedback');

    const feedback = d.feedback || [];
    if (feedback.length === 0) {
      container.innerHTML = '<div style="text-align:center;padding:24px;color:var(--muted);">No feedback or bug reports submitted yet.</div>';
      return;
    }

    container.innerHTML = feedback.map(item => `
      <div style="background:var(--bg-card);border:1px solid var(--border);border-radius:8px;padding:14px;margin-bottom:10px;">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px;">
          <div style="font-size:13px;font-weight:700;color:var(--text);">${item.subject || 'Untitled'}</div>
          <span style="font-size:11px;padding:2px 8px;border-radius:10px;font-weight:600;background:var(--bg-deep);color:var(--accent);">${item.feedback_type || 'feedback'}</span>
        </div>
        <div style="font-size:12.5px;color:var(--text);white-space:pre-wrap;line-height:1.5;margin-bottom:8px;">${item.message}</div>
        <div style="display:flex;align-items:center;justify-content:space-between;font-size:11.5px;color:var(--muted);border-top:1px solid var(--border);padding-top:6px;">
          <span>From: <b>${item.email || 'Anonymous'}</b></span>
          <span>${item.created_at ? new Date(item.created_at).toLocaleString() : ''}</span>
        </div>
      </div>
    `).join('');
  } catch (e) {
    container.innerHTML = `<div style="text-align:center;padding:20px;color:#dc2626;">Error: ${e.message}</div>`;
  }
}

async function loadAdminBroadcasts() {
  const listEl = document.getElementById('adm-broadcast-history');
  if (!listEl) return;

  try {
    const res = await fetch('/api/admin/broadcasts', { headers: _adminHeaders() });
    const d = await res.json();
    if (!res.ok) throw new Error(d.error);

    const bcs = d.broadcasts || [];
    if (bcs.length === 0) {
      listEl.innerHTML = '<div style="text-align:center;padding:16px;color:var(--muted);font-size:12px;">No broadcasts sent yet.</div>';
      return;
    }

    listEl.innerHTML = bcs.map(b => `
      <div style="padding:10px 12px;border:1px solid var(--border);border-radius:6px;margin-bottom:8px;background:var(--bg-card);">
        <div style="display:flex;justify-content:space-between;font-size:12.5px;font-weight:600;color:var(--text);">
          <span>${b.title}</span>
          <span style="font-size:11px;color:#10b981;font-weight:600;">Dispatched (${b.recipients_count} recipients)</span>
        </div>
        <div style="font-size:12px;color:var(--muted);margin-top:4px;">${b.content}</div>
        <div style="font-size:10.5px;color:var(--muted);margin-top:6px;">${new Date(b.created_at).toLocaleString()} by ${b.sent_by}</div>
      </div>
    `).join('');
  } catch (e) {
    listEl.innerHTML = `<div style="color:#dc2626;font-size:12px;">Failed to load history: ${e.message}</div>`;
  }
}

async function submitAdminBroadcast() {
  const titleInput = document.getElementById('adm-bc-title');
  const msgInput = document.getElementById('adm-bc-msg');
  const catInput = document.getElementById('adm-bc-category');
  const statusEl = document.getElementById('adm-bc-status');
  const btn = document.getElementById('btn-admin-broadcast');

  const title = (titleInput?.value || '').trim();
  const content = (msgInput?.value || '').trim();
  const category = catInput?.value || 'release_update';

  if (!title || !content) {
    if (statusEl) {
      statusEl.style.display = '';
      statusEl.style.background = '#fef2f2';
      statusEl.style.color = '#dc2626';
      statusEl.textContent = 'Please enter both broadcast title and update details.';
    }
    return;
  }

  if (btn) {
    btn.disabled = true;
    btn.textContent = 'Dispatching…';
  }

  try {
    const res = await fetch('/api/admin/broadcast', {
      method: 'POST',
      headers: _adminHeaders(),
      body: JSON.stringify({ title, content, category }),
    });
    const d = await res.json();
    if (!res.ok || !d.success) throw new Error(d.error || 'Failed to dispatch broadcast');

    if (statusEl) {
      statusEl.style.display = '';
      statusEl.style.background = '#f0fdf4';
      statusEl.style.color = '#15803d';
      statusEl.textContent = d.message || 'Broadcast successfully dispatched!';
    }
    if (titleInput) titleInput.value = '';
    if (msgInput) msgInput.value = '';
    loadAdminBroadcasts();
  } catch (e) {
    if (statusEl) {
      statusEl.style.display = '';
      statusEl.style.background = '#fef2f2';
      statusEl.style.color = '#dc2626';
      statusEl.textContent = e.message || 'Dispatch failed';
    }
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = 'Dispatch Update to Subscribers';
    }
  }
}

// ── Full-Screen Studio Admin & Metrics Dashboard View ────────────────────────
let _studioAdminOpen = false;

function toggleStudioAdminView(show) {
  const fsView = document.getElementById('studio-admin-fullscreen');
  const adminBtn = document.getElementById('ws-admin-page');
  if (show === undefined) {
    _studioAdminOpen = !_studioAdminOpen;
  } else {
    _studioAdminOpen = !!show;
  }

  if (fsView) {
    fsView.style.display = _studioAdminOpen ? 'block' : 'none';
  }
  if (adminBtn) {
    adminBtn.classList.toggle('active', _studioAdminOpen);
  }

  if (_studioAdminOpen) {
    loadStudioAdminMetrics();
  }
}

async function loadStudioAdminMetrics() {
  try {
    const res = await fetch('/api/admin/overview', { headers: _adminHeaders() });
    if (!res.ok) {
      // If unauthorized, prompt login modal
      openAdminModal();
      return;
    }
    const d = await res.json();
    const m = d.metrics || {};

    const elUsers = document.getElementById('fs-stat-users');
    const elAdmins = document.getElementById('fs-stat-admins');
    const elWs = document.getElementById('fs-stat-workspaces');
    const elOptins = document.getElementById('fs-stat-optins');
    const elFb = document.getElementById('fs-stat-feedback');

    if (elUsers) elUsers.textContent = m.total_users ?? 0;
    if (elAdmins) elAdmins.textContent = m.admin_users ?? 0;
    if (elWs) elWs.textContent = m.isolated_workspaces ?? 0;
    if (elOptins) elOptins.textContent = m.opt_in_subscribers ?? 0;
    if (elFb) elFb.textContent = m.total_feedback ?? 0;

    const healthRes = await fetch('/api/admin/health', { headers: _adminHeaders() });
    const hd = await healthRes.json();
    const h = hd.health || {};
    const healthEl = document.getElementById('fs-health-content');
    if (healthEl) {
      healthEl.innerHTML = `
        <div><b>Status:</b> <span style="color:#10b981;">Operational</span></div>
        <div><b>Platform:</b> ${h.platform} (Python ${d.system?.python_version || '3.x'})</div>
        <div><b>Database:</b> ${h.auth_db?.path} (${h.auth_db?.size_bytes} bytes)</div>
        <div><b>Multi-Tenant Root:</b> ${h.workspaces_dir?.path}</div>
        <div><b>Telemetry Outbox:</b> ${h.outbox_file?.size_bytes} bytes</div>
        <div><b>Checked:</b> ${h.timestamp}</div>
      `;
    }

    // Load users table
    const usersRes = await fetch('/api/admin/users', { headers: _adminHeaders() });
    const ud = await usersRes.json();
    const tbody = document.getElementById('fs-users-table');
    if (tbody && ud.users) {
      tbody.innerHTML = ud.users.map(u => {
        const isAdmin = (u.roles || []).includes('admin');
        return `
          <tr style="border-bottom:1px solid var(--border);">
            <td style="padding:10px 12px;font-size:12.5px;font-weight:600;color:var(--text);">${u.email}</td>
            <td style="padding:10px 12px;font-size:12px;">
              <span style="display:inline-block;padding:2px 8px;border-radius:12px;font-size:11px;font-weight:600;background:${isAdmin ? '#e0e7ff;color:#3730a3;' : 'var(--bg-card);color:var(--muted);'}">
                ${isAdmin ? 'admin' : 'user'}
              </span>
            </td>
            <td style="padding:10px 12px;font-size:11.5px;color:var(--muted);font-family:var(--font-mono);">${u.workspace_path}</td>
            <td style="padding:10px 12px;text-align:right;">
              <button class="btn btn-secondary" style="font-size:11px;padding:3px 8px;" onclick="toggleUserRole('${u.id}', '${isAdmin ? 'revoke' : 'assign'}'); setTimeout(loadStudioAdminMetrics, 300);">
                ${isAdmin ? 'Revoke Admin' : 'Make Admin'}
              </button>
            </td>
          </tr>
        `;
      }).join('');
    }
  } catch (e) {
    console.error('Failed to load studio metrics:', e);
  }
}

async function submitStudioBroadcast() {
  const title = (document.getElementById('fs-bc-title')?.value || '').trim();
  const content = (document.getElementById('fs-bc-msg')?.value || '').trim();
  const statusEl = document.getElementById('fs-bc-status');

  if (!title || !content) {
    if (statusEl) {
      statusEl.style.display = 'block';
      statusEl.style.background = '#fef2f2';
      statusEl.style.color = '#dc2626';
      statusEl.textContent = 'Please enter both title and message.';
    }
    return;
  }

  try {
    const res = await fetch('/api/admin/broadcast', {
      method: 'POST',
      headers: _adminHeaders(),
      body: JSON.stringify({ title, content, category: 'release_update' }),
    });
    const d = await res.json();
    if (!res.ok || !d.success) throw new Error(d.error || 'Broadcast failed');

    if (statusEl) {
      statusEl.style.display = 'block';
      statusEl.style.background = '#f0fdf4';
      statusEl.style.color = '#15803d';
      statusEl.textContent = d.message;
    }
    document.getElementById('fs-bc-title').value = '';
    document.getElementById('fs-bc-msg').value = '';
    setTimeout(loadStudioAdminMetrics, 300);
  } catch (err) {
    if (statusEl) {
      statusEl.style.display = 'block';
      statusEl.style.background = '#fef2f2';
      statusEl.style.color = '#dc2626';
      statusEl.textContent = err.message;
    }
  }
}

// Global modal dismiss on backdrop click
document.addEventListener('DOMContentLoaded', () => {
  const m = document.getElementById('admin-modal');
  if (m) {
    m.addEventListener('click', (e) => {
      if (e.target === m) closeAdminModal();
    });
  }
});

