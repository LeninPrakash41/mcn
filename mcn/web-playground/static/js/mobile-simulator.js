// ── Flutter simulated mobile UI rendering logic ──────────────────────────────
let _flutterRenderVersion = 0;
let _mobileRoute = 'home';
let _mobileFilter = 'All';
let _mobileSearchQuery = '';
let _mobileDarkMode = true;
let _mobileHaptic = true;
let _mobileAnalyticsPeriod = '7d';

// CRM Deals State
let _mobileDeals = [
  { id: 1, name: 'Acme Corp Enterprise', amount: 85000, stage: 'Proposal Sent', date: 'Today, 2:15 PM', color: '#38bdf8', category: 'Enterprise' },
  { id: 2, name: 'Global Logistics Cloud', amount: 142000, stage: 'In Negotiation', date: 'Yesterday', color: '#818cf8', category: 'Cloud' },
  { id: 3, name: 'Apex FinTech API Sync', amount: 64000, stage: 'Closed Won', date: 'Sep 10', color: '#34d399', category: 'FinTech' },
  { id: 4, name: 'Starlight Retail POS', amount: 129000, stage: 'Discovery Call', date: 'Sep 8', color: '#fbbf24', category: 'Retail' }
];

// Smart Home IoT State
let _mobileSmartHomeTemp = 22.5;
let _mobileSmartHomeHVAC = 'COOLING';
let _mobileSmartHomeScene = 'Home';
let _mobileSmartHomeLights = [
  { id: 'living', name: 'Living Room Lights', brightness: 80, on: true, color: '#f59e0b' },
  { id: 'kitchen', name: 'Kitchen Downlights', brightness: 100, on: true, color: '#38bdf8' },
  { id: 'bedroom', name: 'Master Bedroom Strip', brightness: 40, on: false, color: '#ec4899' },
  { id: 'office', name: 'Desk Studio Lamp', brightness: 90, on: true, color: '#10b981' }
];
let _mobileSmartHomeSecurity = 'ARMED';

// Prompt Marketplace State
let _mobilePrompts = [
  { id: 1, title: 'Enterprise Full-Stack Architecture Spec', author: '@alex_architect', category: 'Coding', stars: 4.9, forks: 342, price: 'FREE', prompt: 'You are a Principal Software Architect. Design a production-grade multi-tier architecture for {{system_type}} targeting {{cloud_provider}} with {{concurrency}} req/sec concurrency target...' },
  { id: 2, title: 'Autonomous SQL Query Optimizer & Explainer', author: '@db_ninja', category: 'Data', stars: 4.8, forks: 218, price: '$5.00', prompt: 'Analyze the following SQLite/Postgres query plan for table {{table_name}}: explain bottlenecks, recommend B-Tree indexes, and rewrite...' },
  { id: 3, title: 'Multi-Channel B2B Growth Strategy Matrix', author: '@growth_lead', category: 'Marketing', stars: 4.9, forks: 489, price: 'FREE', prompt: 'Generate a 90-day outbound SaaS acquisition playbook for {{ideal_customer_profile}} with CAC target under {{target_cac}}...' },
  { id: 4, title: 'Multi-Modal UI Wireframe Analyzer', author: '@design_ai', category: 'Vision', stars: 4.7, forks: 154, price: '$8.00', prompt: 'Extract layout hierarchy, color tokens, and Tailwind CSS component tree from the provided UI image spec...' }
];
let _mobilePromptCategoryFilter = 'All';
let _mobilePromptSearch = '';
let _mobileSelectedModel = 'Gemini 1.5 Pro';
let _mobilePromptOutputs = {};
let _mobileWorkflowPipelineRunning = false;

// Inventory State
let _mobileInventoryItems = [
  { id: 1, name: 'Ergonomic Office Chair', sku: 'CHAIR-001', category: 'Furniture', price: 120.00, stock: 54, minStock: 20 },
  { id: 2, name: 'Standing Desk 60"', sku: 'DESK-002', category: 'Furniture', price: 450.00, stock: 12, minStock: 15 },
  { id: 3, name: 'Mechanical Keyboard RGB', sku: 'TECH-003', category: 'Electronics', price: 38.50, stock: 142, minStock: 30 },
  { id: 4, name: '4K USB-C Monitor 27"', sku: 'TECH-004', category: 'Electronics', price: 75.00, stock: 48, minStock: 20 },
  { id: 5, name: 'Wireless Precision Mouse', sku: 'ACC-005', category: 'Accessories', price: 29.99, stock: 83, minStock: 25 }
];
let _mobileInventoryFilter = 'All';
let _mobileInventorySearch = '';

// Construction State
let _mobileConstructionProjects = [
  { id: 1, name: 'Skyview Tower Phase 2', budget: 4200000, spent: 2688000, progress: 64, foreman: 'Marcus Vance', deadline: 'Nov 2026' },
  { id: 2, name: 'Bay Bridge Seismic Retrofit', budget: 12800000, spent: 11648000, progress: 91, foreman: 'Elena Rostova', deadline: 'Dec 2026' },
  { id: 3, name: 'Metro Station Overhaul', budget: 8500000, spent: 3230000, progress: 38, foreman: 'David Chen', deadline: 'Apr 2027' }
];
let _mobileSafetyChecklist = [
  { id: 1, task: 'PPE Hard Hat & Hi-Vis Vest Compliance', done: true },
  { id: 2, task: 'Fall Protection & Harness Anchor Checks', done: true },
  { id: 3, task: 'Excavation Shoring & Trench Shield Inspection', done: true },
  { id: 4, task: 'Heavy Machinery Pre-Operational Inspection', done: false },
  { id: 5, task: 'OSHA Hazardous Material SDS Binder Updated', done: true }
];
let _mobileConstructionJobs = [
  { id: 1, name: 'Concrete Foundation Pour (Block B)', status: 'Completed', stage: 3, badgeColor: '#34d399' },
  { id: 2, name: 'Structural Steel Column Framing', status: 'In Progress', stage: 2, badgeColor: '#38bdf8' },
  { id: 3, name: 'HVAC Ductwork Rough-in (Level 4)', status: 'Scheduled', stage: 1, badgeColor: '#fbbf24' }
];

function getActiveProjectType() {
  if (window._currentExample && window._currentExample.id) {
    if (window._currentExample.id === 'iot_smart_home') return 'iot_smart_home';
    if (window._currentExample.id === 'prompt_marketplace') return 'prompt_marketplace';
    if (window._currentExample.id === 'analytics_hub' || window._currentExample.id === 'db_analytics') return 'analytics_hub';
    if (window._currentExample.id === 'item_manager') return 'item_manager';
    if (window._currentExample.id === 'construction') return 'construction';
    if (window._currentExample.id === 'sales_hub' || window._currentExample.id === 'crm') return 'crm';
  }
  if (typeof _models !== 'undefined') {
    for (const [path, model] of _models.entries()) {
      const val = model.getValue ? model.getValue() : '';
      if (val.includes('Prompt & Workflow Marketplace') || val.includes('prompt_marketplace')) return 'prompt_marketplace';
      if (val.includes('Executive Analytics') || val.includes('kpi_summary') || val.includes('use analytics')) return 'analytics_hub';
      if (val.includes('Smart Home') || val.includes('iot_api') || val.includes('living_room_temp')) return 'iot_smart_home';
      if (val.includes('Inventory') || val.includes('item_manager') || val.includes('CHAIR-001')) return 'item_manager';
      if (val.includes('Construction') || val.includes('Skyview')) return 'construction';
    }
  }
  return 'crm';
}

function updateMobileBottomNav(projectType, activeRoute) {
  const navContainer = document.getElementById('flutter-mock-bottomnav');
  if (!navContainer) return;

  let tabs = [];
  if (projectType === 'iot_smart_home') {
    tabs = [
      { id: 'home', label: 'Climate', icon: '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 14.76V3.5a2.5 2.5 0 0 0-5 0v11.26a4.5 4.5 0 1 0 5 0z"/></svg>' },
      { id: 'devices', label: 'Devices', icon: '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect width="18" height="12" x="3" y="4" rx="2"/><line x1="2" x2="22" y1="20" y2="20"/></svg>' },
      { id: 'energy', label: 'Energy', icon: '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>' },
      { id: 'settings', label: 'Settings', icon: '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>' }
    ];
  } else if (projectType === 'prompt_marketplace') {
    tabs = [
      { id: 'home', label: 'Prompts', icon: '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1-2.5-2.5Z"/><path d="M6 6h10"/><path d="M6 10h10"/></svg>' },
      { id: 'tester', label: 'Playground', icon: '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"/></svg>' },
      { id: 'pipelines', label: 'Pipelines', icon: '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect width="8" height="8" x="3" y="3" rx="2"/><rect width="8" height="8" x="13" y="13" rx="2"/><path d="M14 7h3a2 2 0 0 1 2 2v3"/><path d="M7 14v3a2 2 0 0 0 2 2h3"/></svg>' },
      { id: 'creator', label: 'Creator', icon: '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>' }
    ];
  } else if (projectType === 'analytics_hub') {
    tabs = [
      { id: 'home', label: 'Overview', icon: '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect width="7" height="9" x="3" y="3" rx="1"/><rect width="7" height="5" x="14" y="3" rx="1"/><rect width="7" height="9" x="14" y="12" rx="1"/><rect width="7" height="5" x="3" y="16" rx="1"/></svg>' },
      { id: 'trends', label: 'Trends', icon: '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 3v18h18"/><path d="m19 9-5 5-4-4-3 3"/></svg>' },
      { id: 'pivot', label: 'Matrix', icon: '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect width="18" height="18" x="3" y="3" rx="2"/><path d="M3 9h18"/><path d="M3 15h18"/><path d="M9 3v18"/><path d="M15 3v18"/></svg>' },
      { id: 'export', label: 'Export', icon: '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" x2="12" y1="15" y2="3"/></svg>' }
    ];
  } else if (projectType === 'item_manager') {
    tabs = [
      { id: 'home', label: 'Items', icon: '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m7.5 4.27 9 5.15"/><path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"/><path d="m3.3 7 8.7 5 8.7-5"/><path d="M12 22V12"/></svg>' },
      { id: 'stock', label: 'Stock', icon: '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" x2="12" y1="20" y2="10"/><line x1="18" x2="18" y1="20" y2="4"/><line x1="6" x2="6" y1="20" y2="16"/></svg>' },
      { id: 'add_sku', label: 'Add SKU', icon: '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" x2="12" y1="8" y2="16"/><line x1="8" x2="16" y1="12" y2="12"/></svg>' },
      { id: 'settings', label: 'Settings', icon: '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>' }
    ];
  } else if (projectType === 'construction') {
    tabs = [
      { id: 'home', label: 'Projects', icon: '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M2 20h20"/><path d="M5 20V8l7-5 7 5v12"/><path d="M9 12h6"/><path d="M9 16h6"/></svg>' },
      { id: 'jobs', label: 'Jobs', icon: '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></svg>' },
      { id: 'safety', label: 'Safety', icon: '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>' },
      { id: 'materials', label: 'Materials', icon: '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect width="8" height="8" x="3" y="3" rx="1"/><rect width="8" height="8" x="13" y="3" rx="1"/><rect width="8" height="8" x="3" y="13" rx="1"/><rect width="8" height="8" x="13" y="13" rx="1"/></svg>' }
    ];
  } else {
    tabs = [
      { id: 'home', label: 'Home', icon: '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path><polyline points="9 22 9 12 15 12 15 22"></polyline></svg>' },
      { id: 'deals', label: 'Deals', icon: '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect width="20" height="14" x="2" y="5" rx="2"></rect><line x1="2" x2="22" y1="10" y2="10"></line></svg>' },
      { id: 'analytics', label: 'Analytics', icon: '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 3v18h18"></path><path d="m19 9-5 5-4-4-3 3"></path></svg>' },
      { id: 'settings', label: 'Settings', icon: '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>' }
    ];
  }

  navContainer.innerHTML = tabs.map(tab => {
    const isActive = activeRoute === tab.id;
    const color = isActive ? '#38bdf8' : '#64748b';
    const weight = isActive ? '700' : '600';
    return `
      <div class="flutter-nav-btn ${isActive ? 'active' : ''}" id="fnav-${tab.id}" onclick="setMobileRoute('${tab.id}')" style="display:flex;flex-direction:column;align-items:center;gap:2px;cursor:pointer;padding:4px 8px;border-radius:8px;color:${color};transition:all .15s;">
        ${tab.icon}
        <span style="font-size:9px;font-weight:${weight};">${tab.label}</span>
      </div>
    `;
  }).join('');
}

