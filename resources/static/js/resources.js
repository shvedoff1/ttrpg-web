/**
 * resources.js — Browse, search, create, copy, edit resource items.
 */

let accessToken = localStorage.getItem('access_token');
let _allResources = [];
let _allTags = [];
let _selectedTags = new Set();
let _ownerFilter = 'all';    // 'all' | 'system' | 'mine'
let _editId = null;          // null = create mode, number = edit mode
let _modalTags = [];          // tags in the modal tag-input
let _sugIdx = -1;             // autocomplete highlight index

// ── API helpers ────────────────────────────────────────────────────────────────

async function apiReq(method, path, body) {
  const opts = { method, headers: { 'Content-Type': 'application/json' }, credentials: 'include' };
  if (accessToken) opts.headers['Authorization'] = 'Bearer ' + accessToken;
  if (body !== undefined) opts.body = JSON.stringify(body);
  let res = await fetch(path, opts);
  if (res.status === 401) {
    const rr = await fetch('/auth/refresh', { method: 'POST', credentials: 'include' });
    if (rr.ok) {
      const rd = await rr.json();
      accessToken = rd.access_token;
      localStorage.setItem('access_token', accessToken);
      opts.headers['Authorization'] = 'Bearer ' + accessToken;
      res = await fetch(path, opts);
    }
  }
  return res;
}

async function apiJson(method, path, body) {
  const res = await apiReq(method, path, body);
  if (!res) return null;
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    return { _error: err.detail || `Ошибка ${res.status}` };
  }
  if (res.status === 204) return {};
  return res.json();
}

function toast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 2500);
}

