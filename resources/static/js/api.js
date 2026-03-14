/**
 * api.js — Thin fetch wrappers that attach Authorization header automatically.
 * Imports token from auth.js via getToken().
 */

import { getToken, refreshToken } from './auth.js';

async function _fetch(url, options = {}) {
    const token = getToken();
    const headers = { 'Content-Type': 'application/json', ...options.headers };
    if (token) headers['Authorization'] = `Bearer ${token}`;

    let res = await fetch(url, { ...options, headers });

    // Try to refresh on 401
    if (res.status === 401 && token) {
        const refreshed = await refreshToken();
        if (refreshed) {
            headers['Authorization'] = `Bearer ${getToken()}`;
            res = await fetch(url, { ...options, headers });
        }
    }

    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || `HTTP ${res.status}`);
    }
    return res.json();
}

export const api = {
    get:    (url)           => _fetch(url),
    post:   (url, body)     => _fetch(url, { method: 'POST',   body: JSON.stringify(body) }),
    patch:  (url, body)     => _fetch(url, { method: 'PATCH',  body: JSON.stringify(body) }),
    delete: (url)           => _fetch(url, { method: 'DELETE' }),

    // Raw fetch without JSON parse (for 204 responses)
    deleteRaw: (url) => {
        const token = getToken();
        const headers = {};
        if (token) headers['Authorization'] = `Bearer ${token}`;
        return fetch(url, { method: 'DELETE', headers });
    },
};
