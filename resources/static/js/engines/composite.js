/**
 * engines/composite.js — Composite (user-created) engine renderer.
 * Routes to the underlying engine renderer based on the first mechanic's type.
 */

import { makeWidget, makeActionButton, callAction } from './base.js';

// Map primitive mechanic types to their renderer modules
const RENDERERS = {
    // Core primitives
    weighted_roll:    () => import('./primitives/generic_roll.js'),
    context_roll:     () => import('./primitives/context_roll.js'),
    weighted_sample:  () => import('./primitives/sample.js'),
    cascade_roll:     () => import('./primitives/generic_roll.js'),
    filtered_roll:    () => import('./primitives/context_roll.js'),
    loot_bundle:      () => import('./primitives/context_roll.js'),
    pool_sample:      () => import('./primitives/generic_roll.js'),
    item_generator:   () => import('./item_generator.js'),
    // System engine renderers (for copy-mode engines)
    profession_roll:  () => import('./profession_roll.js'),
    story_motivation: () => import('./story_motivation.js'),
    trader_inventory: () => import('./trader_inventory.js'),
    treasure:         () => import('./treasure.js'),
};

export async function render(container, rec, gameId, postLog) {
    const mechanics = rec.meta?.mechanics || [];

    if (!mechanics.length) {
        const widget = makeWidget(rec.meta?.name || 'Движок');
        widget.appendChild(Object.assign(document.createElement('div'), {
            className: 'engine-loading',
            textContent: 'Движок не настроен (нет механик)',
        }));
        container.appendChild(widget);
        return;
    }

    if (mechanics.length === 1) {
        // Single mechanic — delegate to its renderer
        const mechType = mechanics[0].type;
        const loader   = RENDERERS[mechType];
        if (loader) {
            const mod = await loader();
            const subRec = { ...rec, _mechanicIndex: 0 };
            await mod.render(container, subRec, gameId, postLog);
            return;
        }
    }

    // Multiple mechanics — render as tabs
    const widget = makeWidget(rec.meta?.name || 'Движок');
    container.appendChild(widget);

    const tabs = document.createElement('div');
    tabs.className = 'engine-tabs';
    tabs.style.borderBottom = '1px solid var(--border)';
    tabs.style.marginBottom = '1rem';
    widget.appendChild(tabs);

    const contentArea = document.createElement('div');
    contentArea.className = 'engine-widget';
    widget.appendChild(contentArea);

    for (let i = 0; i < mechanics.length; i++) {
        const m   = mechanics[i];
        const tab = document.createElement('button');
        tab.className = 'engine-tab' + (i === 0 ? ' active' : '');
        tab.textContent = m.label || m.type;
        tab.addEventListener('click', async () => {
            tabs.querySelectorAll('.engine-tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            contentArea.innerHTML = '';

            // Create a fake rec with only this mechanic for the renderer
            const subRec = {
                ...rec,
                _mechanicIndex: i,
                meta: { ...rec.meta, mechanics: [m] },
            };
            const loader = RENDERERS[m.type];
            if (loader) {
                const mod = await loader();
                await mod.render(contentArea, subRec, gameId, postLog);
            } else {
                contentArea.innerHTML = `<div class="engine-loading">Тип ${m.type} не поддерживается</div>`;
            }
        });
        tabs.appendChild(tab);
    }

    // Render first mechanic immediately
    const firstTab = tabs.querySelector('.engine-tab');
    if (firstTab) firstTab.click();
}
