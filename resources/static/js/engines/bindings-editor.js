/**
 * engines/bindings-editor.js — Reusable bindings editor for CategoryEngine.
 *
 * Usage:
 *   const editor = new BindingsEditor(container, engineId, 'weighted_roll');
 *   await editor.load();
 *   // later:
 *   const bindings = editor.save();
 *   const config   = editor.collectConfig();
 */

import { getToken } from '../auth.js';

/* ── Helpers ──────────────────────────────────────── */

function el(tag, props = {}) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (k === 'textContent') e.textContent = v;
    else if (k === 'innerHTML') e.innerHTML = v;
    else if (k === 'className') e.className = v;
    else if (k === 'checked') e.checked = v;
    else if (k === 'selected') e.selected = v;
    else if (k.startsWith('on')) e[k] = v;
    else if (k.startsWith('data-')) e.setAttribute(k, v);
    else e[k] = v;
  }
  return e;
}

async function apiFetch(method, path, body) {
  const token = getToken();
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const opts = { method, headers, credentials: 'include' };
  if (body !== undefined) opts.body = JSON.stringify(body);
  const res = await fetch(path, opts);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

/* ── Role labels for item_generator ───────────────── */

const ITEM_GEN_ROLES = [
  { role: 'base',     label: 'База' },
  { role: 'material', label: 'Материал' },
  { role: 'positive', label: 'Позитивные свойства' },
  { role: 'negative', label: 'Негативные свойства' },
];

/* ── CSS (injected once) ──────────────────────────── */

let _cssInjected = false;
function injectCSS() {
  if (_cssInjected) return;
  _cssInjected = true;
  const style = document.createElement('style');
  style.textContent = `
    .be-card {
      background: var(--bg2);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 14px;
      margin-bottom: 10px;
    }
    .be-card-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 10px;
    }
    .be-card-title {
      font-weight: 600;
      font-size: .9rem;
      color: var(--gold);
    }
    .be-row {
      display: flex;
      gap: 8px;
      align-items: center;
      margin-bottom: 8px;
      flex-wrap: wrap;
    }
    .be-label {
      font-size: .82rem;
      color: var(--dim);
      min-width: 70px;
    }
    .be-input {
      background: var(--bg);
      border: 1px solid var(--border);
      border-radius: 6px;
      color: var(--text);
      padding: 5px 8px;
      font-size: .85rem;
      font-family: inherit;
    }
    .be-input:focus {
      outline: none;
      border-color: var(--gold);
    }
    .be-input--wide { flex: 1; min-width: 120px; }
    .be-input--num  { width: 80px; }
    .be-tag-area {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      align-items: center;
      margin-bottom: 6px;
    }
    .be-tag-pill {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      background: var(--bg3);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 2px 10px;
      font-size: .8rem;
      color: var(--text);
    }
    .be-tag-pill .be-tag-rm {
      cursor: pointer;
      color: var(--dim);
      font-size: .75rem;
      margin-left: 2px;
    }
    .be-tag-pill .be-tag-rm:hover { color: var(--red); }
    .be-tag-input-wrap {
      position: relative;
      flex: 1;
      min-width: 140px;
    }
    .be-tag-input {
      width: 100%;
      background: var(--bg);
      border: 1px solid var(--border);
      border-radius: 6px;
      color: var(--text);
      padding: 5px 8px;
      font-size: .82rem;
      font-family: inherit;
    }
    .be-tag-input:focus { outline: none; border-color: var(--gold); }
    .be-autocomplete {
      position: absolute;
      top: 100%;
      left: 0;
      right: 0;
      background: var(--bg2);
      border: 1px solid var(--border);
      border-radius: 6px;
      max-height: 180px;
      overflow-y: auto;
      z-index: 50;
      display: none;
    }
    .be-autocomplete.open { display: block; }
    .be-ac-item {
      padding: 5px 10px;
      font-size: .82rem;
      cursor: pointer;
      color: var(--text);
    }
    .be-ac-item:hover, .be-ac-item.highlight {
      background: var(--bg3);
      color: var(--gold);
    }
    .be-count {
      font-size: .78rem;
      color: var(--dim);
      margin-left: 4px;
    }
    .be-collapsible-header {
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: .85rem;
      color: var(--gold);
      user-select: none;
      margin-top: 6px;
      margin-bottom: 4px;
    }
    .be-collapsible-header:hover { color: var(--gold-h); }
    .be-collapsible-arrow {
      font-size: .7rem;
      transition: transform .15s;
    }
    .be-collapsible-body { display: none; }
    .be-collapsible-body.open { display: block; }
    .be-items-table {
      width: 100%;
      border-collapse: collapse;
      font-size: .82rem;
      margin-top: 4px;
    }
    .be-items-table th {
      text-align: left;
      color: var(--dim);
      font-weight: normal;
      padding: 4px 6px;
      border-bottom: 1px solid var(--border);
    }
    .be-items-table td {
      padding: 4px 6px;
      border-bottom: 1px solid var(--border);
    }
    .be-items-table input {
      background: var(--bg);
      border: 1px solid var(--border);
      border-radius: 4px;
      color: var(--text);
      padding: 2px 6px;
      width: 70px;
      font-size: .82rem;
      font-family: inherit;
    }
    .be-bulk-toolbar {
      display: flex;
      align-items: center;
      gap: 6px;
      padding: 6px 8px;
      margin-bottom: 4px;
      background: var(--bg-alt, var(--bg));
      border: 1px solid var(--border);
      border-radius: 6px;
      font-size: .82rem;
    }
    .be-bulk-count {
      color: var(--dim);
      margin-right: 4px;
    }
    .be-bulk-val {
      background: var(--bg);
      border: 1px solid var(--border);
      border-radius: 4px;
      color: var(--text);
      padding: 2px 6px;
      font-size: .82rem;
      font-family: inherit;
    }
    .be-slider-row {
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .be-slider {
      flex: 1;
      accent-color: var(--gold);
    }
    .be-slider-val {
      font-size: .82rem;
      min-width: 36px;
      text-align: right;
      color: var(--dim);
    }
    .be-section-title {
      font-size: .88rem;
      color: var(--gold);
      font-weight: 600;
      margin: 14px 0 8px;
    }
    .be-empty {
      color: var(--dim);
      font-size: .82rem;
      font-style: italic;
    }
    .be-dedup-overlay {
      position: fixed;
      inset: 0;
      background: rgba(0,0,0,0.5);
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 1000;
    }
    .be-dedup-dialog {
      background: var(--bg, #1a1a2e);
      border: 1px solid var(--border, #333);
      border-radius: 8px;
      padding: 24px;
      max-width: 420px;
      max-height: 60vh;
      overflow-y: auto;
      color: var(--text, #eee);
    }
    .be-dedup-dialog h3 {
      margin-top: 0;
      color: var(--gold, #d4a017);
    }
    .be-dedup-dialog p {
      font-size: .88rem;
      color: var(--dim, #888);
      margin: 8px 0 12px;
    }
    .be-dedup-dialog ul {
      padding-left: 20px;
      margin: 0 0 16px;
    }
    .be-dedup-dialog li {
      font-size: .88rem;
      margin: 4px 0;
    }
    .be-dedup-dialog .btn {
      width: 100%;
    }
  `;
  document.head.appendChild(style);
}


/* ── Tag Picker Component ─────────────────────────── */

class TagPicker {
  constructor(initialTags = [], onChange) {
    this.tags = [...initialTags];
    this.onChange = onChange;
    this._allTags = null;
    this._matchCount = 0;
    this.el = el('div');
    this._render();
    this._loadAllTags();
  }

  async _loadAllTags() {
    if (!this._allTags) {
      try {
        const data = await apiFetch('GET', '/api/resources/tags?owner_only=true');
        this._allTags = data.tags || [];
      } catch {
        this._allTags = [];
      }
    }
  }

  _render() {
    this.el.innerHTML = '';

    const tagArea = el('div', { className: 'be-tag-area' });
    this.tags.forEach((tag, i) => {
      const pill = el('span', { className: 'be-tag-pill' });
      pill.appendChild(el('span', { textContent: tag }));
      const rm = el('span', { className: 'be-tag-rm', textContent: '\u00d7' });
      rm.onclick = () => { this.tags.splice(i, 1); this._render(); this._fireChange(); };
      pill.appendChild(rm);
      tagArea.appendChild(pill);
    });

    // Input with autocomplete
    const wrap = el('div', { className: 'be-tag-input-wrap' });
    const input = el('input', { className: 'be-tag-input', placeholder: 'Добавить тег...' });
    const dropdown = el('div', { className: 'be-autocomplete' });
    wrap.appendChild(input);
    wrap.appendChild(dropdown);
    tagArea.appendChild(wrap);

    // Count display
    this._countEl = el('span', { className: 'be-count' });
    tagArea.appendChild(this._countEl);

    this.el.appendChild(tagArea);

    let hlIdx = -1;

    const showSuggestions = (q) => {
      if (!this._allTags) { dropdown.classList.remove('open'); return; }
      const filtered = this._allTags.filter(t =>
        !this.tags.includes(t) && t.toLowerCase().includes(q.toLowerCase())
      ).slice(0, 15);
      dropdown.innerHTML = '';
      hlIdx = -1;
      if (!filtered.length) { dropdown.classList.remove('open'); return; }
      filtered.forEach((t, idx) => {
        const item = el('div', { className: 'be-ac-item', textContent: t });
        item.onmousedown = (e) => { e.preventDefault(); this._addTag(t); input.value = ''; dropdown.classList.remove('open'); };
        item.onmouseenter = () => {
          dropdown.querySelectorAll('.be-ac-item').forEach(x => x.classList.remove('highlight'));
          item.classList.add('highlight');
          hlIdx = idx;
        };
        dropdown.appendChild(item);
      });
      dropdown.classList.add('open');
    };

    input.oninput = () => showSuggestions(input.value.trim());
    input.onfocus = () => showSuggestions(input.value.trim());
    input.onblur = () => { setTimeout(() => dropdown.classList.remove('open'), 150); };
    input.onkeydown = (e) => {
      const items = dropdown.querySelectorAll('.be-ac-item');
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        hlIdx = Math.min(hlIdx + 1, items.length - 1);
        items.forEach((it, i) => it.classList.toggle('highlight', i === hlIdx));
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        hlIdx = Math.max(hlIdx - 1, 0);
        items.forEach((it, i) => it.classList.toggle('highlight', i === hlIdx));
      } else if (e.key === 'Enter') {
        e.preventDefault();
        if (hlIdx >= 0 && items[hlIdx]) {
          items[hlIdx].onmousedown(e);
        } else if (input.value.trim()) {
          this._addTag(input.value.trim());
          input.value = '';
          dropdown.classList.remove('open');
        }
      }
    };

    this._refreshCount();
  }

  _addTag(tag) {
    if (!this.tags.includes(tag)) {
      this.tags.push(tag);
      this._render();
      this._fireChange();
    }
  }

  _fireChange() {
    this._refreshCount();
    if (this.onChange) this.onChange(this.tags);
  }

  async _refreshCount() {
    if (!this.tags.length) {
      if (this._countEl) this._countEl.textContent = '';
      return;
    }
    try {
      const data = await apiFetch('GET', `/api/resources/count?tags=${encodeURIComponent(this.tags.join(','))}&owner_only=true`);
      this._matchCount = data.count ?? 0;
      if (this._countEl) this._countEl.textContent = `(${this._matchCount} шт.)`;
    } catch {
      if (this._countEl) this._countEl.textContent = '';
    }
  }

  getTags() { return [...this.tags]; }
}


