/**
 * lib-browser.js — Shared library browser modal.
 *
 * Usage:
 *   LibBrowser.init(librariesArray, currentUserId)
 *   LibBrowser.open()
 *   LibBrowser.close()
 *
 * Also exposes LibBrowser.renderFilterBar(el, onChange) and
 * LibBrowser.filteredLibs(libs, tab, type) for embedding in pages.
 */
window.LibBrowser = (function () {
  let _libs = [];
  let _userId = null;
  let _tab = 'all';
  let _type = '';
  const MODAL_ID = '__lib-browser-modal';

  // ── Public API ──────────────────────────────────────────────────────────────

  function init(libs, userId) {
    _libs = libs || [];
    _userId = userId || null;
  }

  function open() {
    _ensureModal();
    document.getElementById(MODAL_ID).style.display = '';
    _render();
  }

  function close() {
    const m = document.getElementById(MODAL_ID);
    if (m) m.style.display = 'none';
  }

  /** Filter libs by tab and type. */
  function filteredLibs(libs, tab, type) {
    return (libs || _libs).filter(lib => {
      if (type && lib.lib_type !== type) return false;
      if (tab === 'system') return lib.owner_id === null;
      if (tab === 'mine') return _userId !== null && lib.owner_id === _userId;
      if (tab === 'public') return lib.is_public && lib.owner_id !== null;
      return true;
    });
  }

  /** Render a filter pill bar into a container element.
   *  onTabChange(tab) / onTypeChange(type) called on change.
   */
  function renderFilterBar(container, state, onTabChange, onTypeChange) {
    const tab = state.tab || 'all';
    const type = state.type || '';
    const tabs = [
      { k: 'all', label: 'Все' },
      { k: 'system', label: 'Системные' },
      { k: 'mine', label: 'Мои' },
      { k: 'public', label: 'Публичные' },
    ];
    const types = [
      { k: '', label: 'Все типы' },
      { k: 'item_catalog', label: 'Каталоги' },
      { k: 'engine_config', label: 'Конфиги' },
      { k: 'generator_props', label: 'Свойства' },
    ];
    const pills = (arr, active, onClick) => arr.map(x =>
      `<button class="lb-pill${active === x.k ? ' active' : ''}" data-val="${_esc(x.k)}" onclick="(${onClick.toString()})('${_esc(x.k)}')">${x.label}</button>`
    ).join('');

    container.innerHTML = `
<div class="lb-filterbar">
  <div class="lb-pill-group">${pills(tabs, tab, onTabChange)}</div>
  <div class="lb-pill-group">${pills(types, type, onTypeChange)}</div>
</div>`;
  }

  /** Render lib list into a container element. Each item gets a "copy slug" button. */
  function renderList(container, libs, userId) {
    if (!libs.length) {
      container.innerHTML = '<div class="lb-empty">Ничего не найдено</div>';
      return;
    }
    const typeLabel = { item_catalog: 'Каталог', engine_config: 'Конфиг', generator_props: 'Свойства' };
    container.innerHTML = libs.map(lib => {
      const isSystem = lib.owner_id === null;
      const isMine = lib.owner_id === (userId || _userId);
      const badges = [
        `<span class="lb-badge${isSystem ? ' sys' : ''}">${typeLabel[lib.lib_type] || lib.lib_type}</span>`,
        isSystem ? '<span class="lb-badge sys">системная</span>' : '',
        lib.is_public && !isSystem ? '<span class="lb-badge pub">публичная</span>' : '',
        lib.engine_id ? `<span class="lb-badge">${_esc(lib.engine_id)}</span>` : '',
      ].filter(Boolean).join('');
      const preview = (lib.preview || []).slice(0, 5);
      return `
<div class="lb-item">
  <div class="lb-info">
    <div class="lb-name">${_esc(lib.name)}</div>
    <div class="lb-slug">${_esc(lib.slug)}</div>
    ${lib.description ? `<div class="lb-desc">${_esc(lib.description)}</div>` : ''}
    ${preview.length ? `<div class="lb-preview">${preview.map(_esc).join(', ')}</div>` : ''}
    <div class="lb-badges">${badges}</div>
  </div>
  <button class="lb-copy-btn" onclick="navigator.clipboard.writeText('${_esc(lib.slug)}').then(()=>{const t=document.getElementById('__lb-toast');if(t){t.textContent='Скопировано: ${_esc(lib.slug)}';t.classList.add('show');setTimeout(()=>t.classList.remove('show'),2000);}})">Скопировать slug</button>
</div>`;
    }).join('');
  }

  // ── CSS ─────────────────────────────────────────────────────────────────────

  function _injectStyles() {
    if (document.getElementById('__lb-styles')) return;
    const s = document.createElement('style');
    s.id = '__lb-styles';
    s.textContent = `
.lb-filterbar { display:flex; gap:6px; flex-wrap:wrap; margin-bottom:12px; }
.lb-pill-group { display:flex; gap:5px; flex-wrap:wrap; }
.lb-pill { padding:4px 13px; border-radius:16px; border:1px solid var(--border,#2a2a4a); background:transparent; color:var(--muted,#888); font-size:0.8rem; cursor:pointer; transition:all .15s; }
.lb-pill.active { background:var(--bg3,#0f3460); color:var(--gold,#c9a84c); border-color:var(--gold,#c9a84c); }
.lb-pill:hover:not(.active) { color:var(--text,#e0e0e0); }
.lb-item { background:var(--bg,#1a1a2e); border:1px solid var(--border,#2a2a4a); border-radius:6px; padding:10px 14px; display:flex; align-items:flex-start; gap:10px; }
.lb-info { flex:1; min-width:0; }
.lb-name { font-size:0.9rem; font-weight:600; }
.lb-slug { font-size:0.75rem; color:var(--muted,#888); font-family:monospace; }
.lb-desc { font-size:0.8rem; color:var(--muted,#888); margin-top:2px; }
.lb-preview { font-size:0.75rem; color:var(--muted,#888); margin-top:3px; font-style:italic; }
.lb-badges { display:flex; gap:5px; flex-wrap:wrap; margin-top:5px; }
.lb-badge { font-size:0.7rem; padding:1px 7px; border-radius:10px; background:var(--bg3,#0f3460); color:var(--gold,#c9a84c); }
.lb-badge.sys { color:var(--muted,#888); }
.lb-badge.pub { color:var(--success,#98c379); }
.lb-copy-btn { flex-shrink:0; padding:4px 10px; font-size:0.75rem; border-radius:5px; border:1px solid var(--border,#2a2a4a); background:transparent; color:var(--text,#e0e0e0); cursor:pointer; }
.lb-copy-btn:hover { border-color:var(--gold,#c9a84c); color:var(--gold,#c9a84c); }
.lb-empty { color:var(--muted,#888); text-align:center; padding:24px 0; font-size:0.875rem; }
/* Modal */
#__lib-browser-modal { position:fixed; inset:0; background:rgba(0,0,0,.6); display:flex; align-items:flex-start; justify-content:center; padding-top:60px; z-index:1000; }
#__lib-browser-modal .lb-modal { background:var(--bg2,#16213e); border:1px solid var(--border,#2a2a4a); border-radius:12px; padding:20px; width:100%; max-width:700px; max-height:80vh; display:flex; flex-direction:column; }
#__lib-browser-modal .lb-modal h2 { color:var(--gold,#c9a84c); margin-bottom:14px; font-size:1rem; }
#__lib-browser-modal .lb-modal-list { overflow-y:auto; flex:1; display:flex; flex-direction:column; gap:8px; }
#__lib-browser-modal .lb-modal-footer { display:flex; justify-content:space-between; align-items:center; margin-top:14px; border-top:1px solid var(--border,#2a2a4a); padding-top:12px; }
#__lib-browser-modal .lb-modal-footer a, #__lib-browser-modal .lb-modal-footer button { padding:5px 14px; border-radius:6px; border:1px solid var(--border,#2a2a4a); background:transparent; color:var(--muted,#888); font-size:0.8rem; cursor:pointer; text-decoration:none; }
#__lib-browser-modal .lb-modal-footer a:hover, #__lib-browser-modal .lb-modal-footer button:hover { color:var(--text,#e0e0e0); }
#__lb-toast { position:fixed; bottom:24px; right:24px; background:var(--bg3,#0f3460); color:var(--text,#e0e0e0); padding:10px 18px; border-radius:8px; font-size:0.875rem; opacity:0; transition:opacity .3s; pointer-events:none; z-index:2000; }
#__lb-toast.show { opacity:1; }
`;
    document.head.appendChild(s);
  }

  // ── Modal DOM ────────────────────────────────────────────────────────────────

  function _ensureModal() {
    _injectStyles();
    if (document.getElementById(MODAL_ID)) return;
    const div = document.createElement('div');
    div.id = MODAL_ID;
    div.style.display = 'none';
    div.innerHTML = `
<div class="lb-modal" onclick="event.stopPropagation()">
  <h2>📚 Библиотеки данных</h2>
  <div id="__lb-filterbar"></div>
  <div class="lb-modal-list" id="__lb-list"></div>
  <div class="lb-modal-footer">
    <a href="/libraries" target="_blank">✏️ Редактировать библиотеки ↗</a>
    <button onclick="LibBrowser.close()">Закрыть</button>
  </div>
</div>
<div id="__lb-toast"></div>`;
    div.addEventListener('click', e => { if (e.target === div) close(); });
    document.body.appendChild(div);
  }

  function _render() {
    const fb = document.getElementById('__lb-filterbar');
    const list = document.getElementById('__lb-list');
    if (!fb || !list) return;

    // Filter bar
    const tabs = [
      { k: 'all', label: 'Все' },
      { k: 'system', label: 'Системные' },
      { k: 'mine', label: 'Мои' },
      { k: 'public', label: 'Публичные' },
    ];
    const types = [
      { k: '', label: 'Все типы' },
      { k: 'item_catalog', label: 'Каталоги' },
      { k: 'engine_config', label: 'Конфиги' },
      { k: 'generator_props', label: 'Свойства' },
    ];
    fb.innerHTML = `<div class="lb-filterbar">
      <div class="lb-pill-group">${tabs.map(x => `<button class="lb-pill${_tab === x.k ? ' active' : ''}" onclick="LibBrowser._setTab('${x.k}')">${x.label}</button>`).join('')}</div>
      <div class="lb-pill-group">${types.map(x => `<button class="lb-pill${_type === x.k ? ' active' : ''}" onclick="LibBrowser._setType('${x.k}')">${x.label}</button>`).join('')}</div>
    </div>`;

    renderList(list, filteredLibs(_libs, _tab, _type));
  }

  function _setTab(t) { _tab = t; _render(); }
  function _setType(t) { _type = t; _render(); }

  function _esc(s) {
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  return { init, open, close, filteredLibs, renderFilterBar, renderList, _setTab, _setType };
})();
