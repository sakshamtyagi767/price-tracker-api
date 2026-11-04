// ============================================================
// PricePulse — Frontend Application
// Talks directly to the FastAPI backend REST API
// ============================================================

const API = '/api/v1';
let chartInstance = null;

// ---- State ----
const state = {
  token: localStorage.getItem('pt_token') || null,
  user: JSON.parse(localStorage.getItem('pt_user') || 'null'),
  items: [],
  deleteTargetId: null,
};

// ============================================================
// UTILITY HELPERS
// ============================================================

function $(id) { return document.getElementById(id); }

function showModal(id) {
  $(id).classList.remove('hidden');
  $(id).classList.add('flex');
}

function hideModal(id) {
  $(id).classList.add('hidden');
  $(id).classList.remove('flex');
}

function closeModalOnBg(e, id) {
  if (e.target === $(id)) hideModal(id);
}

function showToast(msg, type = 'info', duration = 3500) {
  const icons = { success: 'check-circle', error: 'x-circle', info: 'info' };
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/></svg>${msg}`;
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), duration);
}

function formatPrice(price) {
  if (price === null || price === undefined) return '—';
  return `$${parseFloat(price).toFixed(2)}`;
}

function getDomainBadge(domain) {
  const store = domain.replace('www.', '').split('.')[0];
  return `<span class="badge-domain text-xs px-2 py-0.5 rounded-full font-medium capitalize">${store}</span>`;
}

async function apiFetch(path, opts = {}) {
  const headers = { 'Content-Type': 'application/json', ...(state.token ? { Authorization: `Bearer ${state.token}` } : {}) };
  const res = await fetch(`${API}${path}`, { ...opts, headers: { ...headers, ...(opts.headers || {}) } });
  if (res.status === 204) return null;
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || 'Request failed');
  return data;
}

// ============================================================
// AUTH
// ============================================================

async function login() {
  const email = $('loginEmail').value.trim();
  const pass = $('loginPassword').value.trim();
  if (!email || !pass) return showToast('Please enter email and password', 'error');
  try {
    const form = new URLSearchParams({ username: email, password: pass });
    const res = await fetch(`${API}/auth/login`, { method: 'POST', body: form });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail);
    state.token = data.access_token;
    localStorage.setItem('pt_token', state.token);
    hideModal('loginModal');
    await fetchUser();
    showToast('Welcome back! 👋', 'success');
  } catch (e) { showToast(e.message, 'error'); }
}

async function register() {
  const email = $('regEmail').value.trim();
  const pass = $('regPassword').value.trim();
  const tier = $('regTier').value;
  if (!email || !pass) return showToast('Please fill all fields', 'error');
  if (pass.length < 8) return showToast('Password must be at least 8 characters', 'error');
  try {
    await apiFetch('/auth/register', { method: 'POST', body: JSON.stringify({ email, password: pass, tier }) });
    showToast('Account created! Logging you in...', 'success');
    $('loginEmail').value = email;
    $('loginPassword').value = pass;
    hideModal('registerModal');
    await login();
  } catch (e) { showToast(e.message, 'error'); }
}

async function demoLogin() {
  // Create a demo account if it doesn't exist, then log in
  const demoEmail = 'demo@pricepulse.dev';
  const demoPass = 'demo1234';
  try {
    await apiFetch('/auth/register', { method: 'POST', body: JSON.stringify({ email: demoEmail, password: demoPass, tier: 'FREE' }) });
  } catch (_) { /* Already exists */ }
  $('loginEmail').value = demoEmail;
  $('loginPassword').value = demoPass;
  await login();
}

function logout() {
  state.token = null;
  state.user = null;
  state.items = [];
  localStorage.removeItem('pt_token');
  localStorage.removeItem('pt_user');
  renderLoggedOut();
  showToast('Logged out', 'info');
}

async function fetchUser() {
  try {
    state.user = await apiFetch('/auth/me');
    localStorage.setItem('pt_user', JSON.stringify(state.user));
    renderLoggedIn();
    await loadWatchlist();
  } catch (e) { logout(); }
}

// ============================================================
// TRACKED ITEMS
// ============================================================

async function trackItem() {
  const url = $('trackUrl').value.trim();
  const targetPrice = parseFloat($('targetPrice').value);
  const channel = $('notifChannel').value;
  if (!url) return showToast('Please paste a product URL', 'error');
  if (!targetPrice || targetPrice <= 0) return showToast('Please enter a valid target price', 'error');

  const btn = $('trackBtn');
  btn.innerHTML = '<svg class="spinner w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12a9 9 0 11-6.219-8.56"/></svg> Scraping...';
  btn.disabled = true;

  try {
    await apiFetch('/tracked-items', {
      method: 'POST',
      body: JSON.stringify({ url, target_price: targetPrice, notification_channel: channel })
    });
    $('trackUrl').value = '';
    $('targetPrice').value = '';
    showToast('Product added to your watchlist! 🎉', 'success');
    await loadWatchlist();
  } catch (e) {
    showToast(e.message, 'error');
  } finally {
    btn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg> Track Now';
    btn.disabled = false;
    lucide.createIcons();
  }
}

async function loadWatchlist() {
  try {
    state.items = await apiFetch('/tracked-items');
    renderWatchlist();
    renderStats();
    updateQuota();
  } catch (e) { showToast('Failed to load watchlist', 'error'); }
}

async function deleteItem(id) {
  state.deleteTargetId = id;
  showModal('deleteModal');
  $('confirmDeleteBtn').onclick = async () => {
    try {
      await apiFetch(`/tracked-items/${id}`, { method: 'DELETE' });
      hideModal('deleteModal');
      showToast('Removed from watchlist', 'info');
      await loadWatchlist();
    } catch (e) { showToast(e.message, 'error'); }
  };
}

async function togglePause(id, currentState) {
  try {
    await apiFetch(`/tracked-items/${id}`, {
      method: 'PATCH',
      body: JSON.stringify({ is_active: !currentState })
    });
    await loadWatchlist();
  } catch (e) { showToast(e.message, 'error'); }
}

async function triggerPoll() {
  const btn = $('pollBtn');
  btn.innerHTML = '<svg class="spinner w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12a9 9 0 11-6.219-8.56"/></svg> Polling...';
  btn.disabled = true;
  try {
    const res = await apiFetch('/analytics/trigger-poll', { method: 'POST' });
    showToast(`Background poll triggered! (${res.enqueued_tasks || 0} tasks enqueued)`, 'success');
    setTimeout(loadWatchlist, 3000);
  } catch (e) {
    showToast('Poll triggered (may need Redis running)', 'info');
  } finally {
    setTimeout(() => {
      btn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-.18-7"/></svg> Trigger Background Poll';
      btn.disabled = false;
      lucide.createIcons();
    }, 2000);
  }
}

// ============================================================
// ANALYTICS CHART
// ============================================================

async function openChart(item) {
  $('chartTitle').textContent = item.product.title || 'Price History';
  $('chartSubtitle').textContent = item.product.url;
  $('chartStats').innerHTML = '<div class="col-span-4 text-center text-slate-500 text-sm py-2">Loading analytics...</div>';
  showModal('chartModal');

  if (chartInstance) { chartInstance.destroy(); chartInstance = null; }

  try {
    const data = await apiFetch(`/analytics/products/${item.product_id}/history`);

    if (!data.prices || data.prices.length === 0) {
      $('chartStats').innerHTML = '';
      $('noHistoryMsg').classList.remove('hidden');
      return;
    }
    $('noHistoryMsg').classList.add('hidden');

    const change = data.price_change_percentage ?? 0;
    const changeColor = change <= 0 ? '#22c55e' : '#ef4444';
    const changeSym = change <= 0 ? '▼' : '▲';

    $('chartStats').innerHTML = `
      <div class="card rounded-xl p-3 text-center">
        <p class="text-xs text-slate-500 mb-1">Current</p>
        <p class="text-sm font-bold text-white">${formatPrice(data.current_price)}</p>
      </div>
      <div class="card rounded-xl p-3 text-center">
        <p class="text-xs text-slate-500 mb-1">All-Time Low</p>
        <p class="text-sm font-bold text-green-400">${formatPrice(data.min_price)}</p>
      </div>
      <div class="card rounded-xl p-3 text-center">
        <p class="text-xs text-slate-500 mb-1">All-Time High</p>
        <p class="text-sm font-bold text-red-400">${formatPrice(data.max_price)}</p>
      </div>
      <div class="card rounded-xl p-3 text-center">
        <p class="text-xs text-slate-500 mb-1">Change</p>
        <p class="text-sm font-bold" style="color:${changeColor}">${changeSym} ${Math.abs(change).toFixed(1)}%</p>
      </div>
    `;

    const labels = data.labels.map(l => {
      const d = new Date(l);
      return `${d.getMonth() + 1}/${d.getDate()} ${d.getHours()}:00`;
    });

    const ctx = document.getElementById('priceChart').getContext('2d');
    chartInstance = new Chart(ctx, {
      type: 'line',
      data: {
        labels,
        datasets: [{
          label: 'Price',
          data: data.prices,
          borderColor: '#3b82f6',
          backgroundColor: 'rgba(59, 130, 246, 0.08)',
          borderWidth: 2,
          pointBackgroundColor: data.prices.map(p => p === data.min_price ? '#22c55e' : '#3b82f6'),
          pointRadius: data.prices.map(p => p === data.min_price ? 5 : 3),
          tension: 0.4,
          fill: true,
        }, {
          label: 'Target',
          data: data.prices.map(() => item.target_price),
          borderColor: 'rgba(234, 179, 8, 0.6)',
          borderDash: [6, 3],
          borderWidth: 1.5,
          pointRadius: 0,
          fill: false,
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { labels: { color: '#94a3b8', boxWidth: 12, font: { size: 11 } } },
          tooltip: { backgroundColor: '#1e293b', titleColor: '#e2e8f0', bodyColor: '#94a3b8', borderColor: 'rgba(148,163,184,0.1)', borderWidth: 1 }
        },
        scales: {
          x: { ticks: { color: '#475569', font: { size: 10 } }, grid: { color: 'rgba(148,163,184,0.06)' } },
          y: {
            ticks: { color: '#475569', font: { size: 10 }, callback: v => `$${v}` },
            grid: { color: 'rgba(148,163,184,0.06)' }
          }
        }
      }
    });
  } catch (e) {
    $('chartStats').innerHTML = `<div class="col-span-4 text-center text-red-400 text-sm py-2">Failed to load analytics</div>`;
  }
}

// ============================================================
// RENDERING
// ============================================================

function renderWatchlist() {
  const grid = $('watchlist');
  const empty = $('emptyState');
  const badge = $('itemCountBadge');

  badge.textContent = `${state.items.length} items`;
  grid.innerHTML = '';

  if (!state.items.length) {
    empty.classList.remove('hidden');
    grid.classList.add('hidden');
    return;
  }
  empty.classList.add('hidden');
  grid.classList.remove('hidden');

  state.items.forEach(item => {
    const p = item.product;
    const isBelowTarget = p.current_price !== null && p.current_price <= item.target_price;
    const saving = isBelowTarget ? (item.target_price - p.current_price).toFixed(2) : null;

    const card = document.createElement('div');
    card.className = `card card-hover rounded-2xl overflow-hidden flex flex-col ${isBelowTarget ? 'target-met' : ''} ${!item.is_active ? 'opacity-50' : ''}`;
    card.innerHTML = `
      <div class="relative">
        ${p.image_url
          ? `<img src="${p.image_url}" alt="${p.title}" class="w-full h-36 object-cover bg-slate-800" onerror="this.style.display='none';this.nextElementSibling.style.display='flex'" />`
          : ''
        }
        <div class="${p.image_url ? 'hidden' : 'flex'} w-full h-36 bg-gradient-to-br from-slate-800 to-slate-900 items-center justify-center">
          <svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#334155" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="m7.5 4.27 9 5.15"/><path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"/></svg>
        </div>
        <div class="absolute top-2 right-2 flex gap-1">
          ${isBelowTarget ? '<span class="text-xs bg-green-500 text-white px-2 py-0.5 rounded-full font-semibold">🎯 Target Met!</span>' : ''}
          ${!item.is_active ? '<span class="text-xs bg-slate-700 text-slate-300 px-2 py-0.5 rounded-full">Paused</span>' : ''}
        </div>
      </div>
      <div class="p-4 flex flex-col flex-1">
        <div class="flex items-start justify-between gap-2 mb-2">
          ${getDomainBadge(p.domain)}
          <span class="text-xs text-slate-500 truncate">${p.last_scraped_at ? '↻ ' + new Date(p.last_scraped_at).toLocaleDateString() : 'Pending scrape'}</span>
        </div>
        <h3 class="text-sm font-semibold text-white leading-tight mb-3 line-clamp-2 flex-1" title="${p.title || ''}">
          ${p.title || 'Pending Price Fetch...'}
        </h3>
        <div class="grid grid-cols-2 gap-2 mb-3">
          <div class="bg-slate-900/60 rounded-xl p-2.5 text-center">
            <p class="text-xs text-slate-500 mb-0.5">Current</p>
            <p class="text-sm font-bold price-current ${isBelowTarget ? 'text-green-400' : 'text-white'}">${formatPrice(p.current_price)}</p>
          </div>
          <div class="bg-slate-900/60 rounded-xl p-2.5 text-center">
            <p class="text-xs text-slate-500 mb-0.5">Your Target</p>
            <p class="text-sm font-bold text-yellow-400">${formatPrice(item.target_price)}</p>
          </div>
        </div>
        ${saving ? `<div class="text-center text-xs text-green-400 font-medium mb-3 bg-green-500/10 py-1.5 rounded-lg">🎉 Saving $${saving} right now!</div>` : ''}
        <div class="flex gap-2 mt-auto">
          <button onclick='openChart(${JSON.stringify(item)})' class="flex-1 text-xs py-2 rounded-lg border border-slate-700 hover:border-blue-500/40 hover:text-blue-400 text-slate-400 transition-all flex items-center justify-center gap-1.5">
            <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg> Chart
          </button>
          <button onclick="togglePause(${item.id}, ${item.is_active})" class="text-xs py-2 px-2.5 rounded-lg border border-slate-700 hover:border-slate-500 text-slate-400 hover:text-white transition-all">
            ${item.is_active
              ? '<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect width="4" height="16" x="6" y="4"/><rect width="4" height="16" x="14" y="4"/></svg>'
              : '<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"/></svg>'
            }
          </button>
          <button onclick="deleteItem(${item.id})" class="text-xs py-2 px-2.5 rounded-lg border border-slate-700 hover:border-red-500/40 text-slate-400 hover:text-red-400 transition-all">
            <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/></svg>
          </button>
        </div>
      </div>
    `;
    grid.appendChild(card);
  });
}

function renderStats() {
  const active = state.items.filter(i => i.is_active).length;
  const targetMet = state.items.filter(i => i.product.current_price !== null && i.product.current_price <= i.target_price).length;
  const totalSavings = state.items.reduce((acc, i) => {
    if (i.product.current_price !== null && i.product.current_price < i.target_price) {
      acc += (i.target_price - i.product.current_price);
    }
    return acc;
  }, 0);

  $('statsRow').innerHTML = `
    <div class="card rounded-xl p-4">
      <div class="flex items-center gap-2 mb-1"><svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#60a5fa" stroke-width="2"><path d="M2.5 2h1.4L6 14h12l2-7H6"/><circle cx="10" cy="20" r="1"/><circle cx="17" cy="20" r="1"/></svg><p class="text-xs text-slate-500">Tracking</p></div>
      <p class="text-2xl font-bold text-white">${active}</p>
      <p class="text-xs text-slate-500">active items</p>
    </div>
    <div class="card rounded-xl p-4">
      <div class="flex items-center gap-2 mb-1"><svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#22c55e" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/></svg><p class="text-xs text-slate-500">Target Met</p></div>
      <p class="text-2xl font-bold text-green-400">${targetMet}</p>
      <p class="text-xs text-slate-500">buy opportunities</p>
    </div>
    <div class="card rounded-xl p-4">
      <div class="flex items-center gap-2 mb-1"><svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#facc15" stroke-width="2"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg><p class="text-xs text-slate-500">Potential Savings</p></div>
      <p class="text-2xl font-bold text-yellow-400">$${totalSavings.toFixed(0)}</p>
      <p class="text-xs text-slate-500">if you buy now</p>
    </div>
    <div class="card rounded-xl p-4">
      <div class="flex items-center gap-2 mb-1"><svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#c084fc" stroke-width="2"><path d="M18 20V10"/><path d="M12 20V4"/><path d="M6 20v-6"/></svg><p class="text-xs text-slate-500">Quota Used</p></div>
      <p class="text-2xl font-bold text-purple-400">${state.user ? Math.round((active / state.user.quota_limit) * 100) : 0}%</p>
      <p class="text-xs text-slate-500">${state.user ? state.user.tier : ''} tier</p>
    </div>
  `;
}

function updateQuota() {
  if (!state.user) return;
  const active = state.items.filter(i => i.is_active).length;
  const pct = Math.min((active / state.user.quota_limit) * 100, 100);
  $('quotaText').textContent = `${active} / ${state.user.quota_limit}`;
  $('quotaBar').style.width = `${pct}%`;
  $('quotaDisplay').classList.remove('hidden');
  $('quotaDisplay').classList.add('flex');
}

function renderLoggedIn() {
  $('heroSection').classList.add('hidden');
  $('dashboard').classList.remove('hidden');
  $('dashboard').classList.add('block');
  $('authButtons').classList.add('hidden');
  $('userMenu').classList.remove('hidden');
  $('userMenu').classList.add('flex');
  $('tierBadge').classList.remove('hidden');
  $('tierBadge').className = `hidden text-xs px-2.5 py-1 rounded-full font-medium ${state.user.tier === 'PREMIUM' ? 'badge-premium' : 'badge-free'}`;
  $('tierBadge').classList.remove('hidden');
  $('tierBadge').textContent = state.user.tier;
  $('userEmail').textContent = state.user.email;
}

function renderLoggedOut() {
  $('heroSection').classList.remove('hidden');
  $('dashboard').classList.add('hidden');
  $('dashboard').classList.remove('block');
  $('authButtons').classList.remove('hidden');
  $('userMenu').classList.add('hidden');
  $('userMenu').classList.remove('flex');
  $('tierBadge').classList.add('hidden');
  $('quotaDisplay').classList.add('hidden');
  $('quotaDisplay').classList.remove('flex');
}

function fillSample(url, price) {
  $('trackUrl').value = url;
  $('targetPrice').value = price;
  $('trackUrl').focus();
}

// ============================================================
// APP INIT
// ============================================================

const App = {
  async init() {
    if (state.token && state.user) {
      renderLoggedIn();
      await fetchUser();
    } else {
      renderLoggedOut();
    }
  }
};