/* ── Item Overrides Table ─────────────────────────── */

class ItemOverridesTable {
  constructor(tags, existingOverrides = {}) {
    this.tags = tags;
    this.overrides = { ...existingOverrides };
    this.items = [];
    this._selectedKeys = new Set();
    this.el = el('div');
  }

  async load() {
    if (!this.tags.length) {
      this.el.innerHTML = '<div class="be-empty">Выберите теги для загрузки предметов</div>';
      return;
    }
    this.el.innerHTML = '<div class="be-empty">Загрузка...</div>';
    try {
      const data = await apiFetch('GET', `/api/resources?tags=${encodeURIComponent(this.tags.join(','))}&owner_only=true`);
      this.items = Array.isArray(data) ? data : (data.items || []);
    } catch {
      this.items = [];
    }

    // Дедупликация по key
    const seen = new Map();
    const duplicates = [];
    for (const item of this.items) {
      const key = item.key || item.name;
      if (seen.has(key)) {
        duplicates.push(item);
      } else {
        seen.set(key, item);
      }
    }
    this.items = [...seen.values()];

    if (duplicates.length > 0) {
      this._showDedupDialog(duplicates);
    }

    this._render();
  }

  _showDedupDialog(duplicates) {
    const overlay = el('div', { className: 'be-dedup-overlay' });
    const dialog = el('div', { className: 'be-dedup-dialog' });

    dialog.appendChild(el('h3', { textContent: 'Дублирующиеся элементы удалены' }));

    const desc = el('p', { textContent: `Следующие элементы встречались более одного раза и были убраны (${duplicates.length} шт.):` });
    dialog.appendChild(desc);

    const list = el('ul');
    duplicates.forEach(d => {
      list.appendChild(el('li', { textContent: d.name || d.key }));
    });
    dialog.appendChild(list);

    const okBtn = el('button', { className: 'btn', textContent: 'ОК' });
    okBtn.onclick = () => overlay.remove();
    dialog.appendChild(okBtn);

    overlay.appendChild(dialog);
    document.body.appendChild(overlay);
  }

