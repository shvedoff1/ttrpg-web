/**
 * log.js — Journal: polling, rendering, posting entries.
 *
 * Entry visibility:
 *   "public"  — visible to all authenticated users
 *   "admin"   — visible only to admin/owner roles
 *
 * Log channels (UI tabs):
 *   "all"     — show all entries (public + admin) — for admins only
 *   "public"  — show only public entries
 */

import { getToken, getUser } from './auth.js';
import { api } from './api.js';

let _gameId     = null;
let _lastId     = 0;
let _channel    = 'public';   // current log tab
let _isAdmin    = false;
let _pollTimer  = null;
let _abortCtrl  = null;       // AbortController for event listeners
const POLL_MS   = 5000;

// ── Init ──────────────────────────────────────────────────────────────────

export function initLog({ gameId, isAdmin, listEl, tabsEl, clearBtn }) {
    // Abort previous event listeners before re-initializing
    if (_abortCtrl) _abortCtrl.abort();
    _abortCtrl = new AbortController();
    const { signal } = _abortCtrl;

    _gameId  = gameId;
    _isAdmin = isAdmin;
    _channel = isAdmin ? 'all' : 'public';
    _lastId  = _getLocalClear();

    // Clear displayed entries from previous game
    if (listEl) listEl.innerHTML = '';

    // Build log tabs dynamically if container is empty
    if (tabsEl && !tabsEl.children.length && isAdmin) {
        const allTab = document.createElement('button');
        allTab.className = 'log-tab active';
        allTab.dataset.channel = 'all';
        allTab.textContent = 'Все';

        const pubTab = document.createElement('button');
        pubTab.className = 'log-tab';
        pubTab.dataset.channel = 'public';
        pubTab.textContent = 'Общий';

        tabsEl.append(allTab, pubTab);
    }

    // Show admin tab only for admins
    const adminTab = tabsEl?.querySelector('[data-channel="admin"]');
    if (adminTab) adminTab.style.display = isAdmin ? '' : 'none';

    // Tab switching
    tabsEl?.querySelectorAll('.log-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            _channel = tab.dataset.channel;
            tabsEl.querySelectorAll('.log-tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            _lastId = _getLocalClear();
            if (listEl) listEl.innerHTML = '';
            _poll(listEl);
        }, { signal });
    });

    clearBtn?.addEventListener('click', async () => {
        if (_isAdmin) {
            // Server-side clear — admin only
            await api.delete(`/api/games/${_gameId}/log`);
            _lastId = 0;
            _saveLocalClear(0);
            if (listEl) listEl.innerHTML = '';
        } else {
            // Local clear — save last seen id in cookie, hide on frontend
            _saveLocalClear(_lastId);
            if (listEl) listEl.innerHTML = '';
        }
    }, { signal });

    _poll(listEl);
    _pollTimer = setInterval(() => _poll(listEl), POLL_MS);
}

export function stopLog() {
    if (_pollTimer) clearInterval(_pollTimer);
}

// ── Cookie helpers ────────────────────────────────────────────────────────

function _saveLocalClear(lastId) {
    document.cookie = `log_clear_${_gameId}=${lastId};path=/;max-age=2592000`;
}

function _getLocalClear() {
    if (!_gameId) return 0;
    const m = document.cookie.match(new RegExp(`log_clear_${_gameId}=(\\d+)`));
    return m ? parseInt(m[1]) : 0;
}

// ── Polling ───────────────────────────────────────────────────────────────

async function _poll(listEl) {
    if (!listEl || !_gameId) return;
    try {
        const params = new URLSearchParams({ after_id: _lastId });

        const token = getToken();
        const headers = token ? { 'Authorization': `Bearer ${token}` } : {};
        const res  = await fetch(`/api/games/${_gameId}/log?${params}`, { headers });
        if (!res.ok) return;
        const data = await res.json();

        if (!data.entries?.length) return;

        const frag = document.createDocumentFragment();
        for (const entry of data.entries) {
            // Filter by current channel
            if (_channel === 'public' && entry.visibility === 'admin') continue;
            frag.appendChild(_renderEntry(entry));
        }
        listEl.appendChild(frag);
        if (data.last_id) _lastId = data.last_id;

        // Scroll to bottom
        listEl.scrollTop = listEl.scrollHeight;
    } catch {
        // Silent — network may be down
    }
}

// ── Posting ───────────────────────────────────────────────────────────────

export async function postLog(entryData, visibility = 'public') {
    if (!_gameId) return;
    try {
        await api.post(`/api/games/${_gameId}/log`, { data: entryData, visibility });
    } catch {
        // Non-critical
    }
}

// ── Rendering ─────────────────────────────────────────────────────────────

function _renderEntry(entry) {
    const div = document.createElement('div');
    div.className = 'log-entry';

    const time = entry.timestamp
        ? new Date(entry.timestamp).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
        : '';

    const user = entry.user ? `<span class="log-meta-user">${_esc(entry.user)}</span>` : '';
    const adminBadge = entry.visibility === 'admin'
        ? '<span class="log-meta-admin">🔒 мастер</span>'
        : '';

    const icon = entry.icon || '◆';
    const meta = `<div class="log-entry-meta">
        <span class="log-meta-icon">${icon}</span>
        ${user}
        ${adminBadge}
        <span class="log-meta-time">${time}</span>
    </div>`;

    let body = '';
    if (entry.items && Array.isArray(entry.items)) {
        // Multi-item result (cache/chest)
        const goldLine = entry.gold != null ? `<div class="log-entry-multi-gold">🪙 ${entry.gold}</div>` : '';
        const items = entry.items.map(i => `<div class="log-entry-multi-item">• ${_esc(i)}</div>`).join('');
        body = `<div class="log-entry-multi">
            <div class="log-entry-main">${_esc(entry.name || '')}</div>
            ${goldLine}${items}
        </div>`;
    } else if (entry.motivations && Array.isArray(entry.motivations)) {
        const motItems = entry.motivations.map(m => `<div class="log-entry-multi-item">• ${_esc(m)}</div>`).join('');
        body = `<div class="log-entry-main">Мотивации</div><div>${motItems}</div>`;
    } else {
        const name  = entry.name  ? `<div class="log-entry-main">${_esc(entry.name)}</div>` : '';
        const price = entry.price != null ? `<div class="log-entry-sub">🪙 ${entry.price}</div>` : '';
        const weight = entry.weight != null ? `<div class="log-entry-sub">⚖️ ${entry.weight}</div>` : '';
        const cat   = entry.category ? `<div class="log-entry-sub">${_esc(entry.category)}</div>` : '';
        const desc  = entry.description ? `<div class="log-entry-sub">${_esc(entry.description)}</div>` : '';
        body = name + price + weight + cat + desc;
    }

    div.innerHTML = meta + body;
    return div;
}

function _esc(str) {
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}
