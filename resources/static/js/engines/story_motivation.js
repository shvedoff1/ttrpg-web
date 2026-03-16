/**
 * engines/story_motivation.js — Story motivation engine renderer.
 */

import { makeWidget, makeActionButton, showPopup, callAction } from './base.js';

export async function render(container, rec, gameId, postLog) {
    const widget = makeWidget(rec.meta?.name || 'Мотивации');
    container.appendChild(widget);

    const motivationList = document.createElement('div');
    motivationList.className = 'motivation-list';
    motivationList.style.display = 'none';
    widget.appendChild(motivationList);

    const { wrap, popup, btn } = makeActionButton('Получить мотивации', async () => {
        const result = await callAction(gameId, rec, 'get_motivations', { count: 3 });
        const motivations = result.motivations || [];

        motivationList.style.display = '';
        motivationList.innerHTML = '';
        motivations.forEach(m => {
            const div = document.createElement('div');
            div.className = 'motivation-item';
            div.textContent = m;
            motivationList.appendChild(div);
        });

        await postLog({
            icon: '📜',
            motivations,
            timestamp: new Date().toISOString(),
            action: 'story_motivation',
        });
    });

    widget.appendChild(wrap);
}