  _render() {
    this.el.innerHTML = '';
    if (!this.items.length) {
      this.el.appendChild(el('div', { className: 'be-empty', textContent: 'Нет предметов по выбранным тегам' }));
      return;
    }

    // Bulk action toolbar (hidden when nothing selected)
    const toolbar = el('div', { className: 'be-bulk-toolbar', style: 'display:none' });
    const selCount = el('span', { className: 'be-bulk-count' });
    toolbar.appendChild(selCount);

    const clearBtn = el('button', { className: 'btn btn-ghost btn-sm', textContent: 'Очистить выбранные' });
    clearBtn.onclick = () => {
      this._selectedKeys.forEach(k => delete this.overrides[k]);
      this.el.querySelectorAll('tbody input[type="number"]').forEach(inp => {
        if (this._selectedKeys.has(inp.dataset.itemKey)) inp.value = '';
      });
      this._selectedKeys.clear();
      updateToolbar();
      updateCheckboxes();
    };
    toolbar.appendChild(clearBtn);

    const setValInput = el('input', { type: 'number', className: 'be-bulk-val', placeholder: 'Значение', style: 'width:80px;margin-left:8px' });
    const setValBtn = el('button', { className: 'btn btn-ghost btn-sm', textContent: 'Установить' });
    setValBtn.onclick = () => {
      const v = setValInput.value.trim();
      if (v === '') return;
      const num = parseFloat(v);
      this._selectedKeys.forEach(k => { this.overrides[k] = num; });
      this.el.querySelectorAll('tbody input[type="number"]').forEach(inp => {
        if (this._selectedKeys.has(inp.dataset.itemKey)) inp.value = num;
      });
    };
    toolbar.appendChild(setValInput);
    toolbar.appendChild(setValBtn);
    this.el.appendChild(toolbar);

    const updateToolbar = () => {
      const n = this._selectedKeys.size;
      toolbar.style.display = n > 0 ? '' : 'none';
      selCount.textContent = `Выбрано: ${n}`;
    };

    const updateCheckboxes = () => {
      this.el.querySelectorAll('tbody input[type="checkbox"]').forEach(cb => {
        cb.checked = this._selectedKeys.has(cb.dataset.itemKey);
      });
      if (selectAllCb) selectAllCb.checked = this._selectedKeys.size === this.items.length && this.items.length > 0;
    };

    const table = el('table', { className: 'be-items-table' });
    const thead = el('thead');
    const headRow = el('tr');

    const thCb = el('th', { style: 'width:30px' });
    const selectAllCb = el('input', { type: 'checkbox' });
    selectAllCb.onchange = () => {
      if (selectAllCb.checked) {
        this.items.forEach(item => {
          const key = item.key || item.slug || item.name || '—';
          this._selectedKeys.add(key);
        });
      } else {
        this._selectedKeys.clear();
      }
      updateCheckboxes();
      updateToolbar();
    };
    thCb.appendChild(selectAllCb);
    headRow.appendChild(thCb);

    headRow.appendChild(el('th', { textContent: 'Название' }));
    headRow.appendChild(el('th', { textContent: 'Базовая вероятность' }));
    headRow.appendChild(el('th', { textContent: 'Своя вероятность' }));
    thead.appendChild(headRow);
    table.appendChild(thead);

    const tbody = el('tbody');
    this.items.forEach(item => {
      const tr = el('tr');
      const name = item.name || item.key || '—';
      const baseW = item.probability ?? item.weight ?? 0;
      const key = item.key || item.slug || name;

      const tdCb = el('td');
      const cb = el('input', { type: 'checkbox', 'data-item-key': key });
      cb.checked = this._selectedKeys.has(key);
      cb.onchange = () => {
        if (cb.checked) this._selectedKeys.add(key); else this._selectedKeys.delete(key);
        selectAllCb.checked = this._selectedKeys.size === this.items.length;
        updateToolbar();
      };
      tdCb.appendChild(cb);
      tr.appendChild(tdCb);

      tr.appendChild(el('td', { textContent: name }));
      tr.appendChild(el('td', { textContent: String(baseW), style: 'color:var(--dim)' }));

      const td = el('td');
      const inp = el('input', {
        type: 'number',
        value: this.overrides[key] ?? '',
        placeholder: '—',
        'data-item-key': key,
      });
      inp.oninput = () => {
        const v = inp.value.trim();
        if (v === '') {
          delete this.overrides[key];
        } else {
          this.overrides[key] = parseFloat(v);
        }
      };
      td.appendChild(inp);
      tr.appendChild(td);
      tbody.appendChild(tr);
    });

    table.appendChild(tbody);
    this.el.appendChild(table);
  }