function escHtml(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function getCurrentUser() {
  try { return JSON.parse(localStorage.getItem('user_info') || 'null'); } catch { return null; }
}

// ── Owner filter ──────────────────────────────────────────────────────────────

function setOwnerFilter(mode) {
  _ownerFilter = mode;
  document.querySelectorAll('#owner-pills .pill').forEach(btn => {
    btn.classList.toggle('active', btn.textContent.trim() === ({all:'Все',system:'Системные',mine:'Мои'}[mode]));
  });
  applyFilters();
}

// ── Tag filter bar ─────────────────────────────────────────────────────────────

function renderTagBar() {
  const container = document.getElementById('tag-list');
  const sorted = [..._allTags].sort((a, b) => a.localeCompare(b, 'ru'));
  // Filter tags: only show tags that have resources matching current owner filter
  const user = getCurrentUser();
  const ownerFiltered = _allResources.filter(r => {
    if (_ownerFilter === 'system') return r.owner_id == null;
    if (_ownerFilter === 'mine') return r.owner_id === user?.id;
    return true;
  });
  const visibleTags = sorted.filter(tag => ownerFiltered.some(r => (r.tags || []).includes(tag)));
  container.innerHTML = visibleTags.map(tag => {
    const active = _selectedTags.has(tag) ? 'active' : '';
    const checked = _selectedTags.has(tag) ? 'checked' : '';
    return `<div class="tag-item ${active}" onclick="toggleTag('${escHtml(tag)}')">
      <input type="checkbox" ${checked}> ${escHtml(tag)}
    </div>`;
  }).join('');
}

function createTag() {
  const name = prompt('Название нового тега (латиницей, без пробелов):');
  if (!name) return;
  const tag = name.trim().toLowerCase().replace(/\s+/g, '_');
  if (!tag) return;
  if (_allTags.includes(tag)) { toast('Тег уже существует'); return; }
  _allTags.push(tag);
  renderTagBar();
  toast('Тег добавлен (сохранится при привязке к ресурсу)');
}

function toggleTag(tag) {
  if (_selectedTags.has(tag)) {
    _selectedTags.delete(tag);
  } else {
    _selectedTags.add(tag);
  }
  renderTagBar();
  applyFilters();
}

async function applyFilters() {
  await loadResources();
  renderTagBar();
  updateCount();
}

async function updateCount() {
  if (_selectedTags.size === 0) {
    document.getElementById('count-badge').textContent = '';
    document.getElementById('bulk-copy-btn').style.display = 'none';
    return;
  }
  const tags = [..._selectedTags].join(',');
  const res = await apiJson('GET', `/api/resources/count?tags=${encodeURIComponent(tags)}`);
  if (res && !res._error) {
    document.getElementById('count-badge').textContent = `Найдено: ${res.count}`;
  }
  document.getElementById('bulk-copy-btn').style.display = '';
}

// ── Load resources ─────────────────────────────────────────────────────────────

async function loadResources() {
  let url = '/api/resources?limit=500&offset=0';
  if (_selectedTags.size > 0) {
    url += '&tags=' + encodeURIComponent([..._selectedTags].join(','));
  }
  if (_ownerFilter === 'mine') {
    url += '&owner_only=true';
  }
  const res = await apiJson('GET', url);
  _allResources = (!res || res._error) ? [] : res;
  renderList();
}

// ── Render list ────────────────────────────────────────────────────────────────

function getFilteredResources() {
  let items = _allResources;

  // Owner filter (system = show only owner_id null)
  if (_ownerFilter === 'system') {
    items = items.filter(r => r.owner_id === null || r.owner_id === undefined);
  }

  const q = (document.getElementById('search-input')?.value || '').toLowerCase();
  if (q) {
    items = items.filter(r =>
      (r.name || '').toLowerCase().includes(q) || (r.key || '').toLowerCase().includes(q)
    );
  }
  return items;
}

function renderList() {
  const items = getFilteredResources();
  const el = document.getElementById('res-list');
  const empty = document.getElementById('empty-msg');
  const user = getCurrentUser();

  if (!items.length) {
    el.innerHTML = '';
    empty.style.display = '';
    return;
  }
  empty.style.display = 'none';

  el.innerHTML = items.map(item => {
    const isSystem = item.owner_id === null || item.owner_id === undefined;
    const isMine = item.owner_id === user?.id;

    const tagBadges = (item.tags || []).map(t =>
      `<span class="badge tag">${escHtml(t)}</span>`
    ).join('');

    const systemBadge = isSystem ? '<span class="badge system">Системный</span>' : '';

    const priceStr = item.price != null ? `${item.price} зол.` : '—';
    const weightStr = item.weight ? `${item.weight} кг` : '—';
    const probStr = item.probability ? `${item.probability}` : '—';

    const btnCopy = `<button class="btn btn-ghost btn-sm" onclick="event.stopPropagation(); copyResource(${item.id})">Копировать</button>`;
    const btnEdit = isMine ? `<button class="btn btn-ghost btn-sm" onclick="event.stopPropagation(); openEdit(${item.id})">Изменить</button>` : '';
    const btnDel  = isMine ? `<button class="btn btn-danger btn-sm" onclick="event.stopPropagation(); deleteResource(${item.id})">Удалить</button>` : '';

    return `
<div class="lib-card" data-id="${item.id}"
  onmouseenter="_onCardHover(event, ${item.id})"
  onmouseleave="hidePreview()">
  <div class="info">
    <div class="name">${escHtml(item.name || item.key)}</div>
    <div class="slug">${escHtml(item.key)}</div>
    <div class="meta-row">
      <span>Цена: ${escHtml(priceStr)}</span>
      <span>Вес: ${escHtml(weightStr)}</span>
      <span>Вер.: ${escHtml(probStr)}</span>
    </div>
    <div class="badges">${systemBadge}${tagBadges}</div>
  </div>
  <div class="card-actions">
    ${btnCopy}${btnEdit}${btnDel}
  </div>
</div>`;
  }).join('');
}

// ── Hover preview ──────────────────────────────────────────────────────────────

let _previewTimer = null;

function _onCardHover(event, id) {
  clearTimeout(_previewTimer);
  const item = _allResources.find(r => r.id === id);
  if (!item) return;
  const rect = event.currentTarget.getBoundingClientRect();
  _previewTimer = setTimeout(() => showPreview(item, rect), 250);
}

function showPreview(item, rect) {
  const tt = document.getElementById('preview-tooltip');
  let html = '';

  html += `<div class="pt-row"><span class="pt-label">Key:</span> <span class="pt-val" style="font-family:monospace">${escHtml(item.key)}</span></div>`;
  html += `<div class="pt-row"><span class="pt-label">Цена:</span> <span class="pt-val">${item.price ?? '—'}</span></div>`;
  html += `<div class="pt-row"><span class="pt-label">Вес:</span> <span class="pt-val">${item.weight ?? '—'}</span></div>`;

  if (item.meta && typeof item.meta === 'object') {
    for (const [k, v] of Object.entries(item.meta)) {
      html += `<div class="pt-row"><span class="pt-label">${escHtml(k)}:</span> <span class="pt-val">${escHtml(String(v))}</span></div>`;
    }
  }

  if (item.source_item_id) {
    html += `<div class="pt-row"><span class="pt-label">Копия:</span> <span class="pt-val">#${item.source_item_id}</span></div>`;
  }

  tt.innerHTML = html;
  tt.classList.add('show');

  const ttH = tt.offsetHeight;
  const spaceBelow = window.innerHeight - rect.bottom;
  const top = spaceBelow > ttH + 16 ? rect.bottom + 8 : rect.top - ttH - 8;
  tt.style.top = Math.max(8, top) + 'px';
  tt.style.left = Math.min(rect.left, window.innerWidth - 318) + 'px';
}

function hidePreview() {
  clearTimeout(_previewTimer);
  document.getElementById('preview-tooltip').classList.remove('show');
}

// ── Copy resource ──────────────────────────────────────────────────────────────

async function copyResource(id) {
  const res = await apiJson('POST', `/api/resources/${id}/copy`);
  if (!res || res._error) { toast(res?._error || 'Ошибка копирования'); return; }
  toast('Ресурс скопирован');
  await loadResources();
}

async function bulkCopy() {
  if (_selectedTags.size === 0) return;
  const tags = [..._selectedTags];
  const res = await apiJson('POST', '/api/resources/bulk-copy', { tags });
  if (!res || res._error) { toast(res?._error || 'Ошибка копирования'); return; }
  toast('Набор скопирован');
  await loadResources();
}

// ── Delete resource ────────────────────────────────────────────────────────────

async function deleteResource(id) {
  const item = _allResources.find(r => r.id === id);
  if (!confirm(`Удалить ресурс «${item?.name || id}»?`)) return;
  const res = await apiJson('DELETE', `/api/resources/${id}`);
  if (res && res._error) { toast(res._error); return; }
  toast('Удалено');
  await loadResources();
}

// ── Modal: create / edit ───────────────────────────────────────────────────────

function openCreate() {
  _editId = null;
  _modalTags = [];
  document.getElementById('modal-title').textContent = 'Создать ресурс';
  document.getElementById('field-key').style.display = '';
  document.getElementById('m-key').value = '';
  document.getElementById('m-name').value = '';
  document.getElementById('m-price').value = '';
  document.getElementById('m-weight').value = '';
  document.getElementById('m-probability').value = '';
  document.getElementById('modal-err').textContent = '';
  renderModalTags();
  renderMetaEditor({});
  document.getElementById('modal-edit').style.display = '';
}

async function openEdit(id) {
  const res = await apiJson('GET', `/api/resources/${id}`);
  if (!res || res._error) { toast(res?._error || 'Ошибка'); return; }
  _editId = id;
  _modalTags = res.tags || [];
  document.getElementById('modal-title').textContent = 'Изменить ресурс';
  document.getElementById('field-key').style.display = 'none'; // key is not editable
  document.getElementById('m-key').value = res.key || '';
  document.getElementById('m-name').value = res.name || '';
  document.getElementById('m-price').value = res.price ?? '';
  document.getElementById('m-weight').value = res.weight ?? '';
  document.getElementById('m-probability').value = res.probability ?? '';
  document.getElementById('modal-err').textContent = '';
  renderModalTags();
  renderMetaEditor(res.meta || {});
  document.getElementById('modal-edit').style.display = '';
}

function closeModal() {
  document.getElementById('modal-edit').style.display = 'none';
  _editId = null;
  _modalTags = [];
  hideSuggestions();
}

async function saveResource() {
  const errEl = document.getElementById('modal-err');
  errEl.textContent = '';

  const name = document.getElementById('m-name').value.trim();
  if (!name) { errEl.textContent = 'Название обязательно'; return; }

  const priceVal = document.getElementById('m-price').value.trim();
  const weightVal = document.getElementById('m-weight').value.trim();
  const probVal = document.getElementById('m-probability').value.trim();
  const meta = collectMeta();

  if (_editId) {
    // PATCH
    const body = {
      name,
      price: priceVal !== '' ? parseFloat(priceVal) : null,
      weight: weightVal !== '' ? parseFloat(weightVal) : null,
      probability: probVal !== '' ? parseFloat(probVal) : null,
      tags: _modalTags,
      meta,
    };
    const res = await apiJson('PATCH', `/api/resources/${_editId}`, body);
    if (!res || res._error) { errEl.textContent = res?._error || 'Ошибка'; return; }
    toast('Сохранено');
  } else {
    // POST create
    const key = document.getElementById('m-key').value.trim();
    if (!key) { errEl.textContent = 'Key обязателен'; return; }
    const body = {
      key,
      name,
      price: priceVal !== '' ? parseFloat(priceVal) : null,
      weight: weightVal !== '' ? parseFloat(weightVal) : null,
      probability: probVal !== '' ? parseFloat(probVal) : 0,
      tags: _modalTags,
      meta,
    };
    const res = await apiJson('POST', '/api/resources', body);
    if (!res || res._error) { errEl.textContent = res?._error || 'Ошибка'; return; }
    toast('Ресурс создан');
  }

  closeModal();
  await loadResources();
  // Refresh tags in case new ones were added
  await loadTags();
  renderTagBar();
}

// ── Tag input (modal) ──────────────────────────────────────────────────────────

function renderModalTags() {
  const wrap = document.getElementById('tag-input-wrap');
  // Remove existing chips
  wrap.querySelectorAll('.tag-chip').forEach(c => c.remove());
  const input = document.getElementById('tag-input');
  _modalTags.forEach(tag => {
    const chip = document.createElement('span');
    chip.className = 'tag-chip';
    chip.innerHTML = `${escHtml(tag)}<button onclick="removeModalTag('${escHtml(tag)}')">&times;</button>`;
    wrap.insertBefore(chip, input);
  });
}

function removeModalTag(tag) {
  _modalTags = _modalTags.filter(t => t !== tag);
  renderModalTags();
}

function addModalTag(tag) {
  tag = tag.trim().toLowerCase();
  if (!tag || _modalTags.includes(tag)) return;
  _modalTags.push(tag);
  renderModalTags();
  document.getElementById('tag-input').value = '';
  hideSuggestions();
}

// Tag input events
document.getElementById('tag-input').addEventListener('input', function () {
  const val = this.value.trim().toLowerCase();
  if (!val) { hideSuggestions(); return; }
  const matches = _allTags.filter(t => t.toLowerCase().includes(val) && !_modalTags.includes(t));
  showSuggestions(matches);
});

document.getElementById('tag-input').addEventListener('keydown', function (e) {
  const sugEl = document.getElementById('tag-suggestions');
  const items = sugEl.querySelectorAll('.tag-suggestion');

  if (e.key === 'ArrowDown') {
    e.preventDefault();
    _sugIdx = Math.min(_sugIdx + 1, items.length - 1);
    updateSugHighlight(items);
  } else if (e.key === 'ArrowUp') {
    e.preventDefault();
    _sugIdx = Math.max(_sugIdx - 1, -1);
    updateSugHighlight(items);
  } else if (e.key === 'Enter') {
    e.preventDefault();
    if (_sugIdx >= 0 && items[_sugIdx]) {
      addModalTag(items[_sugIdx].textContent);
    } else if (this.value.trim()) {
      addModalTag(this.value);
    }
  } else if (e.key === 'Escape') {
    hideSuggestions();
  }
});

function showSuggestions(matches) {
  const sugEl = document.getElementById('tag-suggestions');
  if (!matches.length) { hideSuggestions(); return; }
  _sugIdx = -1;
  sugEl.innerHTML = matches.slice(0, 12).map(t =>
    `<div class="tag-suggestion" onclick="addModalTag('${escHtml(t)}')">${escHtml(t)}</div>`
  ).join('');
  sugEl.classList.add('show');
}

function hideSuggestions() {
  document.getElementById('tag-suggestions').classList.remove('show');
  _sugIdx = -1;
}

function updateSugHighlight(items) {
  items.forEach((el, i) => el.classList.toggle('active', i === _sugIdx));
}

// Close suggestions on outside click
document.addEventListener('click', function (e) {
  if (!e.target.closest('#tag-input-wrap') && !e.target.closest('#tag-suggestions')) {
    hideSuggestions();
  }
});

// ── Meta editor ────────────────────────────────────────────────────────────────

function renderMetaEditor(meta) {
  const container = document.getElementById('meta-editor');
  const entries = Object.entries(meta || {});
  container.innerHTML = entries.map(([k, v]) => `
    <div class="meta-row-edit">
      <input type="text" value="${escHtml(k)}" placeholder="ключ" class="meta-key" style="font-family:monospace;max-width:140px">
      <input type="text" value="${escHtml(typeof v === 'string' ? v : JSON.stringify(v))}" placeholder="значение" class="meta-val">
      <button onclick="this.closest('.meta-row-edit').remove()" title="Удалить">&times;</button>
    </div>
  `).join('');
}

function addMetaRow() {
  const container = document.getElementById('meta-editor');
  const div = document.createElement('div');
  div.className = 'meta-row-edit';
  div.innerHTML = `
    <input type="text" placeholder="ключ" class="meta-key" style="font-family:monospace;max-width:140px">
    <input type="text" placeholder="значение" class="meta-val">
    <button onclick="this.closest('.meta-row-edit').remove()" title="Удалить">&times;</button>
  `;
  container.appendChild(div);
}

function collectMeta() {
  const rows = document.querySelectorAll('#meta-editor .meta-row-edit');
  const meta = {};
  rows.forEach(row => {
    const k = row.querySelector('.meta-key')?.value.trim();
    const v = row.querySelector('.meta-val')?.value.trim();
    if (k) {
      // Try to parse JSON values
      try { meta[k] = JSON.parse(v); } catch { meta[k] = v; }
    }
  });
  return Object.keys(meta).length ? meta : null;
}

// ── Load tags ──────────────────────────────────────────────────────────────────

async function loadTags() {
  const res = await apiJson('GET', '/api/resources/tags');
  if (res && !res._error && res.tags) {
    _allTags = res.tags.sort();
  }
}

// ── Init ───────────────────────────────────────────────────────────────────────

async function init() {
  await Promise.all([loadTags(), loadResources()]);
  document.getElementById('loading').style.display = 'none';
  document.getElementById('main').style.display = '';
  renderTagBar();
}

init();
