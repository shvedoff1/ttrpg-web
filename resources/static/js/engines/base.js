/**
 * engines/base.js — Engine renderer base.
 *
 * Each engine renderer is a plain object with:
 *   render(container, engineRecord, gameId, postLog) → void
 *
 * engineRecord: { id, game_id, engine_id, user_engine_id, config, meta }
 * gameId:       number
 * postLog:      function(entryData, visibility?)
 */

export function makeWidget(title) {
    const widget = document.createElement('div');
    widget.className = 'engine-widget';
    if (title) {
        const t = document.createElement('div');
        t.className = 'engine-widget-title';
        t.textContent = title;
        widget.appendChild(t);
    }
    return widget;
}

export function makeOptionGrid(items, onSelect) {
    const grid = document.createElement('div');
    grid.className = 'option-grid';
    let active = null;

    items.forEach(item => {
        const btn = document.createElement('button');
        btn.className = 'option-btn';
        btn.textContent = item.name || item;
        btn.dataset.key = item.key || item;
        btn.addEventListener('click', () => {
            if (active) active.classList.remove('active');
            btn.classList.add('active');
            active = btn;
            onSelect(item.key || item, item.name || item);
        });
        grid.appendChild(btn);
    });

    return grid;
}

export function makeActionButton(label, onClick) {
    const wrap = document.createElement('div');
    wrap.className = 'result-wrap';

    const popup = document.createElement('div');
    popup.className = 'result-popup';
    wrap.appendChild(popup);

    const btn = document.createElement('button');
    btn.className = 'action-btn';
    btn.textContent = label;
    btn.addEventListener('click', async () => {
        btn.disabled = true;
        try {
            const result = await onClick();
            if (result) showPopup(popup, result);
        } finally {
            btn.disabled = false;
        }
    });
    wrap.appendChild(btn);

    return { wrap, popup, btn };
}

export function formatResult(container, data) {
    container.innerHTML = '';

    if (data.items && Array.isArray(data.items)) {
        container.classList.add('multi');
        const header = document.createElement('div');
        header.className = 'result-name';
        header.textContent = data.name || '';
        container.appendChild(header);

        if (data.gold != null) {
            const g = document.createElement('div');
            g.className = 'result-sub';
            g.textContent = `🪙 ${data.gold}`;
            container.appendChild(g);
        }

        const list = document.createElement('div');
        list.className = 'result-items';
        data.items.forEach(item => {
            const row = document.createElement('div');
            row.className = 'result-item';
            row.textContent = `• ${item}`;
            list.appendChild(row);
        });
        container.appendChild(list);
    } else if (data.motivations) {
        container.classList.add('multi');
        data.motivations.forEach(m => {
            const row = document.createElement('div');
            row.className = 'result-item';
            row.textContent = `• ${m}`;
            container.appendChild(row);
        });
    } else if (data.professions || data.chests || data.locations || data.modes) {
        // List-type responses (from get_professions, list, get_locations)
        const items = data.professions || data.chests || data.locations || data.modes || [];
        items.forEach(item => {
            const row = document.createElement('div');
            row.className = 'result-item';
            row.textContent = `• ${item.name || item.key || item}`;
            container.appendChild(row);
        });
    } else {
        const name = document.createElement('div');
        name.className = 'result-name' + (data.name === 'Ничего не нашли' ? ' nothing' : '');
        name.textContent = data.name || '—';
        container.appendChild(name);

        if (data.category) {
            const cat = document.createElement('div');
            cat.className = 'result-cat';
            cat.textContent = data.category;
            container.insertBefore(cat, name);
        }
        if (data.price != null) {
            const price = document.createElement('div');
            price.className = 'result-sub';
            price.textContent = `🪙 ${data.price}`;
            container.appendChild(price);
        }
        if (data.weight != null) {
            const weight = document.createElement('div');
            weight.className = 'result-sub';
            weight.textContent = `⚖️ ${data.weight}`;
            container.appendChild(weight);
        }
    }
}

export function showPopup(popup, data) {
    popup.className = 'result-popup';
    formatResult(popup, data);
    popup.classList.add('show');
    setTimeout(() => popup.classList.remove('show'), 5000);
}

export async function callCategoryAction(gameId, gameEngineId, catEngineId, action, payload = {}) {
    const token = (await import('../auth.js')).getToken();
    const headers = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const url = `/api/games/${gameId}/categories/${gameEngineId}/engines/${catEngineId}/action`;

    const res = await fetch(url, {
        method: 'POST',
        headers,
        body: JSON.stringify({ action, payload }),
    });
    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || `HTTP ${res.status}`);
    }
    return res.json();
}

export async function callAction(gameId, engineRecord, action, payload = {}) {
    const token = (await import('../auth.js')).getToken();
    const headers = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = `Bearer ${token}`;

    // For composite user engines, prefix mechanic index to action
    if (engineRecord._mechanicIndex !== undefined && engineRecord.user_engine_id) {
        action = `${engineRecord._mechanicIndex}:${action}`;
    }

    let url;
    if (engineRecord._categoryRoute) {
        // Category engine — route through category endpoint
        const { gameEngineId, catEngineId } = engineRecord._categoryRoute;
        url = `/api/games/${gameId}/categories/${gameEngineId}/engines/${catEngineId}/action`;
    } else if (engineRecord.user_engine_id) {
        url = `/api/games/${gameId}/user-engines/${engineRecord.id}/action`;
    } else {
        url = `/api/games/${gameId}/engines/${engineRecord.engine_id}/action`;
    }

    const res = await fetch(url, {
        method: 'POST',
        headers,
        body: JSON.stringify({ action, payload }),
    });
    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || `HTTP ${res.status}`);
    }
    return res.json();
}