  collect() {
    const result = {};
    for (const [k, v] of Object.entries(this.overrides)) {
      if (v !== undefined && v !== null && v !== '') result[k] = v;
    }
    return Object.keys(result).length ? result : null;
  }
}


/* ── Collapsible Section ──────────────────────────── */

function makeCollapsible(title, contentEl, startOpen = false) {
  const wrap = el('div');
  const arrow = el('span', { className: 'be-collapsible-arrow', textContent: startOpen ? '\u25bc' : '\u25b6' });
  const header = el('div', { className: 'be-collapsible-header' });
  header.appendChild(arrow);
  header.appendChild(el('span', { textContent: title }));

  const body = el('div', { className: 'be-collapsible-body' + (startOpen ? ' open' : '') });
  body.appendChild(contentEl);

  header.onclick = () => {
    const isOpen = body.classList.toggle('open');
    arrow.textContent = isOpen ? '\u25bc' : '\u25b6';
  };

  wrap.appendChild(header);
  wrap.appendChild(body);
  return wrap;
}


/* ── Main BindingsEditor Class ────────────────────── */

export class BindingsEditor {
  /**
   * @param {HTMLElement} container  — DOM element to render into
   * @param {number}      engineId  — category_engine ID
   * @param {string}      primitiveType — e.g. "weighted_roll"
   */
  constructor(container, engineId, primitiveType) {
    injectCSS();
    this.container = container;
    this.engineId = engineId;
    this.primitiveType = primitiveType;

    this._bindings = [];
    this._cards = [];       // internal card state
    this._configState = {}; // engine-level config changes (contexts, filters, etc.)
    this._deletedBindingIds = [];
  }

  /* ── Public API ─────────────────────────────────── */

  /** Set engine config before load() so existing contexts/filters are populated. */
  setConfig(config) {
    this._configState = { ...config };
  }

  /** Returns IDs of bindings that were removed in the editor. */
  getDeletedBindingIds() {
    return [...this._deletedBindingIds];
  }

  async load() {
    this.container.innerHTML = '<div class="be-empty">Загрузка привязок...</div>';
    try {
      const data = await apiFetch('GET', `/api/engines/${this.engineId}/bindings`);
      this._bindings = Array.isArray(data) ? data : (data.bindings || []);
    } catch {
      this._bindings = [];
    }
    this._render();
  }

  /** Returns array of binding objects ready to POST / PATCH. */
  save() {
    return this._cards.map(c => c.collect());
  }

  /** Returns engine-level config (contexts, filters, districts, templates). */
  collectConfig() {
    return { ...this._configState };
  }

  /* ── Render dispatch ────────────────────────────── */

  _render() {
    this.container.innerHTML = '';
    this._cards = [];

    switch (this.primitiveType) {
      case 'weighted_roll':
      case 'weighted_sample':
        this._renderWeighted();
        break;
      case 'cascade_roll':
        this._renderCascade();
        break;
      case 'context_roll':
        this._renderContext();
        break;
      case 'filtered_roll':
        this._renderFiltered();
        break;
      case 'loot_bundle':
        this._renderLootBundle();
        break;
      case 'pool_sample':
        this._renderPoolSample();
        break;
      case 'item_generator':
        this._renderItemGenerator();
        break;
      default:
        this._renderGeneric();
    }
  }

  /* ── weighted_roll / weighted_sample ────────────── */

  _renderWeighted() {
    const binding = this._bindings[0] || {};
    const card = this._makeBindingCard({
      title: 'Источник данных',
      binding,
      showOverrides: true,
    });
    this.container.appendChild(card.el);
    this._cards.push(card);
  }

  /* ── cascade_roll ───────────────────────────────── */

  _renderCascade() {
    const listWrap = el('div');
    this.container.appendChild(listWrap);

    const addBtn = el('button', {
      className: 'btn btn-ghost',
      textContent: '+ Добавить категорию',
      style: 'margin-top:8px',
    });
    addBtn.onclick = () => {
      const card = this._makeCascadeCard({}, listWrap, addBtn);
      this._cards.push(card);
    };
    this.container.appendChild(addBtn);

    this._bindings.forEach(b => {
      const card = this._makeCascadeCard(b, listWrap, addBtn);
      this._cards.push(card);
    });
  }

