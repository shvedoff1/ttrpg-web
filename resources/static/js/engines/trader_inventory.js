/**
 * engines/trader_inventory.js — Trader inventory engine renderer.
 */

import { makeWidget, makeOptionGrid, makeActionButton, callAction } from './base.js';

function renderItems(container, items) {
    container.innerHTML = '';
    if (!items.length) {
        container.textContent = 'Пусто';
        return;
    }
    items.forEach(item => {
        const row = document.createElement('div');
        row.className = 'inv-row';
        row.innerHTML = `
            <span class="inv-name${item.unique ? ' unique' : ''}">${item.name}</span>
            <span class="inv-price">${item.price != null ? '🪙 ' + item.price : '—'}</span>
        `;
        if (item.properties?.length) {
            const props = document.createElement('div');
            props.className = 'inv-props';
            props.textContent = item.properties.join(' • ');
            row.appendChild(props);
        }
        container.appendChild(row);
    });
}

export async function render(container, rec, gameId, postLog) {
    const widget = makeWidget(rec.meta?.name || 'Торговцы');
    container.appendChild(widget);

    // Fetch traders list
    let traders = [];
    try {
        const res = await callAction(gameId, rec, 'list_traders', {});
        traders = res.traders || [];
    } catch { traders = []; }

    if (!traders.length) {
        widget.appendChild(Object.assign(document.createElement('div'), {
            className: 'engine-loading',
            textContent: 'Нет доступных торговцев',
        }));
        return;
    }

    const invArea = document.createElement('div');
    invArea.className = 'trader-inventory';
    invArea.style.display = 'none';

    const invTitle = document.createElement('div');
    invTitle.className = 'engine-widget-title';
    invTitle.style.display = 'none';

    // Encode subtype in key so makeOptionGrid callback can split it back
    const traderItems = traders.map(t => ({ key: `${t.subtype}:${t.key}`, name: t.name }));

    let lastSelected = null;

    const optionGrid = makeOptionGrid(traderItems, async (key, name) => {
        lastSelected = key;
        invArea.innerHTML = '<div class="engine-loading">Загрузка...</div>';
        invArea.style.display = '';
        invTitle.style.display = '';
        invTitle.textContent = name;

        try {
            const [subtype, traderKey] = key.split(':');
            const res = await callAction(gameId, rec, 'get_inventory', {
                subtype,
                key: traderKey,
            });
            renderItems(invArea, res.items || []);

            await postLog({
                icon: '🏪',
                name: `Торговец: ${name}`,
                timestamp: new Date().toISOString(),
                action: 'trader_inventory',
            });
        } catch (e) {
            invArea.textContent = `Ошибка: ${e.message}`;
        }
    });

    // Reset cache button
    const { wrap: resetWrap, btn: resetBtn } = makeActionButton('🔄 Обновить ассортимент', async () => {
        resetBtn.disabled = true;
        try {
            await callAction(gameId, rec, 'reset_cache', {});
            if (lastSelected) {
                const [subtype, traderKey] = lastSelected.split(':');
                invArea.innerHTML = '<div class="engine-loading">Загрузка...</div>';
                const res = await callAction(gameId, rec, 'get_inventory', { subtype, key: traderKey });
                renderItems(invArea, res.items || []);
            }
        } catch (e) {
            invArea.textContent = `Ошибка: ${e.message}`;
        }
        resetBtn.disabled = false;
    });
    resetWrap.style.marginTop = '0.7rem';

    widget.appendChild(optionGrid);
    widget.appendChild(invTitle);
    widget.appendChild(invArea);
    widget.appendChild(resetWrap);
}
