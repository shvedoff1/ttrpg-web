/**
 * engines/index.js — Engine renderer dispatcher.
 * Maps engine_id → dynamic import of its renderer.
 */

const ENGINE_RENDERERS = {
    profession_roll:   () => import('./profession_roll.js'),
    chest_game:        () => import('./chest_game.js'),
    item_generator:    () => import('./item_generator.js'),
    trader_inventory:  () => import('./trader_inventory.js'),
    story_motivation:  () => import('./story_motivation.js'),
    treasure:          () => import('./treasure.js'),
    composite:         () => import('./composite.js'),
};

/**
 * Render an engine into container.
 * @param {HTMLElement} container
 * @param {Object} rec - GameEngine record with .meta
 * @param {number} gameId
 * @param {Function} postLog - (data, visibility?) => Promise
 */
export async function renderEngine(container, rec, gameId, postLog) {
    container.innerHTML = '';

    // Category type — render via category.js
    if (rec.meta?.type === 'category' || rec.engine_category_id) {
        try {
            const mod = await import('./category.js');
            await mod.render(container, rec, gameId, postLog);
        } catch (e) {
            console.error('Category render error:', e);
            container.innerHTML = `<div class="engine-loading">Ошибка загрузки категории: ${e.message}</div>`;
        }
        return;
    }

    // Determine which renderer to use
    // Copy-mode user engines have base_engine_id in meta — use system renderer
    const engineId = rec.engine_id || rec.meta?.base_engine_id || 'composite';
    const loader   = ENGINE_RENDERERS[engineId];

    if (!loader) {
        container.innerHTML = `<div class="engine-loading">Рендерер для "${engineId}" не найден</div>`;
        return;
    }

    try {
        const mod = await loader();
        await mod.render(container, rec, gameId, postLog);
    } catch (e) {
        console.error('Engine render error:', e);
        container.innerHTML = `<div class="engine-loading">Ошибка загрузки движка: ${e.message}</div>`;
    }
}

/** Return icon for an engine */
export function engineIcon(engineId) {
    const icons = {
        profession_roll:   '⚔',
        chest_game:        '🗝',
        item_generator:    '⚒',
        trader_inventory:  '🏪',
        story_motivation:  '📜',
        treasure:          '💎',
        composite:         '⚙',
    };
    return icons[engineId] || '◆';
}
