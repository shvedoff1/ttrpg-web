/**
 * primitives/context_roll.js — Roll with context picker (location, district, etc.)
 * Used for: context_roll, filtered_roll, loot_bundle
 */

import { makeWidget, makeOptionGrid, makeActionButton, callAction } from '../base.js';

// Подпись секции контекстов по типу примитива
const CONTEXT_LABELS = {
    context_roll:  'Локация',
    filtered_roll: 'Район',
    loot_bundle:   'Район',
};

export async function render(container, rec, gameId, postLog) {
    const meta = rec.meta || {};
    const mechanic = meta.mechanics?.[0] || {};
    const primitiveId = rec.engine_id || '';

    // Inside a category — don't create a nested widget, render directly
    const isCategory = !!rec._categoryRoute;
    let target;
    if (isCategory) {
        target = container;
    } else {
        target = makeWidget(mechanic.label || meta.name || 'Бросок');
        container.appendChild(target);
    }

    let selectedContext = null;

    // Try to load contexts
    try {
        const data = await callAction(gameId, rec, 'list_contexts');
        const contexts = data.contexts || data.locations || [];

        if (contexts.length) {
            // Подпись над кнопками выбора
            const label = document.createElement('div');
            label.className = 'engine-widget-title';
            label.style.marginTop = '0';
            label.textContent = CONTEXT_LABELS[primitiveId] || 'Выберите';
            target.appendChild(label);

            const grid = makeOptionGrid(contexts, (key) => {
                selectedContext = key;
                rollBtn.disabled = false;
            });
            target.appendChild(grid);
        } else {
            const emptyDiv = document.createElement('div');
            emptyDiv.className = 'engine-error';
            emptyDiv.textContent = 'Нет доступных вариантов. Проверьте config_source в конфигурации движка.';
            target.appendChild(emptyDiv);
        }
    } catch (e) {
        console.error('list_contexts error:', e);
        const errDiv = document.createElement('div');
        errDiv.className = 'engine-error';
        errDiv.textContent = `Ошибка загрузки: ${e.message}`;
        target.appendChild(errDiv);
    }

    const effCfg = rec.effective_config || rec.config || {};
    const showPrice = effCfg.show_price ?? false;

    const { wrap, btn: rollBtn } = makeActionButton(
        'Бросить',
        async () => {
            const action = mechanic.action || 'roll';
            const payload = selectedContext ? { context: selectedContext } : {};
            const result = await callAction(gameId, rec, action, payload);
            if (postLog) {
                const logData = {
                    icon: _logIcon(primitiveId),
                    name: result.name || '—',
                    timestamp: new Date().toISOString(),
                    action: primitiveId || 'roll',
                    ...(result.gold != null ? { gold: result.gold } : {}),
                    ...(result.items?.length ? { items: result.items } : {}),
                };
                if (showPrice && result.price != null) logData.price = result.price;
                if (result.weight != null) logData.weight = result.weight;
                postLog(logData);
            }
            const display = showPrice ? result : { ...result, price: undefined };
            return display;
        },
    );
    // Кнопка заблокирована пока не выбран контекст
    rollBtn.disabled = true;
    target.appendChild(wrap);
}

function _logIcon(primitiveId) {
    return { context_roll: '🎯', filtered_roll: '🗡', loot_bundle: '📦' }[primitiveId] || '🎲';
}