function setMobileRoute(route) {
  _mobileRoute = route;
  renderFlutterSimulator();
}

function showMobileToast(message) {
  const toast = document.getElementById('flutter-phone-toast');
  const text = document.getElementById('flutter-phone-toast-text');
  if (!toast || !text) return;
  text.textContent = message;
  toast.style.display = 'flex';
  clearTimeout(window._mobileToastTimer);
  window._mobileToastTimer = setTimeout(() => {
    toast.style.display = 'none';
  }, 2400);
}

function closeMobileModal() {
  const sheet = document.getElementById('flutter-phone-modal-sheet');
  const backdrop = document.getElementById('flutter-phone-modal-backdrop');
  if (sheet) sheet.style.transform = 'translateY(100%)';
  if (backdrop) backdrop.style.opacity = '0';
  setTimeout(() => {
    if (sheet) sheet.style.display = 'none';
    if (backdrop) backdrop.style.display = 'none';
  }, 200);
}

function openMobileModal(html) {
  const sheet = document.getElementById('flutter-phone-modal-sheet');
  const backdrop = document.getElementById('flutter-phone-modal-backdrop');
  const content = document.getElementById('flutter-phone-modal-content');
  if (!sheet || !backdrop || !content) return;
  content.innerHTML = html;
  backdrop.style.display = 'block';
  sheet.style.display = 'block';
  setTimeout(() => {
    backdrop.style.opacity = '1';
    sheet.style.transform = 'translateY(0)';
  }, 10);
}

// ── Smart Home Interactive Handlers ─────────────────────────────────────────
function adjustMobileTemp(delta) {
  _mobileSmartHomeTemp = Math.round((_mobileSmartHomeTemp + delta) * 10) / 10;
  showMobileToast(`🌡 Climate target: ${_mobileSmartHomeTemp}°C`);
  renderFlutterSimulator();
}

function toggleMobileHVAC() {
  const modes = ['COOLING', 'HEATING', 'AUTO', 'ECO'];
  const curIdx = modes.indexOf(_mobileSmartHomeHVAC);
  _mobileSmartHomeHVAC = modes[(curIdx + 1) % modes.length];
  showMobileToast(`❄ HVAC Mode set to ${_mobileSmartHomeHVAC}`);
  renderFlutterSimulator();
}

function selectMobileScene(scene) {
  _mobileSmartHomeScene = scene;
  if (scene === 'Sleep') {
    _mobileSmartHomeLights.forEach(l => l.on = false);
    _mobileSmartHomeTemp = 20.0;
  } else if (scene === 'Party') {
    _mobileSmartHomeLights.forEach(l => l.on = true);
    _mobileSmartHomeTemp = 21.0;
  } else if (scene === 'Home') {
    _mobileSmartHomeLights[0].on = true;
    _mobileSmartHomeLights[1].on = true;
    _mobileSmartHomeTemp = 22.5;
  } else if (scene === 'Away') {
    _mobileSmartHomeLights.forEach(l => l.on = false);
    _mobileSmartHomeSecurity = 'ARMED';
  }
  showMobileToast(`✨ Scene activated: ${scene}`);
  renderFlutterSimulator();
}

function toggleMobileLight(id) {
  const light = _mobileSmartHomeLights.find(l => l.id === id);
  if (light) {
    light.on = !light.on;
    showMobileToast(`💡 ${light.name}: ${light.on ? 'ON' : 'OFF'}`);
    renderFlutterSimulator();
  }
}

function toggleMobileSecurity() {
  _mobileSmartHomeSecurity = _mobileSmartHomeSecurity === 'ARMED' ? 'DISARMED' : 'ARMED';
  showMobileToast(`🛡 Security System: ${_mobileSmartHomeSecurity}`);
  renderFlutterSimulator();
}

// ── Prompt Marketplace Interactive Handlers ────────────────────────────────
function setPromptCategory(cat) {
  _mobilePromptCategoryFilter = cat;
  renderFlutterSimulator();
}

function filterMobilePrompts(query) {
  _mobilePromptSearch = query.toLowerCase();
  renderFlutterSimulator();
}

function copyMobilePrompt(id) {
  const p = _mobilePrompts.find(x => x.id === id);
  if (p) {
    if (navigator.clipboard) {
      navigator.clipboard.writeText(p.prompt).catch(() => {});
    }
    showMobileToast(`📋 Copied: "${p.title}"`);
  }
}

function forkMobilePrompt(id) {
  const p = _mobilePrompts.find(x => x.id === id);
  if (p) {
    p.forks += 1;
    showMobileToast(`⚡ Forked "${p.title}" to Studio`);
    renderFlutterSimulator();
  }
}

function openMobilePromptModal(id) {
  const p = _mobilePrompts.find(x => x.id === id);
  if (!p) return;

  const modalHtml = `
    <div style="display:flex;flex-direction:column;gap:10px;">
      <div style="display:flex;justify-content:space-between;align-items:flex-start;">
        <div>
          <span style="font-size:9px;color:#818cf8;font-weight:700;text-transform:uppercase;">${p.category} PROMPT</span>
          <div style="font-weight:800;font-size:13px;color:#fff;margin-top:2px;">${p.title}</div>
          <div style="font-size:9.5px;color:#94a3b8;margin-top:2px;">by ${p.author} • ★ ${p.stars} (${p.forks} forks)</div>
        </div>
        <button onclick="closeMobileModal()" style="background:none;border:none;color:#94a3b8;font-size:14px;cursor:pointer;">✕</button>
      </div>
      <div style="background:#080e21;border:1px solid #1e293b;border-radius:8px;padding:10px;font-family:monospace;font-size:10px;color:#38bdf8;line-height:1.5;max-height:140px;overflow-y:auto;white-space:pre-wrap;">${p.prompt}</div>
      <div style="display:flex;gap:6px;margin-top:4px;">
        <button onclick="copyMobilePrompt(${p.id}); closeMobileModal();" style="flex:1;background:rgba(255,255,255,0.08);border:none;border-radius:6px;padding:7px;color:#fff;font-size:11px;font-weight:600;cursor:pointer;">📋 Copy Prompt</button>
        <button onclick="forkMobilePrompt(${p.id}); closeMobileModal(); setMobileRoute('tester');" style="flex:1;background:linear-gradient(135deg, #0284c7, #38bdf8);border:none;border-radius:6px;padding:7px;color:#fff;font-weight:700;font-size:11px;cursor:pointer;">⚡ Test in Playground</button>
      </div>
    </div>
  `;
  openMobileModal(modalHtml);
}

function selectMobileModel(model) {
  _mobileSelectedModel = model;
  renderFlutterSimulator();
}

function runMobilePromptSim() {
  const topicInput = document.getElementById('mprompt-topic');
  const topic = topicInput ? topicInput.value.trim() : 'Cloud Microservices';
  showMobileToast(`⚡ Executing on ${_mobileSelectedModel}...`);
  const outputEl = document.getElementById('mprompt-sim-output');
  if (outputEl) {
    outputEl.innerHTML = '<span style="color:#94a3b8;font-style:italic;">Synthesizing response via MCN AI Logic Engine...</span>';
    setTimeout(() => {
      outputEl.innerHTML = `
        <div style="color:#38bdf8;font-weight:700;margin-bottom:4px;">✓ Response from ${_mobileSelectedModel} (184 tokens • 240ms):</div>
        <div style="color:#e2e8f0;line-height:1.4;">Based on the spec for <strong>${topic}</strong>:
1. Deployed Envoy API Gateway with rate limiting & JWT verification.
2. Implemented stateless microservices with Redis L2 caching.
3. Configured PostgreSQL read replicas with connection pooling.</div>
      `;
      showMobileToast('✓ Generation Complete');
    }, 450);
  }
}

function runMobileWorkflowPipeline() {
  if (_mobileWorkflowPipelineRunning) return;
  _mobileWorkflowPipelineRunning = true;
  showMobileToast('▶ Running 3-Stage Workflow...');
  
  const s1 = document.getElementById('wf-step-1');
  const s2 = document.getElementById('wf-step-2');
  const s3 = document.getElementById('wf-step-3');
  
  if (s1) s1.style.borderColor = '#38bdf8';
  setTimeout(() => {
    if (s1) { s1.style.borderColor = '#34d399'; s1.innerHTML = '✓ 1. Extraction & Ingest (Done)'; }
    if (s2) s2.style.borderColor = '#38bdf8';
    setTimeout(() => {
      if (s2) { s2.style.borderColor = '#34d399'; s2.innerHTML = '✓ 2. LLM Synthesis & Reasoning (Done)'; }
      if (s3) s3.style.borderColor = '#38bdf8';
      setTimeout(() => {
        if (s3) { s3.style.borderColor = '#34d399'; s3.innerHTML = '✓ 3. Schema Validator & JSON Guard (Done)'; }
        _mobileWorkflowPipelineRunning = false;
        showMobileToast('✓ Workflow Pipeline Succeeded!');
      }, 400);
    }, 400);
  }, 400);
}

function openPublishPromptModal() {
  const formHtml = `
    <div style="display:flex;flex-direction:column;gap:10px;">
      <div style="display:flex;justify-content:space-between;align-items:center;">
        <span style="font-weight:700;font-size:12.5px;color:#fff;">+ Publish AI Prompt</span>
        <button onclick="closeMobileModal()" style="background:none;border:none;color:#94a3b8;font-size:14px;cursor:pointer;">✕</button>
      </div>
      <div>
        <label style="font-size:10px;color:#94a3b8;display:block;margin-bottom:3px;">Prompt Title</label>
        <input id="mpub-title" type="text" placeholder="e.g. Next.js 15 Server Action Generator" style="width:100%;box-sizing:border-box;background:#1e293b;border:1px solid #334155;border-radius:6px;padding:6px 8px;color:#fff;font-size:11px;" />
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
        <div>
          <label style="font-size:10px;color:#94a3b8;display:block;margin-bottom:3px;">Category</label>
          <select id="mpub-category" style="width:100%;box-sizing:border-box;background:#1e293b;border:1px solid #334155;border-radius:6px;padding:6px 8px;color:#fff;font-size:11px;">
            <option value="Coding">Coding</option>
            <option value="Data">Data</option>
            <option value="Marketing">Marketing</option>
            <option value="Vision">Vision</option>
          </select>
        </div>
        <div>
          <label style="font-size:10px;color:#94a3b8;display:block;margin-bottom:3px;">Price</label>
          <input id="mpub-price" type="text" placeholder="FREE" value="FREE" style="width:100%;box-sizing:border-box;background:#1e293b;border:1px solid #334155;border-radius:6px;padding:6px 8px;color:#fff;font-size:11px;" />
        </div>
      </div>
      <div>
        <label style="font-size:10px;color:#94a3b8;display:block;margin-bottom:3px;">Prompt Template</label>
        <textarea id="mpub-prompt" rows="3" placeholder="You are an expert in {{topic}}..." style="width:100%;box-sizing:border-box;background:#1e293b;border:1px solid #334155;border-radius:6px;padding:6px 8px;color:#fff;font-size:10.5px;font-family:monospace;"></textarea>
      </div>
      <div style="display:flex;gap:6px;margin-top:4px;">
        <button onclick="closeMobileModal()" style="flex:1;background:rgba(255,255,255,0.08);border:none;border-radius:6px;padding:7px;color:#94a3b8;font-size:11px;cursor:pointer;">Cancel</button>
        <button onclick="saveNewPromptFromModal()" style="flex:1;background:linear-gradient(135deg, #0284c7, #38bdf8);border:none;border-radius:6px;padding:7px;color:#fff;font-weight:700;font-size:11px;cursor:pointer;">Publish Now</button>
      </div>
    </div>
  `;
  openMobileModal(formHtml);
}

