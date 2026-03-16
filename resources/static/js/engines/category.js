/**
 * engines/category.js — Category renderer.
 * Renders a category (group of engines) as tabs, each tab is a separate engine.
 * Engines within a category can be primitives or system engines.
 */

import { makeWidget, callCategoryAction, formatResult, showPopup } from './base.js';
import { engineIcon } from './index.js';

// Renderers for primitives
const PRIMITIVE_RENDERERS = {
    weighted_roll:    () => import('./primitives/generic_roll.js'),
    context_roll:     () => import('./primitives/context_roll.js'),
    weighted_sample:  () => import('./primitives/sample.js'),
    cascade_roll:     () => import('./primitives/generic_roll.js'),
    filtered_roll:    () => import('./primitives/context_roll.js'),
    loot_bundle:      () => import('./primitives/context_roll.js'),
    pool_sample:      () => import('./primitives/generic_roll.js'),
    item_generator:   () => import('./item_generator.js'),
};

// Icons for primitive types
const PRIMITIVE_ICONS = {
    weighted_roll:    '🎲',
    context_roll:     '🎯',
    weighted_sample:  '🃏',
    cascade_roll:     '🎰',
    filtered_roll:    '🗡',
    loot_bundle:      '📦',
    pool_sample:      '🎲',
    item_generator:   '⚒',
};

/** Get icon for a category engine */
function catEngineIcon(eng) {
    if (eng.engine_type === 'system') return engineIcon(eng.type_id);
    return PRIMITIVE_ICONS[eng.type_id] || '◆';
}

// Renderers for system engines
const SYSTEM_RENDERERS = {
    profession_roll:  () => import('./profession_roll.js'),
    chest_game:       () => import('./chest_game.js'),
    item_generator:   () => import('./item_generator.js'),
    trader_inventory: () => import('./trader_inventory.js'),
    story_motivation: () => import('./story_motivation.js'),
    treasure:         () => import('./treasure.js'),
};

/**
 * Create a callAction wrapper that routes through the category endpoint.
 */
function makeCatCallAction(gameId, gameEngineId, catEngineId) {
    return async function(action, payload = {}) {
        return callCategoryAction(gameId, gameEngineId, catEngineId, action, payload);
    };
}

export async function render(container, rec, gameId, postLog) {
    const meta = rec.meta || {};
    const engines = meta.engines || [];
    const categoryName = meta.name || 'Категория';
    const categoryIcon = meta.icon || '';

    if (!engines.length) {
        const widget = makeWidget(`${categoryIcon} ${categoryName}`.trim());
        widget.appendChild(Object.assign(document.createElement('div'), {
            className: 'engine-loading',
            textContent: 'В категории нет движков',
        }));
        container.appendChild(widget);
        return;
    }

    // Single engine — render directly without tabs
    if (engines.length === 1) {
        const eng = engines[0];
        const widget = makeWidget(`${categoryIcon} ${eng.name || categoryName}`.trim());
        container.appendChild(widget);
        await renderCategoryEngine(widget, eng, rec, gameId, postLog);
        return;
    }

    // Multiple engines — render as styled card with tabs
    const card = document.createElement('div');
    card.className = 'category-card';
    container.appendChild(card);

    // Card header with icon and name
    const header = document.createElement('div');
    header.className = 'category-header';
    header.textContent = `${categoryIcon} ${categoryName}`.trim();
    card.appendChild(header);

    // Tab bar
    const tabs = document.createElement('div');
    tabs.className = 'category-tabs';
    card.appendChild(tabs);

    // Content area
    const contentArea = document.createElement('div');
    contentArea.className = 'category-content';
    card.appendChild(contentArea);

    for (let i = 0; i < engines.length; i++) {
        const eng = engines[i];
        const tab = document.createElement('button');
        tab.className = 'category-tab' + (i === 0 ? ' active' : '');
        const icon = catEngineIcon(eng);
        tab.innerHTML = `<span class="category-tab-icon">${icon}</span> <span class="category-tab-name">${eng.name || eng.type_id}</span>`;
        tab.addEventListener('click', async () => {
            tabs.querySelectorAll('.category-tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            contentArea.innerHTML = '';
            await renderCategoryEngine(contentArea, eng, rec, gameId, postLog);
        });
        tabs.appendChild(tab);
    }

    // Render first engine immediately
    const firstTab = tabs.querySelector('.category-tab');
    if (firstTab) firstTab.click();
}

/**
 * Render a single engine from a category into container.
 * Creates a proxy rec with a custom callAction that routes through category API.
 */
async function renderCategoryEngine(container, eng, parentRec, gameId, postLog) {
    const gameEngineId = parentRec.id;
    const catEngineId = eng.id;

    if (eng.engine_type === 'system') {
        const loader = SYSTEM_RENDERERS[eng.type_id];
        if (!loader) {
            container.innerHTML = `<div class="engine-loading">Системный движок "${eng.type_id}" не поддерживается</div>`;
            return;
        }
        // Create a proxy record that looks like a system engine record
        // but routes actions through the category endpoint
        const proxyRec = {
            ...parentRec,
            engine_id: eng.type_id,
            meta: eng.meta || {},
            effective_config: eng.effective_config || eng.config || {},
            _categoryRoute: { gameEngineId, catEngineId },
        };
        const mod = await loader();
        await mod.render(container, proxyRec, gameId, postLog);
    } else {
        // Primitive
        const loader = PRIMITIVE_RENDERERS[eng.type_id];
        if (!loader) {
            container.innerHTML = `<div class="engine-loading">Примитив "${eng.type_id}" не поддерживается</div>`;
            return;
        }
        // Create a proxy record for primitive renderers
        const proxyRec = {
            ...parentRec,
            engine_id: eng.type_id,
            meta: {
                ...(eng.meta || {}),
                effective_config: eng.effective_config || eng.config || {},
            },
            effective_config: eng.effective_config || eng.config || {},
            _categoryRoute: { gameEngineId, catEngineId },
        };
        const mod = await loader();
        await mod.render(container, proxyRec, gameId, postLog);
    }
}
