/**
 * engines/treasure.js — Treasure roll engine renderer.
 */

import { makeWidget, makeActionButton, callAction } from './base.js';

export async function render(container, rec, gameId, postLog) {
    const widget = makeWidget(rec.meta?.name || 'Сокровища');
    container.appendChild(widget);

    const { wrap, btn } = makeActionButton('Бросить', async () => {
        const result = await callAction(gameId, rec, 'roll', {});

        await postLog({
            icon: '💎',
            name: result.name,
            price: result.price,
            category: result.category,
            timestamp: new Date().toISOString(),
            action: 'treasure',
        });

        return result;
    });

    widget.appendChild(wrap);
}