function saveNewPromptFromModal() {
  const title = document.getElementById('mpub-title')?.value.trim();
  const category = document.getElementById('mpub-category')?.value || 'Coding';
  const price = document.getElementById('mpub-price')?.value.trim() || 'FREE';
  const promptText = document.getElementById('mpub-prompt')?.value.trim();

  if (!title || !promptText) {
    showMobileToast('⚠️ Please enter title and prompt text');
    return;
  }

  _mobilePrompts.unshift({
    id: Date.now(),
    title: title,
    author: '@you',
    category: category,
    stars: 5.0,
    forks: 0,
    price: price,
    prompt: promptText
  });

  closeMobileModal();
  showMobileToast(`✓ Published: ${title}`);
  renderFlutterSimulator();
}

// ── Inventory Handlers ──────────────────────────────────────────────────────
function adjustMobileStock(id, delta) {
  const item = _mobileInventoryItems.find(x => x.id === id);
  if (item) {
    item.stock = Math.max(0, item.stock + delta);
    showMobileToast(`📦 ${item.name}: ${item.stock} units`);
    renderFlutterSimulator();
  }
}

function reorderMobileStock(id) {
  const item = _mobileInventoryItems.find(x => x.id === id);
  if (item) {
    item.stock += 50;
    showMobileToast(`✓ Reordered +50 units for ${item.name}`);
    renderFlutterSimulator();
  }
}

function filterMobileInventory(query) {
  _mobileInventorySearch = query.toLowerCase();
  renderFlutterSimulator();
}

function setInventoryFilter(cat) {
  _mobileInventoryFilter = cat;
  renderFlutterSimulator();
}

function openMobileAddSkuModal() {
  const formHtml = `
    <div style="display:flex;flex-direction:column;gap:10px;">
      <div style="display:flex;justify-content:space-between;align-items:center;">
        <span style="font-weight:700;font-size:12.5px;color:#fff;">+ Add Inventory Item</span>
        <button onclick="closeMobileModal()" style="background:none;border:none;color:#94a3b8;font-size:14px;cursor:pointer;">✕</button>
      </div>
      <div>
        <label style="font-size:10px;color:#94a3b8;display:block;margin-bottom:3px;">Item Name</label>
        <input id="msku-name" type="text" placeholder="e.g. Ergonomic Monitor Arm" style="width:100%;box-sizing:border-box;background:#1e293b;border:1px solid #334155;border-radius:6px;padding:6px 8px;color:#fff;font-size:11px;" />
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
        <div>
          <label style="font-size:10px;color:#94a3b8;display:block;margin-bottom:3px;">SKU Code</label>
          <input id="msku-code" type="text" placeholder="ARM-006" style="width:100%;box-sizing:border-box;background:#1e293b;border:1px solid #334155;border-radius:6px;padding:6px 8px;color:#fff;font-size:11px;" />
        </div>
        <div>
          <label style="font-size:10px;color:#94a3b8;display:block;margin-bottom:3px;">Category</label>
          <select id="msku-cat" style="width:100%;box-sizing:border-box;background:#1e293b;border:1px solid #334155;border-radius:6px;padding:6px 8px;color:#fff;font-size:11px;">
            <option value="Furniture">Furniture</option>
            <option value="Electronics">Electronics</option>
            <option value="Accessories">Accessories</option>
          </select>
        </div>
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
        <div>
          <label style="font-size:10px;color:#94a3b8;display:block;margin-bottom:3px;">Price ($)</label>
          <input id="msku-price" type="number" placeholder="89.99" style="width:100%;box-sizing:border-box;background:#1e293b;border:1px solid #334155;border-radius:6px;padding:6px 8px;color:#fff;font-size:11px;" />
        </div>
        <div>
          <label style="font-size:10px;color:#94a3b8;display:block;margin-bottom:3px;">Initial Stock</label>
          <input id="msku-stock" type="number" placeholder="30" style="width:100%;box-sizing:border-box;background:#1e293b;border:1px solid #334155;border-radius:6px;padding:6px 8px;color:#fff;font-size:11px;" />
        </div>
      </div>
      <div style="display:flex;gap:6px;margin-top:4px;">
        <button onclick="closeMobileModal()" style="flex:1;background:rgba(255,255,255,0.08);border:none;border-radius:6px;padding:7px;color:#94a3b8;font-size:11px;cursor:pointer;">Cancel</button>
        <button onclick="saveNewSkuFromModal()" style="flex:1;background:linear-gradient(135deg, #0284c7, #38bdf8);border:none;border-radius:6px;padding:7px;color:#fff;font-weight:700;font-size:11px;cursor:pointer;">Save to SQLite</button>
      </div>
    </div>
  `;
  openMobileModal(formHtml);
}

function saveNewSkuFromModal() {
  const name = document.getElementById('msku-name')?.value.trim();
  const sku = document.getElementById('msku-code')?.value.trim() || 'SKU-' + Date.now();
  const category = document.getElementById('msku-cat')?.value || 'Furniture';
  const price = parseFloat(document.getElementById('msku-price')?.value) || 49.99;
  const stock = parseInt(document.getElementById('msku-stock')?.value, 10) || 25;

  if (!name) {
    showMobileToast('⚠️ Please enter an item name');
    return;
  }

  _mobileInventoryItems.unshift({
    id: Date.now(),
    name: name,
    sku: sku,
    category: category,
    price: price,
    stock: stock,
    minStock: 15
  });

  closeMobileModal();
  showMobileToast(`✓ Added SKU: ${sku}`);
  renderFlutterSimulator();
}

// ── Construction Handlers ───────────────────────────────────────────────────
function advanceConstructionJob(id) {
  const job = _mobileConstructionJobs.find(x => x.id === id);
  if (job) {
    if (job.status === 'Scheduled') {
      job.status = 'In Progress';
      job.badgeColor = '#38bdf8';
    } else if (job.status === 'In Progress') {
      job.status = 'Completed';
      job.badgeColor = '#34d399';
    } else {
      job.status = 'Scheduled';
      job.badgeColor = '#fbbf24';
    }
    showMobileToast(`✓ ${job.name}: ${job.status}`);
    renderFlutterSimulator();
  }
}

function toggleSafetyCheck(id) {
  const item = _mobileSafetyChecklist.find(x => x.id === id);
  if (item) {
    item.done = !item.done;
    showMobileToast(`✓ Inspection updated: ${item.task.slice(0, 20)}…`);
    renderFlutterSimulator();
  }
}

// ── Executive BI Handlers ───────────────────────────────────────────────────
function copyExecutiveReportMarkdown() {
  const report = `# Executive Analytics & BI Summary\n**Generated:** ${new Date().toLocaleDateString()}\n**Gross Revenue:** $476,500.00\n**Deals:** 8 Total (6 Closed Won, 2 Pending)\n**Win Rate:** 75.0%\n**Avg Deal Size:** $59,562.50\n\n### Pareto Distribution\n- Cloud Architecture: $234,000 (49.1%)\n- AI & ML Pipelines: $144,000 (30.2%)\n- Enterprise ERP: $79,500 (16.7%)\n- Security & Compliance: $19,000 (4.0%)`;
  if (navigator.clipboard) {
    navigator.clipboard.writeText(report).catch(() => {});
  }
  showMobileToast('📋 Executive BI Report copied!');
}

function exportExecutiveCSV() {
  showMobileToast('📥 Exported sales_transactions.csv');
}

// ── CRM Handlers ────────────────────────────────────────────────────────────
function openNewDealModal() {
  const formHtml = `
    <div style="display:flex;flex-direction:column;gap:10px;">
      <div style="display:flex;justify-content:space-between;align-items:center;">
        <span style="font-weight:700;font-size:12.5px;color:#fff;">+ New Pipeline Deal</span>
        <button onclick="closeMobileModal()" style="background:none;border:none;color:#94a3b8;font-size:14px;cursor:pointer;">✕</button>
      </div>
      <div>
        <label style="font-size:10px;color:#94a3b8;display:block;margin-bottom:3px;">Deal Name</label>
        <input id="mdeal-name" type="text" placeholder="e.g. Acme Corp Expansion" style="width:100%;box-sizing:border-box;background:#1e293b;border:1px solid #334155;border-radius:6px;padding:6px 8px;color:#fff;font-size:11px;" />
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
        <div>
          <label style="font-size:10px;color:#94a3b8;display:block;margin-bottom:3px;">Amount ($)</label>
          <input id="mdeal-amount" type="number" placeholder="50000" style="width:100%;box-sizing:border-box;background:#1e293b;border:1px solid #334155;border-radius:6px;padding:6px 8px;color:#fff;font-size:11px;" />
        </div>
        <div>
          <label style="font-size:10px;color:#94a3b8;display:block;margin-bottom:3px;">Category</label>
          <select id="mdeal-category" style="width:100%;box-sizing:border-box;background:#1e293b;border:1px solid #334155;border-radius:6px;padding:6px 8px;color:#fff;font-size:11px;">
            <option value="Enterprise">Enterprise</option>
            <option value="Cloud">Cloud</option>
            <option value="FinTech">FinTech</option>
            <option value="Retail">Retail</option>
            <option value="SaaS">SaaS</option>
          </select>
        </div>
      </div>
      <div>
        <label style="font-size:10px;color:#94a3b8;display:block;margin-bottom:3px;">Initial Stage</label>
        <select id="mdeal-stage" style="width:100%;box-sizing:border-box;background:#1e293b;border:1px solid #334155;border-radius:6px;padding:6px 8px;color:#fff;font-size:11px;">
          <option value="Discovery Call">Discovery Call</option>
          <option value="Proposal Sent">Proposal Sent</option>
          <option value="In Negotiation">In Negotiation</option>
          <option value="Closed Won">Closed Won</option>
        </select>
      </div>
      <div style="display:flex;gap:6px;margin-top:4px;">
        <button onclick="closeMobileModal()" style="flex:1;background:rgba(255,255,255,0.08);border:none;border-radius:6px;padding:7px;color:#94a3b8;font-size:11px;cursor:pointer;">Cancel</button>
        <button onclick="saveNewDealFromModal()" style="flex:1;background:linear-gradient(135deg, #0284c7, #38bdf8);border:none;border-radius:6px;padding:7px;color:#fff;font-weight:700;font-size:11px;cursor:pointer;">Create Deal</button>
      </div>
    </div>
  `;
  openMobileModal(formHtml);
}

function saveNewDealFromModal() {
  const nameInput = document.getElementById('mdeal-name');
  const amountInput = document.getElementById('mdeal-amount');
  const catInput = document.getElementById('mdeal-category');
  const stageInput = document.getElementById('mdeal-stage');

  const name = nameInput ? nameInput.value.trim() : '';
  const amount = amountInput ? parseInt(amountInput.value, 10) || 10000 : 10000;
  const category = catInput ? catInput.value : 'Enterprise';
  const stage = stageInput ? stageInput.value : 'Discovery Call';

  if (!name) {
    showMobileToast('⚠️ Please enter a deal name');
    return;
  }

  const newDeal = {
    id: Date.now(),
    name: name,
    amount: amount,
    category: category,
    stage: stage,
    date: 'Just now',
    color: category === 'Enterprise' ? '#38bdf8' : category === 'Cloud' ? '#818cf8' : category === 'FinTech' ? '#34d399' : '#fbbf24'
  };

  _mobileDeals.unshift(newDeal);
  closeMobileModal();
  showMobileToast(`✓ Created deal: ${name}`);
  renderFlutterSimulator();
}

