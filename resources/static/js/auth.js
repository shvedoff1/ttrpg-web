/**
 * auth.js — Auth state: token storage, user info, refresh.
 */

const TOKEN_KEY   = 'access_token';
const USER_KEY    = 'user_info';
const GAME_ID_KEY = 'current_game_id';

// ── Token management ──────────────────────────────────────────────────────

export function getToken() {
    return sessionStorage.getItem(TOKEN_KEY) || localStorage.getItem(TOKEN_KEY);
}

export function setToken(token) {
    sessionStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
    sessionStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
}

// ── User info ─────────────────────────────────────────────────────────────

export function getUser() {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? JSON.parse(raw) : null;
}

export function setUser(user) {
    localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function getDisplayName(user) {
    if (!user) return '';
    return user.username || user.email?.split('@')[0] || '';
}

// ── Game selection ────────────────────────────────────────────────────────

export function getCurrentGameId() {
    const fromUrl = new URLSearchParams(window.location.search).get('game');
    if (fromUrl) return parseInt(fromUrl);
    const stored = localStorage.getItem(GAME_ID_KEY);
    return stored ? parseInt(stored) : null;
}

export function setCurrentGameId(id) {
    localStorage.setItem(GAME_ID_KEY, String(id));
}

// ── Refresh ───────────────────────────────────────────────────────────────

export async function refreshToken() {
    try {
        const res = await fetch('/auth/refresh', { method: 'POST' });
        if (!res.ok) return false;
        const data = await res.json();
        setToken(data.access_token);
        if (data.username !== undefined) {
            const user = getUser() || {};
            setUser({ ...user, username: data.username, email: data.email || user.email });
        }
        return true;
    } catch {
        return false;
    }
}

// ── Logout ────────────────────────────────────────────────────────────────

export async function logout() {
    await fetch('/auth/logout', { method: 'POST' }).catch(() => {});
    clearToken();
    window.location.href = '/login';
}

// ── Init: pick up token from URL (after OAuth redirect) ──────────────────

export function initFromUrl() {
    const params = new URLSearchParams(window.location.search);
    const token = params.get('access_token');
    if (token) {
        setToken(token);
        // Clean URL
        const clean = window.location.pathname + (params.get('game') ? `?game=${params.get('game')}` : '');
        window.history.replaceState({}, '', clean);
    }
}

// ── Fetch current user from API ───────────────────────────────────────────

export async function fetchMe() {
    const token = getToken();
    if (!token) return null;
    try {
        const res = await fetch('/auth/me', {
            headers: { 'Authorization': `Bearer ${token}` },
        });
        if (!res.ok) return null;
        const user = await res.json();
        setUser(user);
        return user;
    } catch {
        return null;
    }
}
