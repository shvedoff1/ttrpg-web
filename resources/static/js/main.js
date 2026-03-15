/**
 * main.js — Play page entry point.
 * Orchestrates auth, theme, engine tabs, and journal.
 */

import { initFromUrl, fetchMe, getUser, getDisplayName, getCurrentGameId, setCurrentGameId, logout } from './auth.js';
import { applyTheme, toggleTheme, updateToggleBtn } from './theme.js';
import { initLog, stopLog, postLog as rawPostLog } from './log.js';
import { renderEngine, engineIcon } from './engines/index.js';
import { api } from './api.js';

// ── State ─────────────────────────────────────────────────────────────────

let currentGameId   = null;
let currentRole     = null;
let gameEngines     = [];
let activeEngineIdx = null;

// ── DOM refs ──────────────────────────────────────────────────────────────

const gameTitle     = document.getElementById('gameTitle');
const userNameEl    = document.getElementById('userName');
const gameSelect    = document.getElementById('gameSelect');
const themeToggleEl = document.getElementById('themeToggle');
const logoutBtn     = document.getElementById('logoutBtn');
const loginBtn      = document.getElementById('loginBtn');
const engineTabsEl  = document.getElementById('engineTabs');
const engineContent = document.getElementById('engineContent');
const logEntriesEl  = document.getElementById('logEntries');
const logTabsEl     = document.getElementById('logTabs');
const clearLogBtn   = document.getElementById('clearLogBtn');

// ── Init ──────────────────────────────────────────────────────────────────

async function init() {
    applyTheme();
    updateToggleBtn(themeToggleEl);

    initFromUrl();

    themeToggleEl?.addEventListener('click', () => {
        toggleTheme();
        updateToggleBtn(themeToggleEl);
    });

    logoutBtn?.addEventListener('click', logout);

    const user = await fetchMe();
    if (user) {
        userNameEl.textContent = getDisplayName(user);
        if (loginBtn)   loginBtn.style.display  = 'none';
        if (logoutBtn)  logoutBtn.style.display  = '';
        if (userNameEl) userNameEl.style.display = '';
        await loadGames(user);
    } else {
        // Not logged in — show login button, hide user info
        if (loginBtn)   loginBtn.style.display  = '';
        if (logoutBtn)  logoutBtn.style.display  = 'none';
        if (userNameEl) userNameEl.style.display = 'none';
        showEmptyEngines('Войдите, чтобы видеть движки игры');
    }
}

// ── Games ─────────────────────────────────────────────────────────────────

async function loadGames(user) {
    try {
        const games = await api.get('/api/games');
        if (!games.length) {
            showEmptyEngines('Вы не участвуете ни в одной игре. <a href="/games">Создать</a>');
            return;
        }

        // Populate game selector
        gameSelect.innerHTML = '';
        games.forEach(g => {
            const opt = document.createElement('option');
            opt.value = g.id;
            opt.textContent = g.name;
            gameSelect.appendChild(opt);
        });
        gameSelect.style.display = '';

        // Restore saved game or use first
        const savedId = getCurrentGameId();
        const target  = games.find(g => g.id === savedId) || games[0];
        gameSelect.value = target.id;

        gameSelect.addEventListener('change', () => {
            const id = parseInt(gameSelect.value);
            setCurrentGameId(id);
            history.replaceState(null, '', `?game=${id}`);
            stopLog();
            loadGame(id, games.find(g => g.id === id));
        });

        // Sync URL with the selected game on initial load
        history.replaceState(null, '', `?game=${target.id}`);
        await loadGame(target.id, target);
    } catch (e) {
        showEmptyEngines(`Ошибка загрузки игр: ${e.message}`);
    }
}

async function loadGame(gameId, gameData) {
    currentGameId = gameId;
    setCurrentGameId(gameId);

    if (gameTitle) gameTitle.textContent = gameData?.name || 'TTRPG';

    // Determine role
    currentRole = gameData?.role || 'player';
    const isAdmin = ['admin', 'owner'].includes(currentRole);

    // Init journal
    initLog({
        gameId,
        isAdmin,
        listEl:   logEntriesEl,
        tabsEl:   logTabsEl,
        clearBtn: clearLogBtn,
    });

    // Load engines
    await loadEngines(gameId);
}

// ── Engines ───────────────────────────────────────────────────────────────

async function loadEngines(gameId) {
    engineTabsEl.innerHTML = '';
    engineContent.innerHTML = '<div class="engine-loading">Загрузка движков...</div>';

    try {
        gameEngines = await api.get(`/api/games/${gameId}/engines`);
    } catch (e) {
        showEmptyEngines(`Ошибка: ${e.message}`);
        return;
    }

    if (!gameEngines.length) {
        showEmptyEngines('В этой игре нет движков. <a href="/games">Добавить</a>');
        return;
    }

    // Build tabs
    gameEngines.forEach((eng, idx) => {
        const tab = document.createElement('button');
        tab.className = 'engine-tab' + (idx === 0 ? ' active' : '');

        // Category → use meta.icon; system engine → engineIcon()
        const icon = eng.meta?.icon || engineIcon(eng.engine_id || eng.meta?.base_engine_id || 'composite');
        tab.innerHTML = `<span class="engine-tab-icon">${icon}</span><span class="engine-tab-name">${eng.meta?.name || eng.engine_id || 'Движок'}</span>`;
        tab.addEventListener('click', () => selectEngine(idx));
        engineTabsEl.appendChild(tab);
    });

    selectEngine(0);
}

async function selectEngine(idx) {
    activeEngineIdx = idx;

    // Update tab highlight
    engineTabsEl.querySelectorAll('.engine-tab').forEach((t, i) => {
        t.classList.toggle('active', i === idx);
    });

    const rec = gameEngines[idx];
    if (!rec) return;

    engineContent.innerHTML = '<div class="engine-loading">Загрузка...</div>';

    await renderEngine(engineContent, rec, currentGameId, postLog);
}

function showEmptyEngines(html) {
    engineTabsEl.innerHTML  = `<div class="engine-tabs-empty">${html}</div>`;
    engineContent.innerHTML = '';
}

// ── postLog wrapper ───────────────────────────────────────────────────────

async function postLog(data, visibility = 'public') {
    // Determine visibility from engine's log_routing config if available
    const rec = gameEngines[activeEngineIdx];
    const routing = rec?.config?.log_routing;
    if (routing) {
        const action = data.action || '*';
        const routed = routing[action] || routing['*'] || visibility;
        visibility   = routed;
    }
    await rawPostLog(data, visibility);
}

// ── Start ─────────────────────────────────────────────────────────────────

init();
