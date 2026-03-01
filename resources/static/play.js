// ── Auth ────────────────────────────────────────────
let currentUser = null;

async function initAuth() {
    try {
        const r = await fetch('/auth/me');
        if (r.ok) {
            const { name } = await r.json();
            currentUser = name;
            _updateUserDisplay();
            return;
        }
    } catch {}
    showLoginModal();
}

function showLoginModal() {
    document.getElementById('authOverlay').classList.add('visible');
    setTimeout(() => document.getElementById('authInput').focus(), 50);
}

function hideLoginModal() {
    document.getElementById('authOverlay').classList.remove('visible');
}

async function submitLogin() {
    const input = document.getElementById('authInput');
    const name = input.value.trim();
    if (!name) { input.focus(); return; }
    const btn = document.getElementById('authSubmitBtn');
    btn.disabled = true;
    try {
        const r = await fetch('/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name }),
        });
        if (r.ok) {
            const data = await r.json();
            currentUser = data.name;
            _updateUserDisplay();
            hideLoginModal();
        }
    } catch {}
    btn.disabled = false;
}

function _updateUserDisplay() {
    const el = document.getElementById('userName');
    if (el) el.textContent = currentUser ? `👤 ${currentUser}` : '';
    const area = document.getElementById('headerUserArea');
    if (area) area.style.visibility = currentUser ? 'visible' : 'hidden';
}

document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('authInput').addEventListener('keydown', e => {
        if (e.key === 'Enter') submitLogin();
    });
});

// ── Category definitions ───────────────────────────
const CATS = {
    professions: {
        label: 'Профессии',
        items: [
            { icon: '🌿', name: 'Травы' },
            { icon: '⛏',  name: 'Руды' },
            { icon: '🗝',  name: 'Воровство' },
            { icon: '🐾', name: 'Следы' },
        ]
    },
    items: {
        label: 'Предметы',
        items: [
            { icon: '🏪', name: 'Торговцы' },
            { icon: '📦', name: 'Сундуки' },
            { icon: '💎', name: 'Сокровища' },
        ]
    },
    story: {
        label: 'Сюжет',
        items: [
            { icon: '🎭', name: 'Мотивация' },
            { icon: '⚡', name: 'Событие' },
            { icon: '🗡', name: 'Дозор' },
        ]
    }
};

// ── Profession → data source mapping ──────────────
const PROFESSION_SOURCES = {
    'Травы': { mode: 'with_locations', icon: '🌿' },
    'Руды':  { mode: 'with_locations', icon: '⛏'  },
    'Воровство': {
        mode: 'multi', icon: '🗝',
        param1: [
            { key: 'cache', name: 'Поиск схрона',    icon: '📦' },
            { key: 'steal', name: 'Карманная кража',  icon: '✋' },
        ],
        param2: [
            { key: 'poor',   name: 'Бедный район',  icon: '🏚' },
            { key: 'normal', name: 'Обычный район',  icon: '🏘' },
            { key: 'rich',   name: 'Богатый район',  icon: '🏛' },
            { key: 'magic',  name: 'Обитель магии',  icon: '🔮' },
        ],
    },
    'Следы': { mode: 'with_locations', icon: '🐾' },
};

// ── State ──────────────────────────────────────────
let activeCat        = null;
let activeProfession = null;  // { name, source, icon }
let activeParam1     = null;  // { key, name, icon } — first step for multi-mode
let activeLocation   = null;  // { name, locationKey?, param1Key?, param2Key?, subtype?, key? }

// ── Trader templates ───────────────────────────────
const TRADER_TEMPLATES = [
    { key: 'weapon_smith', name: 'Оружейник',    icon: '⚔'  },
    { key: 'armorer',      name: 'Бронник',       icon: '🛡'  },
    { key: 'hunter',       name: 'Охотник',       icon: '🐾' },
    { key: 'herbalist',    name: 'Травник',       icon: '🌿' },
    { key: 'alchemist',    name: 'Алхимик',       icon: '⚗'  },
    { key: 'haberdasher',  name: 'Галантерейщик', icon: '🧵' },
    { key: 'jeweler',      name: 'Ювелир',        icon: '💎' },
    { key: 'food_drinks',  name: 'Еда и напитки', icon: '🍺' },
];