function openDealDetailModal(id) {
  const deal = _mobileDeals.find(d => d.id === id);
  if (!deal) return;

  const stages = ['Discovery Call', 'Proposal Sent', 'In Negotiation', 'Closed Won'];
  const currentIndex = stages.indexOf(deal.stage);
  const nextStage = currentIndex < stages.length - 1 ? stages[currentIndex + 1] : null;

  const detailHtml = `
    <div style="display:flex;flex-direction:column;gap:10px;">
      <div style="display:flex;justify-content:space-between;align-items:flex-start;">
        <div>
          <div style="font-size:9px;color:#38bdf8;font-weight:700;text-transform:uppercase;">${deal.category} DEAL</div>
          <div style="font-weight:800;font-size:13px;color:#fff;margin-top:2px;">${deal.name}</div>
        </div>
        <button onclick="closeMobileModal()" style="background:none;border:none;color:#94a3b8;font-size:14px;cursor:pointer;">✕</button>
      </div>
      <div style="background:#1e293b;border-radius:10px;padding:10px;display:flex;justify-content:space-between;align-items:center;">
        <div>
          <div style="font-size:9px;color:#94a3b8;">Deal Value</div>
          <div style="font-size:17px;font-weight:800;color:#38bdf8;">$${deal.amount.toLocaleString()}</div>
        </div>
        <div style="text-align:right;">
          <div style="font-size:9px;color:#94a3b8;">Current Stage</div>
          <span style="font-size:9.5px;font-weight:700;background:rgba(56,189,248,0.15);color:#38bdf8;border:1px solid rgba(56,189,248,0.3);padding:2px 7px;border-radius:4px;display:inline-block;margin-top:2px;">${deal.stage}</span>
        </div>
      </div>
      <div style="font-size:9.5px;color:#94a3b8;line-height:1.5;">
        <span>Recorded: ${deal.date}</span><br>
        <span>Engine: MCN Flutter Mobile Backend (:8080)</span>
      </div>
      <div style="display:flex;flex-direction:column;gap:6px;margin-top:4px;">
        ${nextStage ? `
          <button onclick="advanceDealStage(${deal.id}, '${nextStage}')" style="background:linear-gradient(135deg, #0284c7, #38bdf8);border:none;border-radius:6px;padding:7px;color:#fff;font-weight:700;font-size:11px;cursor:pointer;">
            Advance to ${nextStage} →
          </button>
        ` : `
          <div style="text-align:center;padding:6px;background:rgba(52,211,153,0.15);border:1px solid rgba(52,211,153,0.3);border-radius:6px;color:#34d399;font-size:10px;font-weight:700;">
            ✓ Deal Won &amp; Finalized
          </div>
        `}
        <button onclick="deleteMobileDeal(${deal.id})" style="background:rgba(239,68,68,0.12);border:1px solid rgba(239,68,68,0.3);border-radius:6px;padding:6px;color:#f87171;font-size:10.5px;cursor:pointer;">
          Delete Deal
        </button>
      </div>
    </div>
  `;
  openMobileModal(detailHtml);
}

function advanceDealStage(id, newStage) {
  const deal = _mobileDeals.find(d => d.id === id);
  if (deal) {
    deal.stage = newStage;
    closeMobileModal();
    showMobileToast(`✓ Advanced to ${newStage}`);
    renderFlutterSimulator();
  }
}

function deleteMobileDeal(id) {
  _mobileDeals = _mobileDeals.filter(d => d.id !== id);
  closeMobileModal();
  showMobileToast('🗑 Deal deleted');
  renderFlutterSimulator();
}

function filterMobileDeals(query) {
  _mobileSearchQuery = query.toLowerCase();
  renderFlutterSimulator();
}

function setDealFilter(filter) {
  _mobileFilter = filter;
  renderFlutterSimulator();
}

function setAnalyticsPeriod(p) {
  _mobileAnalyticsPeriod = p;
  renderFlutterSimulator();
}

function syncMobileWithBackend() {
  showMobileToast('⚡ Syncing with MCN Backend...');
  setTimeout(() => {
    showMobileToast(`✓ Live: ${_mobileDeals.length} deals synced`);
  }, 600);
}

function triggerMobileHapticSync() {
  showMobileToast('↺ Simulator refreshed');
  renderFlutterSimulator();
}

function toggleMobileTheme() {
  _mobileDarkMode = !_mobileDarkMode;
  showMobileToast(_mobileDarkMode ? '🌙 Dark theme enabled' : '☀️ Light theme enabled');
  renderFlutterSimulator();
}

function toggleMobileHaptics() {
  _mobileHaptic = !_mobileHaptic;
  showMobileToast(_mobileHaptic ? '📳 Haptics enabled' : '🔕 Haptics disabled');
  renderFlutterSimulator();
}

async function pingMobileBackend() {
  showMobileToast('Pinging MCN Backend (:8080)…');
  try {
    const r = await apiFetch('/api/devserver/status');
    const d = await r.json();
    if (d.backend_running) {
      showMobileToast('✓ Backend active on port 8080');
    } else {
      showMobileToast('ℹ Backend idle. Click Run Backend to start.');
    }
  } catch (e) {
    showMobileToast('✗ Backend unreachable: ' + e.message);
  }
}

