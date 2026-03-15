/**
 * app-header.js — Shared app header for non-play pages.
 *
 * Usage: <script src="/js/app-header.js" data-page="games"></script>
 * Place a <header id="app-header"></header> where the header should go.
 *
 * data-page values: games | my-engines | resources | engine-config | changelog
 */

(function () {
    // ── Theme ──────────────────────────────────────────────────────────────
    window.toggleTheme = function () {
        const next = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
        document.documentElement.dataset.theme = next;
        localStorage.setItem('theme', next);
        _updateThemeBtn();
    };

    function _updateThemeBtn() {
        const btn = document.getElementById('app-header-theme');
        if (!btn) return;
        const isDark = (document.documentElement.dataset.theme || 'dark') === 'dark';
        btn.textContent = isDark ? '☀️' : '🌙';
        btn.title = isDark ? 'Светлая тема' : 'Тёмная тема';
    }

    // ── Logout ─────────────────────────────────────────────────────────────
    window.logout = function () {
        fetch('/auth/logout', { method: 'POST' }).catch(() => {});
        localStorage.removeItem('access_token');
        sessionStorage.removeItem('access_token');
        localStorage.removeItem('user_info');
        window.location.href = '/login';
    };

    // ── Render ─────────────────────────────────────────────────────────────
    const NAV_LINKS = [
        { href: '/play',       label: '▶ Игра',        page: 'play'          },
        { href: '/games',      label: 'Мои игры',       page: 'games'         },
        { href: '/my-engines', label: 'Категории',       page: 'my-engines'    },
        { href: '/resources',  label: 'Ресурсы',         page: 'resources'     },
        { href: '/changelog',  label: 'Что нового',     page: 'changelog'     },
    ];

    function _getUsername() {
        try {
            const raw = localStorage.getItem('user_info');
            if (!raw) return null;
            const u = JSON.parse(raw);
            return u.username || u.email?.split('@')[0] || null;
        } catch { return null; }
    }

    function _render() {
        const container = document.getElementById('app-header');
        if (!container) return;

        // Determine active page from script tag's data-page attribute
        const scripts = document.querySelectorAll('script[src*="app-header.js"]');
        const activePage = scripts[scripts.length - 1]?.dataset?.page || '';

        const username = _getUsername();

        const navHtml = NAV_LINKS.map(link => {
            const isActive = link.page === activePage;
            return `<a href="${link.href}" ${isActive ? 'class="active"' : ''}>${link.label}</a>`;
        }).join('');

        const authHtml = username
            ? `<span class="app-header-user" id="app-header-username">${username}</span>
               <button class="app-header-btn" id="app-header-theme" onclick="toggleTheme()" title="Сменить тему">🌙</button>
               <button class="app-header-btn" onclick="logout()">Выйти</button>`
            : `<span class="app-header-user" id="app-header-username" style="display:none"></span>
               <button class="app-header-btn" id="app-header-theme" onclick="toggleTheme()" title="Сменить тему">🌙</button>
               <a class="app-header-btn" href="/login">Войти</a>`;

        container.innerHTML = `
            <nav class="app-header-nav">${navHtml}</nav>
            <div class="app-header-auth">${authHtml}</div>
        `;

        const style = document.createElement('style');
        style.textContent = `
            #app-header {
                background: var(--bg2);
                border-bottom: 1px solid var(--border);
                padding: 10px 24px;
                display: flex;
                align-items: center;
                gap: 8px;
                flex-wrap: wrap;
            }
            .app-header-nav {
                display: flex;
                align-items: center;
                gap: 16px;
                flex: 1;
                flex-wrap: wrap;
            }
            .app-header-nav a {
                color: var(--muted);
                text-decoration: none;
                font-size: 0.9rem;
                white-space: nowrap;
            }
            .app-header-nav a:hover { color: var(--text); }
            .app-header-nav a.active { color: var(--gold); font-weight: 600; }
            .app-header-auth {
                display: flex;
                align-items: center;
                gap: 10px;
                font-size: 0.85rem;
            }
            .app-header-user {
                color: var(--gold);
            }
            .app-header-btn {
                background: none;
                border: 1px solid var(--border);
                border-radius: 6px;
                color: var(--muted);
                cursor: pointer;
                padding: 4px 10px;
                font-size: 0.82rem;
                text-decoration: none;
                display: inline-flex;
                align-items: center;
            }
            .app-header-btn:hover { color: var(--text); border-color: var(--gold); }
        `;
        document.head.appendChild(style);

        _updateThemeBtn();
    }

    /** Call this after fetching user from API to update the displayed name */
    window.updateHeaderUser = function (name) {
        const el = document.getElementById('app-header-username');
        if (el) el.textContent = name || '';
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', _render);
    } else {
        _render();
    }
})();