// ── Category selection ─────────────────────────────
function selectCat(btn) {
    const key = btn.dataset.cat;
    if (activeCat === key) {
        activeCat = null;
        btn.classList.remove('active');
        collapseAll();
        return;
    }
    activeCat = key;
    document.querySelectorAll('.cat-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    expand(CATS[key]);
}

function collapseAll() {
    document.getElementById('vConnector').classList.remove('visible');
    document.getElementById('subArea').classList.remove('visible');
    document.getElementById('catLabelStrip').classList.remove('visible');
    collapseInteract();
    activeProfession = null;
    activeLocation   = null;
}

function collapseInteract() {
    const interactArea = document.getElementById('interactArea');
    interactArea.classList.remove('visible');
    interactArea.classList.remove('trader-mode');
    const searchBtn = document.getElementById('searchBtn');
    searchBtn.disabled = true;
    searchBtn.style.display = '';
    searchBtn.textContent = '⚔ Ищем';
    document.getElementById('param1Section').classList.remove('show');
    document.getElementById('locGrid').innerHTML = '';
    const inv = document.getElementById('traderInventory');
    inv.innerHTML = '';
    inv.classList.remove('show');
    ChestGame.hide();
    activeLocation = null;
    activeParam1   = null;
}

function expand(cat) {
    const subRow  = document.getElementById('subRow');
    const subArea = document.getElementById('subArea');
    const strip   = document.getElementById('catLabelStrip');

    subArea.classList.remove('visible');
    collapseInteract();
    subRow.innerHTML = '';
    subRow.style.removeProperty('--bar-left');
    subRow.style.removeProperty('--bar-w');

    document.getElementById('catLabelText').textContent = cat.label;

    cat.items.forEach((item, i) => {
        const card = document.createElement('div');
        card.className = 'sub-card';
        card.innerHTML = `<span class="sub-icon">${item.icon}</span>${item.name}`;
        card.style.transitionDelay = `${0.1 + i * 0.07}s`;
        card.onclick = () => onSubClick(card, item);
        subRow.appendChild(card);
    });

    document.getElementById('vConnector').classList.add('visible');
    strip.classList.add('visible');

    requestAnimationFrame(() => {
        subArea.classList.add('visible');
        setTimeout(() => {
            const cards = subRow.querySelectorAll('.sub-card');
            if (cards.length > 1) {
                const first = cards[0].getBoundingClientRect();
                const last  = cards[cards.length - 1].getBoundingClientRect();
                const row   = subRow.getBoundingClientRect();
                subRow.style.setProperty('--bar-left', (first.left + first.width / 2 - row.left) + 'px');
                subRow.style.setProperty('--bar-w',    (last.left  + last.width  / 2 - row.left - (first.left + first.width / 2 - row.left)) + 'px');
            }
            cards.forEach(c => c.classList.add('shown'));
        }, 60);
    });
}

// ── Sub-card click ─────────────────────────────────
async function onSubClick(cardEl, item) {
    if (activeCat === 'items' && item.name === 'Сокровища') {
        document.querySelectorAll('.sub-card').forEach(c => c.classList.remove('active'));
        cardEl.classList.add('active');
        activeProfession = { name: 'Сокровища', icon: '💎', source: { mode: 'treasure' } };
        collapseInteract();

        const interactArea  = document.getElementById('interactArea');
        const interactTitle = document.getElementById('interactTitle');
        const locGrid       = document.getElementById('locGrid');
        const searchBtn     = document.getElementById('searchBtn');

        interactArea.classList.add('visible');
        document.getElementById('param1Section').classList.remove('show');
        interactTitle.textContent = '💎 Сокровища';
        locGrid.innerHTML = '';

        activeLocation = { name: 'Сокровище' };
        searchBtn.style.display = '';
        searchBtn.disabled = false;
        searchBtn.textContent = '💎 Найти';
        return;
    }

    if (activeCat === 'items' && item.name === 'Сундуки') {
        document.querySelectorAll('.sub-card').forEach(c => c.classList.remove('active'));
        cardEl.classList.add('active');
        activeProfession = { name: 'Сундуки', icon: '📦', source: { mode: 'chests' } };
        collapseInteract();

        const interactArea  = document.getElementById('interactArea');
        const interactTitle = document.getElementById('interactTitle');
        const locGrid       = document.getElementById('locGrid');
        const param1Section = document.getElementById('param1Section');
        const param1Grid    = document.getElementById('param1Grid');

        interactArea.classList.add('visible');
        param1Section.classList.add('show');
        param1Grid.innerHTML = '';
        [
            { key: 'common',  name: 'Обычный деревянный сундук', icon: '📦' },
            { key: 'metal',   name: 'Сундук с металлической оковкой', icon: '🗃' },
            { key: 'special', name: 'Особое хранилище',          icon: '🔒' },
            { key: 'magic',   name: 'Магический сундук',          icon: '✨' },
        ].forEach(opt => {
            const btn = document.createElement('button');
            btn.className = 'param1-btn';
            btn.innerHTML = `<span class="p1-icon">${opt.icon}</span>${opt.name}`;
            btn.onclick = () => selectChestRarity(btn, opt);
            param1Grid.appendChild(btn);
        });
        interactTitle.textContent = 'Выбери сундук';
        locGrid.innerHTML = '<span style="color:#3a3020;font-size:0.8rem;font-style:italic">Сначала выбери редкость выше</span>';
        document.getElementById('searchBtn').style.display = 'none';
        return;
    }

    if (activeCat === 'items' && item.name === 'Торговцы') {
        document.querySelectorAll('.sub-card').forEach(c => c.classList.remove('active'));
        cardEl.classList.add('active');
        activeProfession = { name: 'Торговцы', icon: '🏪', source: { mode: 'traders' } };
        collapseInteract();

        const interactArea  = document.getElementById('interactArea');
        const interactTitle = document.getElementById('interactTitle');
        const locGrid       = document.getElementById('locGrid');
        const param1Section = document.getElementById('param1Section');
        const param1Grid    = document.getElementById('param1Grid');

        interactArea.classList.add('visible');
        param1Section.classList.add('show');
        param1Grid.innerHTML = '';
        [
            { key: 'standard', name: 'Стандартные', icon: '🏪' },
            { key: 'named',    name: 'Именные',     icon: '👤' },
        ].forEach(opt => {
            const btn = document.createElement('button');
            btn.className = 'param1-btn';
            btn.innerHTML = `<span class="p1-icon">${opt.icon}</span>${opt.name}`;
            btn.onclick = () => selectTraderType(btn, opt);
            param1Grid.appendChild(btn);
        });
        interactTitle.textContent = 'Выбери торговца';
        locGrid.innerHTML = '<span style="color:#3a3020;font-size:0.8rem;font-style:italic">Сначала выбери тип выше</span>';
        return;
    }

    if (activeCat === 'story') {
        document.querySelectorAll('.sub-card').forEach(c => c.classList.remove('active'));
        cardEl.classList.add('active');

        const modeMap = { 'Мотивация': 'story_motivation', 'Событие': 'story_event', 'Дозор': 'story_patrol' };
        activeProfession = { name: item.name, icon: item.icon, source: { mode: modeMap[item.name] } };
        collapseInteract();

        const interactArea  = document.getElementById('interactArea');
        const interactTitle = document.getElementById('interactTitle');
        const searchBtn     = document.getElementById('searchBtn');

        interactArea.classList.add('visible');
        document.getElementById('param1Section').classList.remove('show');
        document.getElementById('locGrid').innerHTML = '';
        interactTitle.textContent = `${item.icon} ${item.name}`;

        activeLocation = { name: item.name };
        searchBtn.style.display = '';
        searchBtn.disabled = false;
        searchBtn.textContent = '🎲 Зароллить';
        return;
    }

    if (activeCat !== 'professions') return;

    document.querySelectorAll('.sub-card').forEach(c => c.classList.remove('active'));
    cardEl.classList.add('active');

    const source = PROFESSION_SOURCES[item.name];
    activeProfession = { name: item.name, icon: source.icon, source };
    collapseInteract();

    const interactArea  = document.getElementById('interactArea');
    const interactTitle = document.getElementById('interactTitle');
    const locGrid       = document.getElementById('locGrid');
    const param1Section = document.getElementById('param1Section');
    const param1Grid    = document.getElementById('param1Grid');

    interactArea.classList.add('visible');

    if (source.mode === 'multi') {
        // ── Two-step selection ──
        param1Section.classList.add('show');
        param1Grid.innerHTML = '';
        source.param1.forEach(opt => {
            const btn = document.createElement('button');
            btn.className = 'param1-btn';
            btn.innerHTML = `<span class="p1-icon">${opt.icon}</span>${opt.name}`;
            btn.onclick = () => selectParam1(btn, opt);
            param1Grid.appendChild(btn);
        });
        interactTitle.textContent = 'Выбери район';
        locGrid.innerHTML = '<span style="color:#3a3020;font-size:0.8rem;font-style:italic">Сначала выбери действие выше</span>';

    } else if (source.mode === 'with_locations') {
        // ── Fetch location list from backend ──
        param1Section.classList.remove('show');
        interactTitle.textContent = `${source.icon} ${item.name} — выбери место`;
        locGrid.innerHTML = '<span class="loc-loading">Загружаем...</span>';
        try {
            const r = await fetch(`/api/play/profession/${encodeURIComponent(item.name)}/locations`);
            if (!r.ok) throw new Error(`HTTP ${r.status}`);
            const { locations } = await r.json();
            locGrid.innerHTML = '';
            locations.forEach(loc => {
                const btn = document.createElement('button');
                btn.className = 'loc-btn';
                btn.textContent = loc.name;
                btn.onclick = () => selectLocation(btn, { name: loc.name, locationKey: loc.key });
                locGrid.appendChild(btn);
            });
        } catch (err) {
            locGrid.innerHTML = `<span style="color:#6a2a1a;font-size:.8rem">${err.message}</span>`;
        }
    }
}

// ── Param1 selection (action type for multi-mode) ──
function selectParam1(btn, opt) {
    document.querySelectorAll('.param1-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    activeParam1 = opt;
    activeLocation = null;
    document.getElementById('searchBtn').disabled = true;

    const source  = activeProfession.source;
    const locGrid = document.getElementById('locGrid');

    locGrid.innerHTML = '';
    source.param2.forEach(p2 => {
        const distBtn = document.createElement('button');
        distBtn.className = 'loc-btn';
        distBtn.textContent = `${p2.icon} ${p2.name}`;
        distBtn.onclick = () => selectLocation(distBtn, {
            name: `${opt.name} · ${p2.name}`,
            param1Key: opt.key,
            param2Key: p2.key,
        });
        locGrid.appendChild(distBtn);
    });
}

// ── Trader type selection ──────────────────────────
async function selectTraderType(btn, opt) {
    document.querySelectorAll('.param1-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    activeLocation = null;
    document.getElementById('searchBtn').disabled = true;

    const locGrid = document.getElementById('locGrid');
    locGrid.innerHTML = '<span class="loc-loading">Загружаем...</span>';

    if (opt.key === 'standard') {
        locGrid.innerHTML = '';
        TRADER_TEMPLATES.forEach(tmpl => {
            const tBtn = document.createElement('button');
            tBtn.className = 'loc-btn';
            tBtn.textContent = `${tmpl.icon} ${tmpl.name}`;
            tBtn.onclick = () => selectStandardTrader(tBtn, tmpl);
            locGrid.appendChild(tBtn);
        });
    } else {
        try {
            const r = await fetch('/api/play/traders/named');
            if (!r.ok) throw new Error(`HTTP ${r.status}`);
            const stores = await r.json();
            locGrid.innerHTML = '';
            stores.forEach(store => {
                const sBtn = document.createElement('button');
                sBtn.className = 'loc-btn';
                sBtn.textContent = store.name;
                sBtn.onclick = () => selectNamedTrader(sBtn, store);
                locGrid.appendChild(sBtn);
            });
        } catch (err) {
            locGrid.innerHTML = `<span style="color:#6a2a1a;font-size:.8rem">${err.message}</span>`;
        }
    }
}

function selectStandardTrader(btn, tmpl) {
    document.querySelectorAll('.loc-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('searchBtn').style.display = 'none';
    showTraderInventory('standard', tmpl.key);
}

function selectNamedTrader(btn, store) {
    document.querySelectorAll('.loc-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('searchBtn').style.display = 'none';
    showTraderInventory('named', store.key);
}

async function showTraderInventory(subtype, key) {
    const inv = document.getElementById('traderInventory');
    inv.innerHTML = '<span class="loc-loading">Загружаем...</span>';
    inv.classList.add('show');
    document.getElementById('interactArea').classList.add('trader-mode');
    activeLocation = { name: key, subtype, key };
    try {
        const r = await fetch(`/api/play/traders/inventory/${subtype}/${encodeURIComponent(key)}`);
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const { items } = await r.json();
        if (!items.length) {
            inv.innerHTML = '<span style="color:#3a3020;font-size:0.8rem;font-style:italic">Нет товаров</span>';
            return;
        }
        inv.innerHTML = items.map(it => {
            const badge = it.unique ? '<span class="inv-badge">✦</span>' : '';
            const propsHtml = it.properties && it.properties.length > 0
                ? `<div style="font-size:0.85rem;color:#8b949e;margin-top:2px">${it.properties.join(', ')}</div>`
                : '';
            return `<div class="inv-row">
                <div>
                    <span class="inv-name${it.unique ? ' unique' : ''}">${it.name}${badge}</span>
                    ${propsHtml}
                </div>
                ${it.price ? `<span class="inv-price">${it.price} зол.</span>` : ''}
            </div>`;
        }).join('');
    } catch (err) {
        inv.innerHTML = `<span style="color:#6a2a1a;font-size:.8rem">${err.message}</span>`;
    }
}

// ── Chest rarity selection ─────────────────────────
function selectChestRarity(btn, opt) {
    console.log('selectChestRarity called with:', opt);
    document.querySelectorAll('.param1-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');

    // Store chest key for later use (don't set activeLocation yet - it triggers other code)
    window.selectedChestKey = opt.key;
    window.selectedChestName = opt.name;

    document.getElementById('locGrid').innerHTML = '';

    // Hide search button and show chest game area
    const searchBtn = document.getElementById('searchBtn');
    searchBtn.style.display = 'none';
    searchBtn.disabled = true;
    console.log('searchBtn hidden');

    // Start chest game immediately
    if (typeof ChestGame !== 'undefined' && ChestGame.show && ChestGame.start) {
        console.log('ChestGame exists, calling show and start');
        ChestGame.show();
        ChestGame.start(opt.key);
    } else {
        console.error('ChestGame module not loaded');
    }
}

// ── Location selection ─────────────────────────────
function selectLocation(btn, loc) {
    document.querySelectorAll('.loc-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    activeLocation = loc;
    document.getElementById('searchBtn').disabled = false;
}

// ── Result popup ───────────────────────────────────
function showResultPopup(result) {
    const popup = document.getElementById('resultPopup');
    let html, duration;

    if (result.items !== undefined) {
        // Cache result: gold + items list
        popup.classList.add('multi');
        const goldLine = result.gold > 0 ? `<div class="result-popup-sub">💰 ${result.gold} зол.</div>` : '';
        const itemsHtml = result.items.length
            ? result.items.map(i => `<div class="result-popup-item">${i}</div>`).join('')
            : '';
        html = `<div class="result-popup-name">${result.name}</div>${goldLine}${itemsHtml ? `<div class="result-popup-items">${itemsHtml}</div>` : ''}`;
        duration = 4500;
    } else {
        popup.classList.remove('multi');
        const isNothing = /ничего/i.test(result.name);
        const catLine  = result.category ? `<div class="result-popup-cat">${result.category}</div>` : '';
        const subText  = !result.category && result.price && activeProfession.name !== 'Следы' ? `${result.price} зол.`
                       : !result.category && result.amount ? `×${result.amount}`
                       : '';
        const subLine  = subText ? `<div class="result-popup-sub">${subText}</div>` : '';
        html = `${catLine}<div class="result-popup-name${isNothing ? ' nothing' : ''}">${result.name}</div>${subLine}`;
        duration = 2800;
    }

    popup.innerHTML = html;
    popup.classList.remove('show');
    clearTimeout(popup._timer);
    requestAnimationFrame(() => {
        popup.classList.add('show');
        popup._timer = setTimeout(() => popup.classList.remove('show'), duration);
    });
}

// ── Search / roll ──────────────────────────────────
async function _doRollRequest() {
    const mode = activeProfession.source.mode;
    let body;
    if (mode === 'treasure') {
        body = { type: 'treasure' };
    } else if (mode === 'chests') {
        body = { type: 'chests', chest: activeLocation.chestKey };
    } else if (mode === 'with_locations') {
        body = { type: 'profession', profession: activeProfession.name, location: activeLocation.locationKey };
    } else if (mode === 'multi') {
        body = { type: 'profession', profession: 'Воровство', param1: activeLocation.param1Key, param2: activeLocation.param2Key };
    } else {
        throw new Error(`Unknown mode: ${mode}`);
    }
    const r = await fetch('/api/play/roll', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
    });
    if (!r.ok) {
        const err = await r.json().catch(() => ({}));
        throw new Error(err.detail || `HTTP ${r.status}`);
    }
    return r.json();
}

async function doStoryRoll(mode) {
    const btn = document.getElementById('searchBtn');
    btn.disabled = true;
    btn.classList.add('searching');
    btn.textContent = '⏳ Роллим...';

    await new Promise(r => setTimeout(r, 280 + Math.random() * 200));

    try {
        if (mode === 'story_motivation') {
            const r = await fetch('/api/play/story/motivation', { method: 'POST' });
            if (!r.ok) throw new Error(`HTTP ${r.status}`);
            const { motivations } = await r.json();
            const inv = document.getElementById('traderInventory');
            inv.innerHTML = motivations.map(m =>
                `<div class="inv-row"><span class="inv-name">${_esc(m)}</span></div>`
            ).join('');
            inv.classList.add('show');
            document.getElementById('interactArea').classList.add('trader-mode');
        } else {
            // stub: random 1-10
            const value = Math.floor(Math.random() * 10) + 1;
            showResultPopup({ name: String(value) });
        }
    } catch (err) {
        showResultPopup({ name: `Ошибка: ${err.message}` });
    } finally {
        btn.disabled = false;
        btn.classList.remove('searching');
        btn.textContent = '🎲 Зароллить';
    }
}

async function doSearch() {
    if (!activeProfession || !activeLocation) return;

    const mode = activeProfession.source.mode;
    if (mode === 'story_motivation' || mode === 'story_event' || mode === 'story_patrol') {
        await doStoryRoll(mode);
        return;
    }

    // Chest game is handled separately via ChestGame module
    if (mode === 'chests') {
        return;
    }

    const btn = document.getElementById('searchBtn');
    btn.disabled = true;
    btn.classList.add('searching');
    btn.textContent = activeProfession.source.mode === 'chests' ? '⏳ Открываем...' : '⏳ Ищем...';

    // Small artificial delay for feel
    await new Promise(r => setTimeout(r, 280 + Math.random() * 200));

    try {
        const result = await _doRollRequest();
        showResultPopup(result);
        const time = new Date().toLocaleTimeString('ru', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
        await postLog({
            profIcon: activeProfession.icon,
            profName: activeProfession.name,
            locName:  activeLocation.name,
            result,
            time,
        });
    } finally {
        btn.disabled = false;
        btn.classList.remove('searching');
        const finalMode = activeProfession?.source?.mode;
        btn.textContent = finalMode === 'treasure' ? '💎 Найти'
                        : finalMode === 'chests'   ? '🗝 Открыть'
                        : '⚔ Ищем';
    }
}

// ── Log ────────────────────────────────────────────
let logOffset = 0;

function _esc(s) {
    return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

function renderLogEntry({ profIcon, profName, locName, result, time, user }) {
    const entries = document.getElementById('logEntries');
    const empty = entries.querySelector('.log-empty');
    if (empty) empty.remove();

    let isNothing, resultHtml;
    if (result.items !== undefined) {
        isNothing = false;
        const parts = [];
        if (result.gold > 0) parts.push(`💰 ${result.gold} зол.`);
        parts.push(...result.items);
        resultHtml = parts.join(' · ');
    } else {
        isNothing = /ничего/i.test(result.name);
        const catLine = result.category ? `<span class="log-category">${result.category}</span>` : '';
        resultHtml = `${catLine}${result.name}${result.amount ? `<span class="log-amount">×${result.amount}</span>` : result.price && profName !== 'Следы' ? `<span class="log-amount">${result.price} зол.</span>` : ''}`;
    }

    const userLine = user
        ? `<span class="log-user">${_esc(user)}</span><span class="log-meta-sep">·</span>`
        : '';
    const entry = document.createElement('div');
    entry.className = 'log-entry';
    entry.innerHTML = `
        <div class="log-meta">
            ${userLine}<span>${profIcon} ${profName}</span>
            <span class="log-meta-sep">·</span>
            <span>${locName}</span>
            <span class="log-meta-sep">·</span>
            <span>${time}</span>
        </div>
        <div class="log-result${isNothing ? ' nothing' : ''}">
            ${resultHtml}
        </div>`;
    entries.appendChild(entry);
    entries.scrollTop = entries.scrollHeight;
}

async function postLog(logData) {
    renderLogEntry({ ...logData, user: currentUser });
    try {
        const r = await fetch('/api/log', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(logData),
        });
        const { total } = await r.json();
        logOffset = total;
    } catch {}
}

async function pollLog() {
    try {
        const r = await fetch(`/api/log?after=${logOffset}`);
        const { entries, total } = await r.json();
        if (entries.length > 0) {
            entries.forEach(e => renderLogEntry(e));
            logOffset = total;
        }
    } catch {}
}

async function clearLog() {
    const entries = document.getElementById('logEntries');
    entries.innerHTML = '<div class="log-empty">Результаты появятся здесь</div>';
    logOffset = 0;
    try { await fetch('/api/log', { method: 'DELETE' }); } catch {}
}

// Auth check on start, then load log and poll
initAuth();
pollLog();
setInterval(pollLog, 5000);