  _makeCascadeCard(binding, listWrap, addBtn) {
    const card = this._makeBindingCard({
      title: binding.label || 'Категория',
      binding,
      extraFields: [
        { key: 'label', label: 'Название', type: 'text', value: binding.label || '' },
        { key: 'icon', label: 'Иконка', type: 'text', value: binding.icon || '', inputClass: 'be-input--num' },
        { key: 'category_weight', label: 'Вес категории', type: 'slider', value: binding.category_weight ?? 1, min: 0, max: 10, step: 0.1 },
      ],
      removable: true,
      onRemove: () => {
        const idx = this._cards.indexOf(card);
        if (idx >= 0) this._cards.splice(idx, 1);
        card.el.remove();
      },
    });
    listWrap.insertBefore(card.el, addBtn?.nextSibling || null);
    return card;
  }

  /* ── context_roll ───────────────────────────────── */

  _renderContext() {
    // Single binding card
    const binding = this._bindings[0] || {};
    const card = this._makeBindingCard({ title: 'Источник данных', binding });
    this.container.appendChild(card.el);
    this._cards.push(card);

    // Contexts section (stored in engine config)
    const existingContexts = this._configState.contexts || {};
    this.container.appendChild(el('div', { className: 'be-section-title', textContent: 'Контексты' }));

    const ctxList = el('div');
    this.container.appendChild(ctxList);

    const ctxCards = [];

    const addCtxBtn = el('button', {
      className: 'btn btn-ghost',
      textContent: '+ Добавить контекст',
      style: 'margin-top:8px',
    });
    addCtxBtn.onclick = () => {
      const cc = this._makeContextCard('', {}, ctxList, ctxCards);
      ctxCards.push(cc);
    };
    this.container.appendChild(addCtxBtn);

    for (const [name, weights] of Object.entries(existingContexts)) {
      const cc = this._makeContextCard(name, weights, ctxList, ctxCards);
      ctxCards.push(cc);
    }

    // Hook config collection
    this._configState._contextCards = ctxCards;
    const origCollect = this.collectConfig.bind(this);
    this.collectConfig = () => {
      const cfg = origCollect();
      const contexts = {};
      (cfg._contextCards || ctxCards).forEach(cc => {
        const name = cc.nameInput.value.trim();
        if (!name) return;
        contexts[name] = cc.overrides.collect() || {};
      });
      delete cfg._contextCards;
      cfg.contexts = contexts;
      return cfg;
    };
  }

  _makeContextCard(name, weights, listWrap, ctxCards) {
    const card = el('div', { className: 'be-card' });
    const header = el('div', { className: 'be-card-header' });
    const nameInput = el('input', {
      className: 'be-input be-input--wide',
      value: name,
      placeholder: 'Название контекста',
    });
    header.appendChild(nameInput);
    const rmBtn = el('button', { className: 'btn btn-ghost', textContent: '\u2715' });
    rmBtn.onclick = () => {
      const idx = ctxCards.indexOf(state);
      if (idx >= 0) ctxCards.splice(idx, 1);
      card.remove();
    };
    header.appendChild(rmBtn);
    card.appendChild(header);

    const overrides = new ItemOverridesTable(
      this._cards[0]?.tagPicker?.getTags() || [],
      weights
    );
    card.appendChild(makeCollapsible('Вероятности выпадения', overrides.el, Object.keys(weights).length > 0));
    overrides.load();

    listWrap.appendChild(card);
    const state = { el: card, nameInput, overrides };
    return state;
  }

  /* ── filtered_roll ──────────────────────────────── */

  _renderFiltered() {
    // Binding cards with tag pickers
    const listWrap = el('div');
    this.container.appendChild(listWrap);

    const addBindBtn = el('button', {
      className: 'btn btn-ghost',
      textContent: '+ Добавить источник',
      style: 'margin-top:8px',
    });
    addBindBtn.onclick = () => {
      const card = this._makeBindingCard({ title: 'Источник', binding: {}, removable: true, onRemove: () => { const idx = this._cards.indexOf(card); if (idx >= 0) this._cards.splice(idx, 1); card.el.remove(); } });
      listWrap.appendChild(card.el);
      this._cards.push(card);
    };
    this.container.appendChild(addBindBtn);

    this._bindings.forEach(b => {
      const card = this._makeBindingCard({ title: 'Источник', binding: b, removable: true, onRemove: () => { const idx = this._cards.indexOf(card); if (idx >= 0) this._cards.splice(idx, 1); card.el.remove(); } });
      listWrap.appendChild(card.el);
      this._cards.push(card);
    });

    // Filters section (engine config)
    this.container.appendChild(el('div', { className: 'be-section-title', textContent: 'Фильтры' }));
    const rawFilters = this._configState.filters || [];
    const existingFilters = Array.isArray(rawFilters)
      ? rawFilters
      : Object.entries(rawFilters).map(([k, v]) => ({ name: v?.name || k, ...v }));
    const filterList = el('div');
    this.container.appendChild(filterList);
    const filterCards = [];

    const addFilterBtn = el('button', {
      className: 'btn btn-ghost',
      textContent: '+ Добавить фильтр',
      style: 'margin-top:8px',
    });
    addFilterBtn.onclick = () => {
      filterCards.push(this._makeFilterCard({}, filterList, filterCards));
    };
    this.container.appendChild(addFilterBtn);

    existingFilters.forEach(f => {
      filterCards.push(this._makeFilterCard(f, filterList, filterCards));
    });

    const origCollect = this.collectConfig.bind(this);
    this.collectConfig = () => {
      const cfg = origCollect();
      cfg.filters = filterCards.map(fc => {
        const entry = {
          name: fc.nameInput.value.trim(),
          field: fc.fieldSelect.value,
          exclude: fc.excludeSelect.value,
          mode: fc.modeSelect.value,
          value: parseFloat(fc.valueInput.value) || 0,
        };
        const ov = fc.overrides?.collect();
        if (ov) entry.overrides = ov;
        return entry;
      }).filter(f => f.name);
      return cfg;
    };
  }