async function renderFlutterSimulator() {
  const currentVersion = ++_flutterRenderVersion;
  const mockContent = document.getElementById('flutter-mock-content');
  const titleEl = document.getElementById('flutter-appbar-title');
  if (!mockContent) return;

  const projectType = getActiveProjectType();
  updateMobileBottomNav(projectType, _mobileRoute);

  let manifest = null;
  try {
    const r = await apiFetch('/api/workspace/file?path=mobile/ui-manifest.json');
    if (r.ok) {
      const d = await r.json();
      manifest = JSON.parse(d.content);
    }
  } catch (_) {}

  if (currentVersion !== _flutterRenderVersion) return;

  // ═══════════════════════════════════════════════════════════════════════════
  // 1. SMART HOME IOT CONTROLLER (iot_smart_home)
  // ═══════════════════════════════════════════════════════════════════════════
  if (projectType === 'iot_smart_home') {
    if (_mobileRoute === 'devices') {
      if (titleEl) titleEl.textContent = 'Connected Devices';
      const devices = [
        { name: 'Living Room Hue', type: 'Lighting', status: 'Online • 80%', icon: '💡', active: true },
        { name: 'Nest Thermostat Pro', type: 'Climate', status: 'Online • 22.5°C', icon: '🌡', active: true },
        { name: 'Kitchen Downlights', type: 'Lighting', status: 'Online • 100%', icon: '💡', active: true },
        { name: 'Front Door SmartLock', type: 'Security', status: 'Locked • Battery 94%', icon: '🔒', active: true },
        { name: 'Garage Tilt Sensor', type: 'Security', status: 'Closed • Battery 88%', icon: '🚪', active: true },
        { name: 'Solar Micro-Inverter', type: 'Energy', status: '+4.8 kW Generating', icon: '⚡', active: true }
      ];

      mockContent.innerHTML = `
        <div style="display:flex;justify-content:space-between;align-items:center;padding:2px 0;">
          <span style="font-size:11px;font-weight:700;color:#fff;">6 Connected Nodes</span>
          <span style="font-size:9.5px;color:#34d399;font-weight:600;">● Zigbee Mesh Active</span>
        </div>
        <div style="display:flex;flex-direction:column;gap:6px;">
          ${devices.map(d => `
            <div style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:10px;padding:10px;display:flex;justify-content:space-between;align-items:center;">
              <div style="display:flex;align-items:center;gap:8px;">
                <span style="font-size:16px;">${d.icon}</span>
                <div>
                  <div style="font-size:11px;font-weight:700;color:#fff;">${d.name}</div>
                  <div style="font-size:9px;color:#94a3b8;">${d.status}</div>
                </div>
              </div>
              <button onclick="showMobileToast('✓ Toggled ${d.name}')" style="background:${d.active ? '#0284c7' : 'rgba(255,255,255,0.1)'};border:none;border-radius:10px;padding:3px 8px;font-size:9px;color:#fff;cursor:pointer;">${d.active ? 'ON' : 'OFF'}</button>
            </div>
          `).join('')}
        </div>
      `;
      return;
    }

    if (_mobileRoute === 'energy') {
      if (titleEl) titleEl.textContent = 'Energy & Power';
      mockContent.innerHTML = `
        <div style="background:linear-gradient(135deg, rgba(16,185,129,0.15), rgba(2,132,199,0.1));border:1px solid rgba(16,185,129,0.3);border-radius:12px;padding:12px;">
          <div style="font-size:9.5px;font-weight:700;color:#34d399;text-transform:uppercase;">Solar Generation</div>
          <div style="font-size:22px;font-weight:800;color:#ffffff;margin-top:2px;">+4.8 kW</div>
          <div style="font-size:9.5px;color:#94a3b8;margin-top:2px;">Grid Export: <span style="color:#38bdf8;font-weight:700;">1.4 kW</span> • House Load: <span style="color:#fbbf24;font-weight:700;">3.4 kW</span></div>
        </div>

        <div style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:12px;padding:10px;">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
            <span style="font-size:10px;font-weight:700;color:#e2e8f0;">Weekly Consumption</span>
            <span style="font-size:9px;color:#38bdf8;">Flutter CustomPainter</span>
          </div>
          <div style="height:54px;display:flex;align-items:flex-end;justify-content:space-between;gap:6px;padding:0 4px;">
            ${['M', 'T', 'W', 'T', 'F', 'S', 'S'].map((day, i) => `
              <div style="flex:1;display:flex;flex-direction:column;align-items:center;gap:3px;">
                <div style="width:100%;height:${[28, 42, 36, 50, 40, 22, 18][i]}px;background:${i === 3 ? 'linear-gradient(to top, #0284c7, #38bdf8)' : 'rgba(56,189,248,0.45)'};border-radius:3px;"></div>
                <span style="font-size:8px;color:${i === 3 ? '#38bdf8' : '#64748b'};font-weight:${i === 3 ? '700' : '500'};">${day}</span>
              </div>
            `).join('')}
          </div>
        </div>

        <div style="background:rgba(52,211,153,0.08);border:1px solid rgba(52,211,153,0.25);border-radius:10px;padding:9px;display:flex;align-items:center;gap:8px;">
          <span style="font-size:16px;">🌱</span>
          <div style="font-size:9.5px;color:#34d399;font-weight:600;">$48.20 saved this month via Solar Smart Shift algorithm.</div>
        </div>
      `;
      return;
    }

    if (_mobileRoute === 'settings') {
      if (titleEl) titleEl.textContent = 'Hub Settings';
      mockContent.innerHTML = `
        <div style="background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.08);border-radius:12px;padding:10px;display:flex;align-items:center;gap:10px;">
          <div style="width:36px;height:36px;border-radius:50%;background:linear-gradient(135deg, #0284c7, #38bdf8);display:flex;align-items:center;justify-content:center;font-weight:700;font-size:14px;color:#fff;">🏠</div>
          <div>
            <div style="font-weight:700;font-size:11.5px;color:#fff;">Smart Home Central Hub</div>
            <div style="font-size:9px;color:#94a3b8;">Matter 1.3 • Zigbee 3.0 Bridge</div>
          </div>
        </div>

        <div style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:12px;padding:10px;display:flex;flex-direction:column;gap:8px;">
          <div style="font-size:10px;font-weight:700;color:#38bdf8;text-transform:uppercase;">Preferences</div>
          <div style="display:flex;justify-content:space-between;align-items:center;font-size:10.5px;">
            <span style="color:#e2e8f0;">Dark Theme</span>
            <button onclick="toggleMobileTheme()" style="background:${_mobileDarkMode ? '#0284c7' : 'rgba(255,255,255,0.1)'};border:none;border-radius:10px;padding:2px 8px;font-size:9px;color:#fff;cursor:pointer;">${_mobileDarkMode ? 'ON' : 'OFF'}</button>
          </div>
          <div style="display:flex;justify-content:space-between;align-items:center;font-size:10.5px;border-top:1px solid rgba(255,255,255,0.05);padding-top:6px;">
            <span style="color:#e2e8f0;">Haptic Feedback</span>
            <button onclick="toggleMobileHaptics()" style="background:${_mobileHaptic ? '#0284c7' : 'rgba(255,255,255,0.1)'};border:none;border-radius:10px;padding:2px 8px;font-size:9px;color:#fff;cursor:pointer;">${_mobileHaptic ? 'ON' : 'OFF'}</button>
          </div>
        </div>

        <button onclick="pingMobileBackend()" style="background:rgba(56,189,248,0.15);border:1px solid rgba(56,189,248,0.3);border-radius:8px;padding:8px;color:#38bdf8;font-size:10.5px;font-weight:700;cursor:pointer;">⚡ Ping IoT Backend (:8080)</button>
      `;
      return;
    }

    // Default: 'home' / Climate
    if (titleEl) titleEl.textContent = 'Smart Home Hub';
    mockContent.innerHTML = `
      <!-- Thermostat Dial Widget -->
      <div style="background:radial-gradient(circle at 50% 30%, rgba(56,189,248,0.12), rgba(15,23,42,0.6));border:1px solid rgba(56,189,248,0.25);border-radius:14px;padding:12px;text-align:center;">
        <div style="display:flex;justify-content:space-between;align-items:center;">
          <span style="font-size:9.5px;font-weight:700;color:#38bdf8;text-transform:uppercase;">Living Room Climate</span>
          <span onclick="toggleMobileHVAC()" style="font-size:9px;font-weight:700;background:rgba(56,189,248,0.2);color:#38bdf8;padding:2px 6px;border-radius:4px;cursor:pointer;">${_mobileSmartHomeHVAC}</span>
        </div>
        <div style="margin:10px auto;width:100px;height:100px;border-radius:50%;border:4px solid #38bdf8;display:flex;flex-direction:column;align-items:center;justify-content:center;background:#080e21;box-shadow:0 0 20px rgba(56,189,248,0.25);">
          <span style="font-size:22px;font-weight:800;color:#fff;">${_mobileSmartHomeTemp.toFixed(1)}°</span>
          <span style="font-size:8.5px;color:#94a3b8;">TARGET</span>
        </div>
        <div style="display:flex;justify-content:center;gap:12px;">
          <button onclick="adjustMobileTemp(-0.5)" style="width:32px;height:32px;border-radius:50%;background:rgba(255,255,255,0.08);border:1px solid rgba(255,255,255,0.15);color:#fff;font-size:16px;font-weight:700;cursor:pointer;">−</button>
          <button onclick="adjustMobileTemp(0.5)" style="width:32px;height:32px;border-radius:50%;background:linear-gradient(135deg, #0284c7, #38bdf8);border:none;color:#fff;font-size:16px;font-weight:700;cursor:pointer;">+</button>
        </div>
      </div>

      <!-- Quick Scenes -->
      <div style="display:grid;grid-template-columns:repeat(4, 1fr);gap:4px;">
        ${['Home', 'Away', 'Sleep', 'Party'].map(scene => `
          <button onclick="selectMobileScene('${scene}')" style="background:${_mobileSmartHomeScene === scene ? '#0284c7' : 'rgba(255,255,255,0.05)'};border:1px solid ${_mobileSmartHomeScene === scene ? '#38bdf8' : 'rgba(255,255,255,0.08)'};border-radius:8px;padding:6px 2px;color:#fff;font-size:9.5px;font-weight:${_mobileSmartHomeScene === scene ? '700' : '500'};cursor:pointer;">${scene}</button>
        `).join('')}
      </div>

      <!-- Lighting & Security -->
      <div style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:10px;padding:10px;display:flex;flex-direction:column;gap:6px;">
        <div style="display:flex;justify-content:space-between;align-items:center;">
          <span style="font-size:10px;font-weight:700;color:#e2e8f0;">Quick Lighting</span>
          <span onclick="setMobileRoute('devices')" style="font-size:9px;color:#38bdf8;cursor:pointer;">All →</span>
        </div>
        ${_mobileSmartHomeLights.slice(0, 2).map(l => `
          <div style="display:flex;justify-content:space-between;align-items:center;font-size:10.5px;">
            <span style="color:#cbd5e1;">${l.name}</span>
            <button onclick="toggleMobileLight('${l.id}')" style="background:${l.on ? '#0284c7' : 'rgba(255,255,255,0.1)'};border:none;border-radius:10px;padding:2px 8px;font-size:9px;color:#fff;cursor:pointer;">${l.on ? 'ON' : 'OFF'}</button>
          </div>
        `).join('')}
      </div>

      <!-- Security Status Bar -->
      <div onclick="toggleMobileSecurity()" style="background:${_mobileSmartHomeSecurity === 'ARMED' ? 'rgba(16,185,129,0.12)' : 'rgba(239,68,68,0.12)'};border:1px solid ${_mobileSmartHomeSecurity === 'ARMED' ? 'rgba(16,185,129,0.3)' : 'rgba(239,68,68,0.3)'};border-radius:8px;padding:8px 10px;display:flex;justify-content:space-between;align-items:center;cursor:pointer;">
        <span style="font-size:10px;font-weight:700;color:#fff;">🛡 Security System</span>
        <span style="font-size:9.5px;font-weight:700;color:${_mobileSmartHomeSecurity === 'ARMED' ? '#34d399' : '#f87171'};">${_mobileSmartHomeSecurity} (Tap to switch)</span>
      </div>
    `;
    return;
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // 2. PROMPT & WORKFLOW MARKETPLACE (prompt_marketplace)
  // ═══════════════════════════════════════════════════════════════════════════
  if (projectType === 'prompt_marketplace') {
    if (_mobileRoute === 'tester') {
      if (titleEl) titleEl.textContent = 'Prompt Playground';
      mockContent.innerHTML = `
        <div style="display:flex;gap:4px;background:rgba(255,255,255,0.05);border-radius:8px;padding:3px;">
          ${['Gemini 1.5 Pro', 'Claude 3.5', 'GPT-4o'].map(m => `
            <span onclick="selectMobileModel('${m}')" style="flex:1;text-align:center;padding:4px 0;border-radius:6px;font-size:9.5px;font-weight:600;cursor:pointer;background:${_mobileSelectedModel === m ? '#0284c7' : 'transparent'};color:${_mobileSelectedModel === m ? '#fff' : '#94a3b8'};">${m}</span>
          `).join('')}
        </div>

        <div style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:10px;padding:10px;display:flex;flex-direction:column;gap:6px;">
          <span style="font-size:10px;font-weight:700;color:#38bdf8;text-transform:uppercase;">Interpolate Variable</span>
          <input id="mprompt-topic" type="text" value="Cloud Native Microservices" placeholder="Target Topic / Architecture" style="background:#1e293b;border:1px solid #334155;border-radius:6px;padding:6px 8px;color:#fff;font-size:10.5px;outline:none;" />
          <button onclick="runMobilePromptSim()" style="background:linear-gradient(135deg, #0284c7, #38bdf8);border:none;border-radius:6px;padding:7px;color:#fff;font-weight:700;font-size:11px;cursor:pointer;margin-top:2px;">⚡ Execute Prompt</button>
        </div>

        <div id="mprompt-sim-output" style="background:#080e21;border:1px solid rgba(56,189,248,0.25);border-radius:10px;padding:10px;font-size:10px;min-height:90px;max-height:140px;overflow-y:auto;">
          <span style="color:#64748b;font-style:italic;">Output stream will appear here upon execution…</span>
        </div>
      `;
      return;
    }

    if (_mobileRoute === 'pipelines') {
      if (titleEl) titleEl.textContent = 'Workflow Pipelines';
      mockContent.innerHTML = `
        <div style="background:linear-gradient(135deg, rgba(56,189,248,0.12), rgba(129,140,248,0.1));border:1px solid rgba(56,189,248,0.3);border-radius:12px;padding:10px;">
          <div style="font-size:10px;font-weight:700;color:#38bdf8;text-transform:uppercase;">3-Stage Enterprise Pipeline</div>
          <div style="font-size:12px;font-weight:800;color:#fff;margin-top:2px;">Ingest → Reasoning → Schema Guard</div>
        </div>

        <div style="display:flex;flex-direction:column;gap:6px;">
          <div id="wf-step-1" style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.1);border-radius:8px;padding:8px 10px;font-size:10.5px;color:#e2e8f0;font-weight:600;">1. Data Extraction & Cleanse</div>
          <div id="wf-step-2" style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.1);border-radius:8px;padding:8px 10px;font-size:10.5px;color:#e2e8f0;font-weight:600;">2. LLM Synthesis & Reasoning</div>
          <div id="wf-step-3" style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.1);border-radius:8px;padding:8px 10px;font-size:10.5px;color:#e2e8f0;font-weight:600;">3. Schema Validator & JSON Guard</div>
        </div>

        <button onclick="runMobileWorkflowPipeline()" style="background:linear-gradient(135deg, #0284c7, #38bdf8);border:none;border-radius:8px;padding:8px;color:#fff;font-weight:700;font-size:11px;cursor:pointer;">▶ Execute Workflow</button>
      `;
      return;
    }

    if (_mobileRoute === 'creator') {
      if (titleEl) titleEl.textContent = 'Creator Studio';
      mockContent.innerHTML = `
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;">
          <div style="background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.1);border-radius:10px;padding:8px;">
            <div style="font-size:9px;color:#94a3b8;">Total Revenue</div>
            <div style="font-size:15px;font-weight:800;color:#34d399;margin-top:2px;">$1,420.00</div>
          </div>
          <div style="background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.1);border-radius:10px;padding:8px;">
            <div style="font-size:9px;color:#94a3b8;">Downloads</div>
            <div style="font-size:15px;font-weight:800;color:#38bdf8;margin-top:2px;">3,840</div>
          </div>
        </div>

        <button onclick="openPublishPromptModal()" style="background:linear-gradient(135deg, #0284c7, #38bdf8);border:none;border-radius:8px;padding:8px;color:#fff;font-weight:700;font-size:11px;cursor:pointer;">+ Publish New Prompt</button>

        <div style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:10px;padding:10px;">
          <div style="font-size:10px;font-weight:700;color:#e2e8f0;margin-bottom:6px;">My Published Assets</div>
          <div style="display:flex;flex-direction:column;gap:6px;">
            <div style="display:flex;justify-content:space-between;align-items:center;font-size:10.5px;">
              <span style="color:#fff;font-weight:600;">Full-Stack Spec Gen</span>
              <span style="color:#34d399;font-weight:700;">★ 4.9 (342)</span>
            </div>
            <div style="display:flex;justify-content:space-between;align-items:center;font-size:10.5px;">
              <span style="color:#fff;font-weight:600;">SQL Optimizer Pro</span>
              <span style="color:#38bdf8;font-weight:700;">★ 4.8 (218)</span>
            </div>
          </div>
        </div>
      `;
      return;
    }

    // Default: 'home' / Prompt Feed
    if (titleEl) titleEl.textContent = 'Prompt Catalog';
    let filteredPrompts = _mobilePrompts.filter(p => {
      const matchSearch = !_mobilePromptSearch || p.title.toLowerCase().includes(_mobilePromptSearch) || p.category.toLowerCase().includes(_mobilePromptSearch);
      const matchCat = _mobilePromptCategoryFilter === 'All' || p.category === _mobilePromptCategoryFilter;
      return matchSearch && matchCat;
    });

    mockContent.innerHTML = `
      <div style="display:flex;gap:6px;align-items:center;">
        <input type="text" placeholder="Search prompts..." value="${_mobilePromptSearch}" oninput="filterMobilePrompts(this.value)" style="flex:1;background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.12);border-radius:8px;padding:6px 10px;color:#fff;font-size:10.5px;outline:none;" />
        <button onclick="openPublishPromptModal()" style="background:linear-gradient(135deg, #0284c7, #38bdf8);border:none;border-radius:8px;padding:6px 10px;color:#fff;font-weight:700;font-size:11px;cursor:pointer;" title="Publish">+</button>
      </div>

      <div style="display:flex;gap:5px;overflow-x:auto;padding-bottom:2px;">
        ${['All', 'Coding', 'Data', 'Marketing', 'Vision'].map(c => `
          <span onclick="setPromptCategory('${c}')" style="background:${_mobilePromptCategoryFilter === c ? '#0284c7' : 'rgba(255,255,255,0.06)'};color:${_mobilePromptCategoryFilter === c ? '#fff' : '#94a3b8'};padding:3px 8px;border-radius:12px;font-size:9.5px;font-weight:600;cursor:pointer;white-space:nowrap;">${c}</span>
        `).join('')}
      </div>

      <div style="display:flex;flex-direction:column;gap:6px;">
        ${filteredPrompts.map(p => `
          <div onclick="openMobilePromptModal(${p.id})" style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:10px;padding:9px;cursor:pointer;">
            <div style="display:flex;justify-content:space-between;align-items:flex-start;">
              <span style="font-size:9px;font-weight:700;color:#38bdf8;text-transform:uppercase;">${p.category}</span>
              <span style="font-size:9px;font-weight:700;color:${p.price === 'FREE' ? '#34d399' : '#fbbf24'};background:rgba(255,255,255,0.06);padding:1px 5px;border-radius:4px;">${p.price}</span>
            </div>
            <div style="font-weight:700;font-size:11px;color:#fff;margin-top:2px;">${p.title}</div>
            <div style="display:flex;justify-content:space-between;align-items:center;margin-top:6px;">
              <span style="font-size:8.5px;color:#94a3b8;">★ ${p.stars} (${p.forks} forks)</span>
              <div style="display:flex;gap:4px;" onclick="event.stopPropagation()">
                <button onclick="copyMobilePrompt(${p.id})" style="background:rgba(255,255,255,0.08);border:none;border-radius:4px;padding:2px 6px;color:#fff;font-size:8.5px;cursor:pointer;">Copy</button>
                <button onclick="forkMobilePrompt(${p.id})" style="background:linear-gradient(135deg, #0284c7, #38bdf8);border:none;border-radius:4px;padding:2px 6px;color:#fff;font-size:8.5px;font-weight:700;cursor:pointer;">Fork</button>
              </div>
            </div>
          </div>
        `).join('')}
      </div>
    `;
    return;
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // 3. EXECUTIVE ANALYTICS & BI HUB (analytics_hub)
  // ═══════════════════════════════════════════════════════════════════════════
  if (projectType === 'analytics_hub') {
    if (_mobileRoute === 'trends') {
      if (titleEl) titleEl.textContent = 'Revenue & Trends';
      mockContent.innerHTML = `
        <div style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:12px;padding:10px;">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
            <span style="font-size:10px;font-weight:700;color:#e2e8f0;">Monthly Revenue (2026)</span>
            <span style="font-size:9px;color:#38bdf8;">$476.5k Total</span>
          </div>
          <div style="height:58px;display:flex;align-items:flex-end;justify-content:space-between;gap:6px;padding:0 4px;">
            ${[
              { m: 'Jan', v: '$65k', h: 32 },
              { m: 'Feb', v: '$110k', h: 46 },
              { m: 'Mar', v: '$145k', h: 56 },
              { m: 'Apr', v: '$92k', h: 40 },
              { m: 'May', v: '$64.5k', h: 30 }
            ].map(item => `
              <div style="flex:1;display:flex;flex-direction:column;align-items:center;gap:3px;">
                <div style="width:100%;height:${item.h}px;background:${item.m === 'Mar' ? 'linear-gradient(to top, #0284c7, #38bdf8)' : 'rgba(56,189,248,0.45)'};border-radius:3px;"></div>
                <span style="font-size:8px;color:${item.m === 'Mar' ? '#38bdf8' : '#64748b'};font-weight:${item.m === 'Mar' ? '700' : '500'};">${item.m}</span>
              </div>
            `).join('')}
          </div>
        </div>

        <div style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:12px;padding:10px;display:flex;flex-direction:column;gap:6px;">
          <span style="font-size:10px;font-weight:700;color:#38bdf8;text-transform:uppercase;">Pareto Distribution</span>
          ${[
            { cat: 'Cloud Architecture', pct: 49.1, amt: '$234,000' },
            { cat: 'AI & ML Pipelines', pct: 30.2, amt: '$144,000' },
            { cat: 'Enterprise ERP', pct: 16.7, amt: '$79,500' },
            { cat: 'Security & Audit', pct: 4.0, amt: '$19,000' }
          ].map(p => `
            <div style="font-size:9.5px;">
              <div style="display:flex;justify-content:space-between;color:#e2e8f0;margin-bottom:2px;">
                <span>${p.cat}</span>
                <span style="font-weight:700;color:#38bdf8;">${p.amt} (${p.pct}%)</span>
              </div>
              <div style="width:100%;height:4px;background:rgba(255,255,255,0.08);border-radius:2px;overflow:hidden;">
                <div style="width:${p.pct}%;height:100%;background:#38bdf8;"></div>
              </div>
            </div>
          `).join('')}
        </div>
      `;
      return;
    }

    if (_mobileRoute === 'pivot') {
      if (titleEl) titleEl.textContent = '2D Pivot Matrix';
      mockContent.innerHTML = `
        <div style="font-size:10px;font-weight:700;color:#38bdf8;text-transform:uppercase;margin-bottom:2px;">Region × Category Matrix</div>
        <div style="display:flex;flex-direction:column;gap:6px;">
          <div style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:10px;padding:8px;">
            <div style="display:flex;justify-content:space-between;align-items:center;font-weight:700;font-size:10.5px;color:#fff;border-bottom:1px solid rgba(255,255,255,0.05);padding-bottom:4px;">
              <span>North America</span>
              <span style="color:#34d399;">$284,500</span>
            </div>
            <div style="display:flex;justify-content:space-between;font-size:9px;color:#94a3b8;margin-top:4px;">
              <span>Cloud: $185k • AI: $64.5k • ERP: $35k</span>
            </div>
          </div>

          <div style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:10px;padding:8px;">
            <div style="display:flex;justify-content:space-between;align-items:center;font-weight:700;font-size:10.5px;color:#fff;border-bottom:1px solid rgba(255,255,255,0.05);padding-bottom:4px;">
              <span>Europe</span>
              <span style="color:#38bdf8;">$128,000</span>
            </div>
            <div style="display:flex;justify-content:space-between;font-size:9px;color:#94a3b8;margin-top:4px;">
              <span>Cloud: $49k • AI: $54.5k • ERP: $24.5k</span>
            </div>
          </div>

          <div style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:10px;padding:8px;">
            <div style="display:flex;justify-content:space-between;align-items:center;font-weight:700;font-size:10.5px;color:#fff;border-bottom:1px solid rgba(255,255,255,0.05);padding-bottom:4px;">
              <span>Asia Pacific</span>
              <span style="color:#fbbf24;">$64,000</span>
            </div>
            <div style="display:flex;justify-content:space-between;font-size:9px;color:#94a3b8;margin-top:4px;">
              <span>AI: $25k • ERP: $20k • Security: $19k</span>
            </div>
          </div>
        </div>
      `;
      return;
    }

    if (_mobileRoute === 'export') {
      if (titleEl) titleEl.textContent = 'Export Reports';
      mockContent.innerHTML = `
        <div style="background:#080e21;border:1px solid #1e293b;border-radius:10px;padding:10px;font-family:monospace;font-size:9.5px;color:#38bdf8;line-height:1.4;max-height:160px;overflow-y:auto;">
# Executive Analytics Report
Gross Revenue: $476,500.00
Deals: 8 Total (6 Closed Won, 2 Pending)
Win Rate: 75.0%
Avg Deal: $59,562.50

Top Driver: Cloud Architecture (49.1%)
        </div>

        <div style="display:flex;gap:6px;margin-top:2px;">
          <button onclick="copyExecutiveReportMarkdown()" style="flex:1;background:linear-gradient(135deg, #0284c7, #38bdf8);border:none;border-radius:8px;padding:8px;color:#fff;font-weight:700;font-size:10.5px;cursor:pointer;">📋 Copy Markdown</button>
          <button onclick="exportExecutiveCSV()" style="flex:1;background:rgba(255,255,255,0.08);border:none;border-radius:8px;padding:8px;color:#fff;font-weight:600;font-size:10.5px;cursor:pointer;">📥 Export CSV</button>
        </div>
      `;
      return;
    }

    // Default: 'home' / BI Overview
    if (titleEl) titleEl.textContent = 'Executive BI Hub';
    mockContent.innerHTML = `
      <div style="background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.1);border-radius:12px;padding:12px;">
        <div style="font-size:9.5px;font-weight:700;color:#38bdf8;text-transform:uppercase;">Gross Revenue KPI</div>
        <div style="font-size:22px;font-weight:800;color:#ffffff;margin-top:2px;">$476,500</div>
        <div style="font-size:9.5px;color:#34d399;margin-top:2px;">↑ +23.8% MoM • 8 Closed &amp; Pending Deals</div>
      </div>

      <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;">
        <div style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:10px;padding:8px;">
          <div style="font-size:9px;color:#94a3b8;">Win Rate</div>
          <div style="font-size:14px;font-weight:700;color:#34d399;margin-top:2px;">75.0%</div>
        </div>
        <div style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:10px;padding:8px;">
          <div style="font-size:9px;color:#94a3b8;">Avg Deal</div>
          <div style="font-size:14px;font-weight:700;color:#38bdf8;margin-top:2px;">$59,562</div>
        </div>
      </div>

      <div style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:10px;padding:10px;">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
          <span style="font-size:10px;font-weight:700;color:#e2e8f0;">Top Pipeline Drivers</span>
          <span onclick="setMobileRoute('trends')" style="font-size:9px;color:#38bdf8;cursor:pointer;">Trends →</span>
        </div>
        <div style="display:flex;flex-direction:column;gap:5px;font-size:10px;">
          <div style="display:flex;justify-content:space-between;color:#fff;">
            <span>Cloud Enterprise</span>
            <span style="color:#38bdf8;font-weight:700;">$234,000 (49%)</span>
          </div>
          <div style="display:flex;justify-content:space-between;color:#fff;">
            <span>AI Reasoning Studio</span>
            <span style="color:#34d399;font-weight:700;">$144,000 (30%)</span>
          </div>
        </div>
      </div>
    `;
    return;
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // 4. INVENTORY & ITEM MANAGER (item_manager)
  // ═══════════════════════════════════════════════════════════════════════════
  if (projectType === 'item_manager') {
    if (_mobileRoute === 'stock') {
      if (titleEl) titleEl.textContent = 'Stock Metrics';
      const totalUnits = _mobileInventoryItems.reduce((s, i) => s + (i.stock || 0), 0);
      const totalValuation = _mobileInventoryItems.reduce((s, i) => s + (i.stock * i.price), 0);
      const lowStockCount = _mobileInventoryItems.filter(i => i.stock <= i.minStock).length;

      mockContent.innerHTML = `
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;">
          <div style="background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.1);border-radius:10px;padding:8px;">
            <div style="font-size:9px;color:#94a3b8;">Total Units</div>
            <div style="font-size:15px;font-weight:800;color:#38bdf8;margin-top:2px;">${totalUnits}</div>
          </div>
          <div style="background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.1);border-radius:10px;padding:8px;">
            <div style="font-size:9px;color:#94a3b8;">Inventory Value</div>
            <div style="font-size:15px;font-weight:800;color:#34d399;margin-top:2px;">$${totalValuation.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})}</div>
          </div>
        </div>

        <div style="background:${lowStockCount > 0 ? 'rgba(245,158,11,0.1)' : 'rgba(16,185,129,0.1)'};border:1px solid ${lowStockCount > 0 ? 'rgba(245,158,11,0.3)' : 'rgba(16,185,129,0.3)'};border-radius:10px;padding:10px;">
          <div style="font-size:10px;font-weight:700;color:${lowStockCount > 0 ? '#fbbf24' : '#34d399'};">⚠️ ${lowStockCount} Low Stock Alert(s)</div>
          <div style="font-size:9px;color:#94a3b8;margin-top:2px;">Standing Desk 60" is below minimum threshold (12/15 units).</div>
          <button onclick="reorderMobileStock(2)" style="margin-top:6px;background:linear-gradient(135deg, #0284c7, #38bdf8);border:none;border-radius:6px;padding:6px 10px;color:#fff;font-weight:700;font-size:10px;cursor:pointer;">⚡ Reorder 50 Units</button>
        </div>
      `;
      return;
    }

    if (_mobileRoute === 'add_sku') {
      if (titleEl) titleEl.textContent = 'Add SKU Item';
      mockContent.innerHTML = `
        <div style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:12px;padding:10px;display:flex;flex-direction:column;gap:8px;">
          <div>
            <label style="font-size:9.5px;color:#94a3b8;display:block;margin-bottom:2px;">Item Name</label>
            <input id="msku-name" type="text" placeholder="e.g. Ergonomic Monitor Arm" style="width:100%;box-sizing:border-box;background:#1e293b;border:1px solid #334155;border-radius:6px;padding:6px;color:#fff;font-size:10.5px;" />
          </div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;">
            <div>
              <label style="font-size:9.5px;color:#94a3b8;display:block;margin-bottom:2px;">SKU</label>
              <input id="msku-code" type="text" placeholder="ARM-006" style="width:100%;box-sizing:border-box;background:#1e293b;border:1px solid #334155;border-radius:6px;padding:6px;color:#fff;font-size:10.5px;" />
            </div>
            <div>
              <label style="font-size:9.5px;color:#94a3b8;display:block;margin-bottom:2px;">Category</label>
              <select id="msku-cat" style="width:100%;box-sizing:border-box;background:#1e293b;border:1px solid #334155;border-radius:6px;padding:6px;color:#fff;font-size:10.5px;">
                <option value="Furniture">Furniture</option>
                <option value="Electronics">Electronics</option>
                <option value="Accessories">Accessories</option>
              </select>
            </div>
          </div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;">
            <div>
              <label style="font-size:9.5px;color:#94a3b8;display:block;margin-bottom:2px;">Price ($)</label>
              <input id="msku-price" type="number" placeholder="89.99" style="width:100%;box-sizing:border-box;background:#1e293b;border:1px solid #334155;border-radius:6px;padding:6px;color:#fff;font-size:10.5px;" />
            </div>
            <div>
              <label style="font-size:9.5px;color:#94a3b8;display:block;margin-bottom:2px;">Initial Units</label>
              <input id="msku-stock" type="number" placeholder="30" style="width:100%;box-sizing:border-box;background:#1e293b;border:1px solid #334155;border-radius:6px;padding:6px;color:#fff;font-size:10.5px;" />
            </div>
          </div>
          <button onclick="saveNewSkuFromModal()" style="background:linear-gradient(135deg, #0284c7, #38bdf8);border:none;border-radius:6px;padding:8px;color:#fff;font-weight:700;font-size:11px;cursor:pointer;margin-top:2px;">+ Save Item to SQLite</button>
        </div>
      `;
      return;
    }

    if (_mobileRoute === 'settings') {
      if (titleEl) titleEl.textContent = 'Inventory Settings';
      mockContent.innerHTML = `
        <div style="background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.08);border-radius:12px;padding:10px;">
          <div style="font-weight:700;font-size:11.5px;color:#fff;">Bay Area Warehouse B-4</div>
          <div style="font-size:9px;color:#94a3b8;margin-top:2px;">SQLite Database Sync: Active</div>
        </div>
        <button onclick="showMobileToast('📷 Barcode Scanner Active…'); setTimeout(() => showMobileToast('✓ Scanned SKU: DESK-002'), 800);" style="background:rgba(56,189,248,0.15);border:1px solid rgba(56,189,248,0.3);border-radius:8px;padding:8px;color:#38bdf8;font-size:10.5px;font-weight:700;cursor:pointer;">📷 Simulate Barcode Scan</button>
      `;
      return;
    }

    // Default: 'home' / Items List
    if (titleEl) titleEl.textContent = 'Item Catalog';
    let filteredItems = _mobileInventoryItems.filter(i => {
      const matchSearch = !_mobileInventorySearch || i.name.toLowerCase().includes(_mobileInventorySearch) || i.sku.toLowerCase().includes(_mobileInventorySearch);
      const matchCat = _mobileInventoryFilter === 'All' || i.category === _mobileInventoryFilter;
      return matchSearch && matchCat;
    });

    mockContent.innerHTML = `
      <div style="display:flex;gap:6px;align-items:center;">
        <input type="text" placeholder="Search SKU or name..." value="${_mobileInventorySearch}" oninput="filterMobileInventory(this.value)" style="flex:1;background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.12);border-radius:8px;padding:6px 10px;color:#fff;font-size:10.5px;outline:none;" />
        <button onclick="openMobileAddSkuModal()" style="background:linear-gradient(135deg, #0284c7, #38bdf8);border:none;border-radius:8px;padding:6px 10px;color:#fff;font-weight:700;font-size:11px;cursor:pointer;" title="Add SKU">+</button>
      </div>

      <div style="display:flex;gap:5px;overflow-x:auto;padding-bottom:2px;">
        ${['All', 'Furniture', 'Electronics', 'Accessories'].map(c => `
          <span onclick="setInventoryFilter('${c}')" style="background:${_mobileInventoryFilter === c ? '#0284c7' : 'rgba(255,255,255,0.06)'};color:${_mobileInventoryFilter === c ? '#fff' : '#94a3b8'};padding:3px 8px;border-radius:12px;font-size:9.5px;font-weight:600;cursor:pointer;white-space:nowrap;">${c}</span>
        `).join('')}
      </div>

      <div style="display:flex;flex-direction:column;gap:6px;">
        ${filteredItems.map(item => `
          <div style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:10px;padding:9px;">
            <div style="display:flex;justify-content:space-between;align-items:flex-start;">
              <div>
                <span style="font-size:8.5px;color:#94a3b8;font-weight:700;">${item.sku} • ${item.category}</span>
                <div style="font-weight:700;font-size:11px;color:#fff;margin-top:1px;">${item.name}</div>
              </div>
              <span style="color:#38bdf8;font-weight:800;font-size:11px;">$${item.price.toFixed(2)}</span>
            </div>
            <div style="display:flex;justify-content:space-between;align-items:center;margin-top:6px;">
              <span style="font-size:9px;color:${item.stock <= item.minStock ? '#fbbf24' : '#34d399'};font-weight:700;">
                ${item.stock} in stock ${item.stock <= item.minStock ? '⚠️ Low' : '✓'}
              </span>
              <div style="display:flex;gap:4px;align-items:center;">
                <button onclick="adjustMobileStock(${item.id}, -1)" style="width:20px;height:20px;border-radius:4px;background:rgba(255,255,255,0.08);border:none;color:#fff;font-size:11px;font-weight:700;cursor:pointer;">−</button>
                <button onclick="adjustMobileStock(${item.id}, 1)" style="width:20px;height:20px;border-radius:4px;background:linear-gradient(135deg, #0284c7, #38bdf8);border:none;color:#fff;font-size:11px;font-weight:700;cursor:pointer;">+</button>
              </div>
            </div>
          </div>
        `).join('')}
      </div>
    `;
    return;
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // 5. CONSTRUCTION PROJECT MANAGER (construction)
  // ═══════════════════════════════════════════════════════════════════════════
  if (projectType === 'construction') {
    if (_mobileRoute === 'jobs') {
      if (titleEl) titleEl.textContent = 'Site Job Orders';
      mockContent.innerHTML = `
        <div style="display:flex;flex-direction:column;gap:6px;">
          ${_mobileConstructionJobs.map(j => `
            <div style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:10px;padding:10px;">
              <div style="display:flex;justify-content:space-between;align-items:center;">
                <span style="font-weight:700;font-size:11px;color:#fff;">${j.name}</span>
                <span style="font-size:9px;font-weight:700;color:${j.badgeColor};background:rgba(255,255,255,0.06);padding:2px 6px;border-radius:4px;">${j.status}</span>
              </div>
              <button onclick="advanceConstructionJob(${j.id})" style="margin-top:6px;width:100%;background:rgba(56,189,248,0.12);border:1px solid rgba(56,189,248,0.25);border-radius:6px;padding:4px;color:#38bdf8;font-size:9.5px;font-weight:700;cursor:pointer;">Advance Status →</button>
            </div>
          `).join('')}
        </div>
      `;
      return;
    }

    if (_mobileRoute === 'safety') {
      if (titleEl) titleEl.textContent = 'OSHA Safety & Compliance';
      mockContent.innerHTML = `
        <div style="background:linear-gradient(135deg, rgba(16,185,129,0.15), rgba(2,132,199,0.1));border:1px solid rgba(16,185,129,0.3);border-radius:12px;padding:10px;">
          <div style="font-size:9.5px;font-weight:700;color:#34d399;text-transform:uppercase;">Zero Incidents Streak</div>
          <div style="font-size:20px;font-weight:800;color:#fff;margin-top:2px;">142 Days Safe</div>
          <div style="font-size:9px;color:#94a3b8;margin-top:2px;">OSHA 1926 Compliance Score: <span style="color:#38bdf8;font-weight:700;">99.4%</span></div>
        </div>

        <div style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:10px;padding:10px;">
          <div style="font-size:10px;font-weight:700;color:#e2e8f0;margin-bottom:6px;">Daily Site Inspection Checklist</div>
          <div style="display:flex;flex-direction:column;gap:5px;">
            ${_mobileSafetyChecklist.map(item => `
              <div onclick="toggleSafetyCheck(${item.id})" style="display:flex;align-items:center;gap:6px;font-size:9.5px;color:#cbd5e1;cursor:pointer;">
                <span style="color:${item.done ? '#34d399' : '#94a3b8'};font-weight:700;">${item.done ? '☑' : '☐'}</span>
                <span style="${item.done ? 'text-decoration:none;' : 'color:#94a3b8;'}">${item.task}</span>
              </div>
            `).join('')}
          </div>
        </div>
      `;
      return;
    }

    if (_mobileRoute === 'materials') {
      if (titleEl) titleEl.textContent = 'Jobsite Materials';
      const materials = [
        { name: 'Rebar Grade 60 (Tons)', qty: '45 / 50', status: 'In Stock', color: '#34d399' },
        { name: 'Portland Cement Type II (Bags)', qty: '800 / 1000', status: 'In Stock', color: '#34d399' },
        { name: 'Ready-mix Concrete (yd³)', qty: '250 / 300', status: 'Scheduled', color: '#38bdf8' },
        { name: 'Structural Steel I-Beams', qty: '12 / 60', status: 'Low Stock', color: '#fbbf24' }
      ];

      mockContent.innerHTML = `
        <div style="display:flex;flex-direction:column;gap:6px;">
          ${materials.map(m => `
            <div style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:10px;padding:9px;display:flex;justify-content:space-between;align-items:center;">
              <div>
                <div style="font-size:10.5px;font-weight:700;color:#fff;">${m.name}</div>
                <div style="font-size:9px;color:#94a3b8;">${m.qty}</div>
              </div>
              <span style="font-size:9px;font-weight:700;color:${m.color};background:rgba(255,255,255,0.06);padding:2px 6px;border-radius:4px;">${m.status}</span>
            </div>
          `).join('')}
        </div>
      `;
      return;
    }

    // Default: 'home' / Projects List
    if (titleEl) titleEl.textContent = 'Active Projects';
    mockContent.innerHTML = `
      <div style="display:flex;flex-direction:column;gap:8px;">
        ${_mobileConstructionProjects.map(p => `
          <div style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:10px;padding:10px;">
            <div style="display:flex;justify-content:space-between;align-items:flex-start;">
              <div>
                <div style="font-weight:700;font-size:11.5px;color:#fff;">${p.name}</div>
                <div style="font-size:9px;color:#94a3b8;">Foreman: ${p.foreman} • Due ${p.deadline}</div>
              </div>
              <span style="font-size:10.5px;font-weight:800;color:#38bdf8;">${p.progress}%</span>
            </div>
            <div style="width:100%;height:4px;background:rgba(255,255,255,0.08);border-radius:2px;overflow:hidden;margin:6px 0;">
              <div style="width:${p.progress}%;height:100%;background:linear-gradient(90deg, #0284c7, #38bdf8);"></div>
            </div>
            <div style="display:flex;justify-content:space-between;font-size:9px;color:#94a3b8;">
              <span>Spent: $${(p.spent / 1000000).toFixed(1)}M</span>
              <span>Budget: $${(p.budget / 1000000).toFixed(1)}M</span>
            </div>
          </div>
        `).join('')}
      </div>
    `;
    return;
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // 6. CRM & SALES PIPELINE HUB (sales_hub / crm / default)
  // ═══════════════════════════════════════════════════════════════════════════
  if (_mobileRoute === 'deals') {
    if (titleEl) titleEl.textContent = 'Pipeline Deals';
    
    let filtered = _mobileDeals.filter(d => {
      const matchSearch = !_mobileSearchQuery || d.name.toLowerCase().includes(_mobileSearchQuery) || d.category.toLowerCase().includes(_mobileSearchQuery);
      const matchFilter = _mobileFilter === 'All' || d.stage.toLowerCase().includes(_mobileFilter.toLowerCase());
      return matchSearch && matchFilter;
    });

    const filterChips = ['All', 'Discovery', 'Proposal', 'Negotiation', 'Won'];
    const chipsHtml = filterChips.map(f => {
      const active = (_mobileFilter === f || (_mobileFilter === 'All' && f === 'All'));
      const bg = active ? '#0284c7' : 'rgba(255,255,255,0.06)';
      const color = active ? '#fff' : '#94a3b8';
      return `<span onclick="setDealFilter('${f}')" style="background:${bg};color:${color};padding:3px 8px;border-radius:12px;font-size:9.5px;font-weight:600;cursor:pointer;white-space:nowrap;transition:all .12s;">${f}</span>`;
    }).join('');

    const dealsListHtml = filtered.length > 0 ? filtered.map(d => `
      <div onclick="openDealDetailModal(${d.id})" style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:10px;padding:10px;display:flex;justify-content:space-between;align-items:center;cursor:pointer;transition:background .12s;" onmouseover="this.style.background='rgba(255,255,255,0.08)'" onmouseout="this.style.background='rgba(255,255,255,0.04)'">
        <div style="flex:1;overflow:hidden;padding-right:6px;">
          <div style="display:flex;align-items:center;gap:5px;">
            <span style="font-weight:600;font-size:11px;color:#fff;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${d.name}</span>
          </div>
          <div style="display:flex;gap:6px;align-items:center;margin-top:2px;">
            <span style="font-size:9px;color:${d.color};font-weight:700;">${d.stage}</span>
            <span style="font-size:8.5px;color:#64748b;">• ${d.date}</span>
          </div>
        </div>
        <div style="text-align:right;">
          <div style="color:#38bdf8;font-weight:800;font-size:11.5px;">$${d.amount.toLocaleString()}</div>
          <span style="font-size:8.5px;color:#94a3b8;">${d.category}</span>
        </div>
      </div>
    `).join('') : `
      <div style="text-align:center;padding:30px 10px;color:#64748b;font-size:11px;">
        No deals match your filter.<br>
        <button onclick="setDealFilter('All'); filterMobileDeals('');" style="margin-top:6px;background:none;border:none;color:#38bdf8;cursor:pointer;font-size:10.5px;text-decoration:underline;">Clear filters</button>
      </div>
    `;

    mockContent.innerHTML = `
      <div style="display:flex;gap:6px;align-items:center;">
        <input type="text" placeholder="Search deals..." value="${_mobileSearchQuery}" oninput="filterMobileDeals(this.value)" style="flex:1;background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.12);border-radius:8px;padding:6px 10px;color:#fff;font-size:10.5px;outline:none;" />
        <button onclick="openNewDealModal()" style="background:linear-gradient(135deg, #0284c7, #38bdf8);border:none;border-radius:8px;padding:6px 10px;color:#fff;font-weight:700;font-size:11px;cursor:pointer;" title="Add deal">+</button>
      </div>

      <div style="display:flex;gap:5px;overflow-x:auto;padding-bottom:2px;">
        ${chipsHtml}
      </div>

      <div style="display:flex;flex-direction:column;gap:6px;">
        ${dealsListHtml}
      </div>
    `;
    return;
  }

  if (_mobileRoute === 'analytics') {
    if (titleEl) titleEl.textContent = 'Performance Analytics';

    const periods = ['24h', '7d', '30d'];
    const periodHtml = periods.map(p => `
      <span onclick="setAnalyticsPeriod('${p}')" style="flex:1;text-align:center;padding:4px 0;border-radius:6px;font-size:10px;font-weight:600;cursor:pointer;background:${_mobileAnalyticsPeriod === p ? '#0284c7' : 'transparent'};color:${_mobileAnalyticsPeriod === p ? '#fff' : '#94a3b8'};">${p.toUpperCase()}</span>
    `).join('');

    const totalPipeline = _mobileDeals.reduce((s, d) => s + (d.amount || 0), 0);
    const wonCount = _mobileDeals.filter(d => d.stage === 'Closed Won').length;
    const winRate = _mobileDeals.length > 0 ? Math.round((wonCount / _mobileDeals.length) * 100) : 0;

    mockContent.innerHTML = `
      <div style="background:rgba(255,255,255,0.05);border-radius:8px;padding:3px;display:flex;">
        ${periodHtml}
      </div>

      <div style="background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.1);border-radius:12px;padding:10px;">
        <div style="font-size:9.5px;font-weight:700;color:#38bdf8;text-transform:uppercase;">Revenue Velocity</div>
        <div style="font-size:18px;font-weight:800;color:#fff;margin-top:2px;">$${(totalPipeline * 0.42).toLocaleString(undefined, {maximumFractionDigits:0})} <span style="font-size:9.5px;color:#34d399;font-weight:600;">↑ +14.2%</span></div>
        <div style="font-size:9px;color:#94a3b8;margin-top:2px;">Weekly pipeline conversion flow</div>
      </div>

      <!-- Flutter Bar Chart Visualizer -->
      <div style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:12px;padding:10px;">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
          <span style="font-size:10px;font-weight:700;color:#e2e8f0;">Deal Inflow</span>
          <span style="font-size:9px;color:#38bdf8;">Flutter CustomPainter</span>
        </div>
        <div style="height:64px;display:flex;align-items:flex-end;justify-content:space-between;gap:6px;padding:0 4px;">
          <div style="flex:1;display:flex;flex-direction:column;align-items:center;gap:3px;">
            <div style="width:100%;height:32px;background:rgba(56,189,248,0.4);border-radius:3px;"></div>
            <span style="font-size:8px;color:#64748b;">M</span>
          </div>
          <div style="flex:1;display:flex;flex-direction:column;align-items:center;gap:3px;">
            <div style="width:100%;height:48px;background:rgba(56,189,248,0.6);border-radius:3px;"></div>
            <span style="font-size:8px;color:#64748b;">T</span>
          </div>
          <div style="flex:1;display:flex;flex-direction:column;align-items:center;gap:3px;">
            <div style="width:100%;height:40px;background:rgba(56,189,248,0.5);border-radius:3px;"></div>
            <span style="font-size:8px;color:#64748b;">W</span>
          </div>
          <div style="flex:1;display:flex;flex-direction:column;align-items:center;gap:3px;">
            <div style="width:100%;height:58px;background:linear-gradient(to top, #0284c7, #38bdf8);border-radius:3px;"></div>
            <span style="font-size:8px;color:#38bdf8;font-weight:700;">T</span>
          </div>
          <div style="flex:1;display:flex;flex-direction:column;align-items:center;gap:3px;">
            <div style="width:100%;height:44px;background:rgba(56,189,248,0.55);border-radius:3px;"></div>
            <span style="font-size:8px;color:#64748b;">F</span>
          </div>
          <div style="flex:1;display:flex;flex-direction:column;align-items:center;gap:3px;">
            <div style="width:100%;height:22px;background:rgba(56,189,248,0.3);border-radius:3px;"></div>
            <span style="font-size:8px;color:#64748b;">S</span>
          </div>
        </div>
      </div>

      <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;">
        <div style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:10px;padding:8px;">
          <div style="font-size:9px;color:#94a3b8;">Win Rate</div>
          <div style="font-size:14px;font-weight:700;color:#34d399;margin-top:2px;">${winRate}%</div>
        </div>
        <div style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:10px;padding:8px;">
          <div style="font-size:9px;color:#94a3b8;">API Latency</div>
          <div style="font-size:14px;font-weight:700;color:#38bdf8;margin-top:2px;">14ms</div>
        </div>
      </div>
    `;
    return;
  }

  if (_mobileRoute === 'settings') {
    if (titleEl) titleEl.textContent = 'App Settings';
    mockContent.innerHTML = `
      <div style="background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.08);border-radius:12px;padding:10px;display:flex;align-items:center;gap:10px;">
        <div style="width:36px;height:36px;border-radius:50%;background:linear-gradient(135deg, #0284c7, #38bdf8);display:flex;align-items:center;justify-content:center;font-weight:700;font-size:13px;color:#fff;">LP</div>
        <div>
          <div style="font-weight:700;font-size:11.5px;color:#fff;">Developer Admin</div>
          <div style="font-size:9px;color:#94a3b8;">MCN Flutter Enterprise Kit</div>
        </div>
      </div>

      <div style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:12px;padding:10px;display:flex;flex-direction:column;gap:8px;">
        <div style="font-size:10px;font-weight:700;color:#38bdf8;text-transform:uppercase;">Preferences</div>
        <div style="display:flex;justify-content:space-between;align-items:center;font-size:10.5px;">
          <span style="color:#e2e8f0;">Dark Theme</span>
          <button onclick="toggleMobileTheme()" style="background:${_mobileDarkMode ? '#0284c7' : 'rgba(255,255,255,0.1)'};border:none;border-radius:10px;padding:2px 8px;font-size:9px;color:#fff;cursor:pointer;">${_mobileDarkMode ? 'ON' : 'OFF'}</button>
        </div>
        <div style="display:flex;justify-content:space-between;align-items:center;font-size:10.5px;border-top:1px solid rgba(255,255,255,0.05);padding-top:6px;">
          <span style="color:#e2e8f0;">Haptic Feedback</span>
          <button onclick="toggleMobileHaptics()" style="background:${_mobileHaptic ? '#0284c7' : 'rgba(255,255,255,0.1)'};border:none;border-radius:10px;padding:2px 8px;font-size:9px;color:#fff;cursor:pointer;">${_mobileHaptic ? 'ON' : 'OFF'}</button>
        </div>
      </div>

      <div style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:12px;padding:10px;display:flex;flex-direction:column;gap:6px;">
        <div style="font-size:10px;font-weight:700;color:#38bdf8;text-transform:uppercase;">Backend Service</div>
        <div style="font-size:9.5px;color:#94a3b8;line-height:1.4;">
          Endpoint: <code>http://localhost:8080</code><br>
          Runtime: Flutter 3.22 / Dart 3.4.0
        </div>
        <button onclick="pingMobileBackend()" style="margin-top:2px;background:rgba(56,189,248,0.15);border:1px solid rgba(56,189,248,0.3);border-radius:6px;padding:6px;color:#38bdf8;font-size:10px;font-weight:700;cursor:pointer;">Ping Backend API</button>
      </div>
    `;
    return;
  }

  // Default: 'home' route
  if (titleEl) titleEl.textContent = 'MCN Mobile Dashboard';

  const totalPipeline = _mobileDeals.reduce((s, d) => s + (d.amount || 0), 0);
  const wonCount = _mobileDeals.filter(d => d.stage === 'Closed Won').length;
  const winRate = _mobileDeals.length > 0 ? Math.round((wonCount / _mobileDeals.length) * 100) : 0;

  const recentDealsHtml = _mobileDeals.slice(0, 2).map(d => `
    <div onclick="openDealDetailModal(${d.id})" style="display:flex;justify-content:space-between;align-items:center;font-size:10.5px;border-bottom:1px solid rgba(255,255,255,0.05);padding-bottom:5px;cursor:pointer;">
      <div>
        <div style="font-weight:600;color:#fff;">${d.name}</div>
        <div style="font-size:9px;color:#94a3b8;">Stage: ${d.stage}</div>
      </div>
      <span style="color:#38bdf8;font-weight:700;">$${d.amount.toLocaleString()}</span>
    </div>
  `).join('');

  mockContent.innerHTML = `
    <div style="background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.1);border-radius:12px;padding:12px;display:flex;flex-direction:column;gap:4px;">
      <div style="font-size:9.5px;font-weight:700;color:#38bdf8;text-transform:uppercase;letter-spacing:0.04em;">Active Pipeline</div>
      <div style="font-size:20px;font-weight:800;color:#ffffff;letter-spacing:-0.02em;">$${totalPipeline.toLocaleString()}</div>
      <div style="font-size:9.5px;color:#4ade80;display:flex;align-items:center;gap:4px;">
        <span>↑ +18.4%</span>
        <span style="color:#94a3b8;">vs last month</span>
      </div>
    </div>

    <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;">
      <div style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:10px;padding:8px;">
        <div style="font-size:9px;color:#94a3b8;">Deals Won</div>
        <div style="font-size:14px;font-weight:700;color:#fff;margin-top:2px;">${wonCount}</div>
      </div>
      <div style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:10px;padding:8px;">
        <div style="font-size:9px;color:#94a3b8;">Win Rate</div>
        <div style="font-size:14px;font-weight:700;color:#38bdf8;margin-top:2px;">${winRate}%</div>
      </div>
    </div>

    <div style="display:flex;gap:6px;margin-top:2px;">
      <button class="btn btn-hero-run" onclick="syncMobileWithBackend()" style="flex:1;padding:6px;font-size:10px;border-radius:6px;justify-content:center;">⚡ Sync API</button>
      <button class="btn" onclick="openNewDealModal()" style="flex:1;padding:6px;font-size:10px;border-radius:6px;justify-content:center;background:rgba(255,255,255,0.08);color:#fff;">+ New Deal</button>
    </div>

    <div style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:10px;padding:10px;margin-top:2px;">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
        <span style="font-size:10px;font-weight:700;color:#e2e8f0;">Recent Deals</span>
        <span onclick="setMobileRoute('deals')" style="font-size:9px;color:#38bdf8;cursor:pointer;">View All →</span>
      </div>
      <div style="display:flex;flex-direction:column;gap:6px;">
        ${recentDealsHtml}
      </div>
    </div>
  `;
}

