/**
 * theme.js — Dark/light theme management.
 * Theme is stored in localStorage['theme'] and applied to <html data-theme="...">
 */

const STORAGE_KEY = 'theme';
const DEFAULT = 'dark';

export function getTheme() {
    return localStorage.getItem(STORAGE_KEY) || DEFAULT;
}

export function setTheme(theme) {
    localStorage.setItem(STORAGE_KEY, theme);
    document.documentElement.dataset.theme = theme;
}

export function toggleTheme() {
    const next = getTheme() === 'dark' ? 'light' : 'dark';
    setTheme(next);
    return next;
}

export function applyTheme() {
    document.documentElement.dataset.theme = getTheme();
}

/** Update toggle button icon/title */
export function updateToggleBtn(btn) {
    if (!btn) return;
    const isDark = getTheme() === 'dark';
    btn.textContent = isDark ? '☀️' : '🌙';
    btn.title = isDark ? 'Светлая тема' : 'Тёмная тема';
}