  _makeFilterCard(filter, listWrap, filterCards) {
    // Normalize legacy format for display
    let field = filter.field || 'probability';
    let exclude = filter.exclude || 'gt';
    let mode = filter.mode || 'percent';
    let value = filter.value ?? filter.percent ?? 20;
    // Legacy rule conversion
    if (!filter.field && (filter.rule || filter.filter)) {
      const rule = filter.rule || filter.filter;
      field = 'probability';
      if (rule === 'exclude_rarest') { exclude = 'lt'; }
      else if (rule === 'exclude_common') { exclude = 'gt'; }
    }

    const card = el('div', { className: 'be-card' });

    // Row 1: name + remove
    const row1 = el('div', { className: 'be-row' });
    const nameInput = el('input', { className: 'be-input be-input--wide', value: filter.name || '', placeholder: 'Название фильтра' });
    const rmBtn = el('button', { className: 'btn btn-ghost', textContent: '\u2715' });
    rmBtn.onclick = () => {
      const idx = filterCards.indexOf(state);
      if (idx >= 0) filterCards.splice(idx, 1);
      card.remove();
    };
    row1.appendChild(nameInput);
    row1.appendChild(rmBtn);
    card.appendChild(row1);

    // Row 2: field + exclude
    const row2 = el('div', { className: 'be-row' });
    row2.appendChild(el('span', { className: 'be-label', textContent: 'Критерий' }));
    const fieldSelect = el('select', { className: 'be-input' });
    [['probability', 'Вероятность'], ['price', 'Цена']].forEach(([v, t]) => {
      const opt = el('option', { value: v, textContent: t });
      if (field === v) opt.selected = true;
      fieldSelect.appendChild(opt);
    });
    row2.appendChild(fieldSelect);

    row2.appendChild(el('span', { className: 'be-label', textContent: 'Исключить', style: 'min-width:auto;margin-left:8px' }));
    const excludeSelect = el('select', { className: 'be-input' });
    [['gt', 'больше ↑'], ['lt', 'меньше ↓']].forEach(([v, t]) => {
      const opt = el('option', { value: v, textContent: t });
      if (exclude === v) opt.selected = true;
      excludeSelect.appendChild(opt);
    });
    row2.appendChild(excludeSelect);
    card.appendChild(row2);

    // Row 3: mode + value
    const row3 = el('div', { className: 'be-row' });
    row3.appendChild(el('span', { className: 'be-label', textContent: 'Режим' }));
    const modeSelect = el('select', { className: 'be-input' });
    [['percent', '% от пула'], ['absolute', 'Абсолютное значение']].forEach(([v, t]) => {
      const opt = el('option', { value: v, textContent: t });
      if (mode === v) opt.selected = true;
      modeSelect.appendChild(opt);
    });
    row3.appendChild(modeSelect);

    const valueLabel = el('span', { className: 'be-label', textContent: mode === 'percent' ? 'Процент' : 'Порог', style: 'min-width:auto;margin-left:8px' });
    row3.appendChild(valueLabel);

    // For percent mode — slider, for absolute — number input
    const sliderWrap = el('div', { className: 'be-slider-row', style: `flex:1;${mode !== 'percent' ? 'display:none' : ''}` });
    const slider = el('input', { type: 'range', className: 'be-slider', min: '0', max: '100', step: '1', value: String(mode === 'percent' ? value : 20) });
    const sliderVal = el('span', { className: 'be-slider-val', textContent: `${mode === 'percent' ? value : 20}%` });
    slider.oninput = () => { sliderVal.textContent = `${slider.value}%`; numInput.value = slider.value; };
    sliderWrap.appendChild(slider);
    sliderWrap.appendChild(sliderVal);

    const numInput = el('input', { type: 'number', className: 'be-input be-input--num', value: String(value), style: mode !== 'absolute' ? 'display:none' : '' });
    numInput.oninput = () => { slider.value = numInput.value; sliderVal.textContent = `${numInput.value}%`; };

    modeSelect.onchange = () => {
      const isPercent = modeSelect.value === 'percent';
      sliderWrap.style.display = isPercent ? '' : 'none';
      numInput.style.display = isPercent ? 'none' : '';
      valueLabel.textContent = isPercent ? 'Процент' : 'Порог';
    };

    row3.appendChild(sliderWrap);
    row3.appendChild(numInput);
    card.appendChild(row3);

    // Probability overrides table
    const overrides = new ItemOverridesTable(
      this._cards[0]?.tagPicker?.getTags() || [],
      filter.overrides || {}
    );
    card.appendChild(makeCollapsible('Вероятности выпадения', overrides.el, Object.keys(filter.overrides || {}).length > 0));
    overrides.load();

    listWrap.appendChild(card);
    const state = {
      el: card,
      nameInput,
      fieldSelect,
      excludeSelect,
      modeSelect,
      overrides,
      get valueInput() { return modeSelect.value === 'percent' ? slider : numInput; },
    };
    return state;
  }

  /* ── loot_bundle ────────────────────────────────── */

  _renderLootBundle() {
    // Binding cards
    const listWrap = el('div');
    this.container.appendChild(listWrap);

    const addBindBtn = el('button', {
      className: 'btn btn-ghost',
      textContent: '+ Добавить источник',
      style: 'margin-top:8px',
    });
    addBindBtn.onclick = () => {
      const card = this._makeBindingCard({ title: 'Источник', binding: {}, removable: true, onRemove: () => { const idx = this._cards.indexOf(card); if (idx >= 0) this._cards.splice(idx, 1); card.el.remove(); } });
      listWrap.appendChild(card.el);
      this._cards.push(card);
    };
    this.container.appendChild(addBindBtn);

    this._bindings.forEach(b => {
      const card = this._makeBindingCard({ title: 'Источник', binding: b, removable: true, onRemove: () => { const idx = this._cards.indexOf(card); if (idx >= 0) this._cards.splice(idx, 1); card.el.remove(); } });
      listWrap.appendChild(card.el);
      this._cards.push(card);
    });

    // Presets section (engine config)
    this.container.appendChild(el('div', { className: 'be-section-title', textContent: 'Пресеты' }));
    const existingPresets = this._configState.presets || this._configState.districts || [];
    const presetList = el('div');
    this.container.appendChild(presetList);
    const presetCards = [];

    const addPresetBtn = el('button', {
      className: 'btn btn-ghost',
      textContent: '+ Добавить пресет',
      style: 'margin-top:8px',
    });
    addPresetBtn.onclick = () => {
      presetCards.push(this._makePresetCard({}, presetList, presetCards));
    };
    this.container.appendChild(addPresetBtn);

    existingPresets.forEach(p => {
      presetCards.push(this._makePresetCard(p, presetList, presetCards));
    });

    const origCollect = this.collectConfig.bind(this);
    this.collectConfig = () => {
      const cfg = origCollect();
      cfg.presets = presetCards.map(pc => {
        const entry = {
          name: pc.nameInput.value.trim(),
          gold_min: parseFloat(pc.goldMin.value) || 0,
          gold_max: parseFloat(pc.goldMax.value) || 0,
          items_min: parseInt(pc.itemsMin.value) || 0,
          items_max: parseInt(pc.itemsMax.value) || 0,
        };
        const ov = pc.overrides?.collect();
        if (ov) entry.overrides = ov;
        return entry;
      }).filter(p => p.name);
      return cfg;
    };
  }

  _makePresetCard(preset, listWrap, presetCards) {
    const card = el('div', { className: 'be-card' });
    const row1 = el('div', { className: 'be-row' });

    const nameInput = el('input', { className: 'be-input be-input--wide', value: preset.name || '', placeholder: 'Название пресета' });
    const rmBtn = el('button', { className: 'btn btn-ghost', textContent: '\u2715' });
    rmBtn.onclick = () => {
      const idx = presetCards.indexOf(state);
      if (idx >= 0) presetCards.splice(idx, 1);
      card.remove();
    };
    row1.appendChild(nameInput);
    row1.appendChild(rmBtn);
    card.appendChild(row1);

    const row2 = el('div', { className: 'be-row' });
    row2.appendChild(el('span', { className: 'be-label', textContent: 'Золото' }));
    const goldMin = el('input', { type: 'number', className: 'be-input be-input--num', value: preset.gold_min ?? '', placeholder: 'мин' });
    row2.appendChild(goldMin);
    row2.appendChild(el('span', { textContent: '—', style: 'color:var(--dim)' }));
    const goldMax = el('input', { type: 'number', className: 'be-input be-input--num', value: preset.gold_max ?? '', placeholder: 'макс' });
    row2.appendChild(goldMax);
    card.appendChild(row2);

    const row3 = el('div', { className: 'be-row' });
    row3.appendChild(el('span', { className: 'be-label', textContent: 'Предметы' }));
    const itemsMin = el('input', { type: 'number', className: 'be-input be-input--num', value: preset.items_min ?? '', placeholder: 'мин' });
    row3.appendChild(itemsMin);
    row3.appendChild(el('span', { textContent: '—', style: 'color:var(--dim)' }));
    const itemsMax = el('input', { type: 'number', className: 'be-input be-input--num', value: preset.items_max ?? '', placeholder: 'макс' });
    row3.appendChild(itemsMax);
    card.appendChild(row3);

    // Probability overrides table
    const overrides = new ItemOverridesTable(
      this._cards[0]?.tagPicker?.getTags() || [],
      preset.overrides || {}
    );
    card.appendChild(makeCollapsible('Вероятности выпадения', overrides.el, Object.keys(preset.overrides || {}).length > 0));
    overrides.load();

    listWrap.appendChild(card);
    const state = { el: card, nameInput, goldMin, goldMax, itemsMin, itemsMax, overrides };
    return state;
  }

  /* ── pool_sample ────────────────────────────────── */

  _renderPoolSample() {
    const listWrap = el('div');
    this.container.appendChild(listWrap);

    const addBtn = el('button', {
      className: 'btn btn-ghost',
      textContent: '+ Добавить пул',
      style: 'margin-top:8px',
    });
    addBtn.onclick = () => {
      const card = this._makePoolCard({}, listWrap);
      this._cards.push(card);
    };
    this.container.appendChild(addBtn);

    this._bindings.forEach(b => {
      const card = this._makePoolCard(b, listWrap);
      this._cards.push(card);
    });
  }

  _makePoolCard(binding, listWrap) {
    const card = this._makeBindingCard({
      title: 'Пул',
      binding,
      extraFields: [
        { key: 'priority', label: 'Приоритет', type: 'number', value: binding.priority ?? 0 },
        { key: 'count', label: 'Количество', type: 'number', value: binding.count ?? 1 },
      ],
      removable: true,
      onRemove: () => {
        const idx = this._cards.indexOf(card);
        if (idx >= 0) this._cards.splice(idx, 1);
        card.el.remove();
      },
    });
    listWrap.appendChild(card.el);
    return card;
  }

  /* ── item_generator ─────────────────────────────── */

  _renderItemGenerator() {
    ITEM_GEN_ROLES.forEach(({ role, label }) => {
      const binding = this._bindings.find(b => b.role === role) || { role };
      const card = this._makeBindingCard({
        title: label,
        binding,
        fixedRole: role,
      });
      this.container.appendChild(card.el);
      this._cards.push(card);
    });
  }

  /* ── Generic fallback ───────────────────────────── */

  _renderGeneric() {
    const listWrap = el('div');
    this.container.appendChild(listWrap);

    const addBtn = el('button', {
      className: 'btn btn-ghost',
      textContent: '+ Добавить привязку',
      style: 'margin-top:8px',
    });
    addBtn.onclick = () => {
      const card = this._makeBindingCard({ title: 'Привязка', binding: {}, removable: true, onRemove: () => { const idx = this._cards.indexOf(card); if (idx >= 0) this._cards.splice(idx, 1); card.el.remove(); } });
      listWrap.appendChild(card.el);
      this._cards.push(card);
    };
    this.container.appendChild(addBtn);

    this._bindings.forEach(b => {
      const card = this._makeBindingCard({ title: 'Привязка', binding: b, removable: true, onRemove: () => { const idx = this._cards.indexOf(card); if (idx >= 0) this._cards.splice(idx, 1); card.el.remove(); } });
      listWrap.appendChild(card.el);
      this._cards.push(card);
    });
  }

  /* ── Core: binding card builder ─────────────────── */

  /**
   * @param {Object} opts
   *   title           — card title
   *   binding         — existing binding data
   *   extraFields     — [{key, label, type, value, ...}]
   *   showOverrides   — if true, show item overrides collapsible
   *   removable       — show remove button
   *   onRemove        — callback
   *   fixedRole       — lock role to this value
   */
  _makeBindingCard(opts) {
    const { title, binding = {}, extraFields = [], showOverrides = false, removable = false, onRemove, fixedRole } = opts;

    const card = el('div', { className: 'be-card' });

    // Header
    const header = el('div', { className: 'be-card-header' });
    header.appendChild(el('span', { className: 'be-card-title', textContent: title }));
    if (removable) {
      const rmBtn = el('button', { className: 'btn btn-ghost', textContent: '\u2715' });
      rmBtn.onclick = () => {
        if (binding.id) this._deletedBindingIds.push(binding.id);
        if (onRemove) onRemove();
      };
      header.appendChild(rmBtn);
    }
    card.appendChild(header);

    // Tag picker
    const existingTags = binding.tag_filter ? (Array.isArray(binding.tag_filter) ? binding.tag_filter : binding.tag_filter.split(',').map(t => t.trim()).filter(Boolean)) : [];
    const tagPicker = new TagPicker(existingTags, (tags) => {
      if (overridesTable) {
        overridesTable.tags = tags;
        overridesTable.load();
      }
    });

    const tagRow = el('div', { className: 'be-row' });
    tagRow.appendChild(el('span', { className: 'be-label', textContent: 'Теги' }));
    tagRow.appendChild(tagPicker.el);
    card.appendChild(tagRow);

    // Extra fields
    const fieldInputs = {};
    extraFields.forEach(f => {
      const row = el('div', { className: 'be-row' });
      row.appendChild(el('span', { className: 'be-label', textContent: f.label }));

      if (f.type === 'slider') {
        const sliderRow = el('div', { className: 'be-slider-row', style: 'flex:1' });
        const slider = el('input', { type: 'range', className: 'be-slider', min: String(f.min ?? 0), max: String(f.max ?? 10), step: String(f.step ?? 1), value: String(f.value ?? 0) });
        const valSpan = el('span', { className: 'be-slider-val', textContent: String(f.value ?? 0) });
        slider.oninput = () => { valSpan.textContent = slider.value; };
        sliderRow.appendChild(slider);
        sliderRow.appendChild(valSpan);
        row.appendChild(sliderRow);
        fieldInputs[f.key] = slider;
      } else if (f.type === 'number') {
        const inp = el('input', { type: 'number', className: 'be-input be-input--num', value: f.value ?? '' });
        row.appendChild(inp);
        fieldInputs[f.key] = inp;
      } else {
        const cls = f.inputClass ? `be-input ${f.inputClass}` : 'be-input be-input--wide';
        const inp = el('input', { type: 'text', className: cls, value: f.value ?? '' });
        row.appendChild(inp);
        fieldInputs[f.key] = inp;
      }

      card.appendChild(row);
    });

    // Item overrides (collapsible)
    let overridesTable = null;
    if (showOverrides) {
      overridesTable = new ItemOverridesTable(existingTags, binding.item_overrides || {});
      card.appendChild(makeCollapsible('Тонкая настройка весов', overridesTable.el, false));
      overridesTable.load();
    }

    const state = {
      el: card,
      tagPicker,
      fieldInputs,
      overridesTable,
      _binding: binding,
      _fixedRole: fixedRole,
      collect() {
        const tags = tagPicker.getTags();
        const result = {
          tag_filter: tags.join(','),
        };
        // Preserve id for PATCH
        if (binding.id) result.id = binding.id;
        // Fixed role
        if (fixedRole) result.role = fixedRole;
        else if (binding.role) result.role = binding.role;
        // Extra fields
        for (const [k, inp] of Object.entries(fieldInputs)) {
          const v = inp.value;
          if (inp.type === 'range' || inp.type === 'number') {
            result[k] = parseFloat(v) || 0;
          } else {
            result[k] = v || null;
          }
        }
        // Item overrides
        if (overridesTable) {
          const ov = overridesTable.collect();
          if (ov) result.item_overrides = ov;
        }
        return result;
      },
    };

    return state;
  }
}

// Also expose on window for non-module usage
if (typeof window !== 'undefined') {
  window.BindingsEditor = BindingsEditor;
}
