/**
 * primitives/sample.js — Weighted sample (N items without replacement).
 * Used for: weighted_sample
 */

import { makeWidget, makeActionButton, callAction } from '../base.js';

export async function render(container, rec, gameId, postLog) {
    const meta = rec.meta || {};
    const mechanic = meta.mechanics?.[0] || {};
    const effCfg = rec.effective_config || {};
    const isCategory = !!rec._categoryRoute;
    let target;
    if (isCategory) {
        target = container;
    } else {
        target = makeWidget(mechanic.label || meta.name || 'Выборка');
        container.appendChild(target);
    }

    // Count input
    const countWrap = document.createElement('div');
    countWrap.className = 'sample-count-wrap';

    const countLabel = document.createElement('label');
    countLabel.className = 'sample-count-label';
    countLabel.textContent = 'Количество';

    const countInput = document.createElement('input');
    countInput.type = 'number';
    countInput.className = 'sample-count-input';
    countInput.min = 1;
    countInput.max = 20;
    countInput.value = effCfg.default_count || mechanic.config?.default_count || 3;

    countWrap.appendChild(countLabel);
    countWrap.appendChild(countInput);
    target.appendChild(countWrap);

    const { wrap } = makeActionButton(
        'Выбрать',
        async () => {
            const action = mechanic.action || 'sample';
            const result = await callAction(gameId, rec, action, {
                count: parseInt(countInput.value) || 3,
            });
            if (postLog) {
                postLog({
                    icon: '📜',
                    name: 'Выборка',
                    timestamp: new Date().toISOString(),
                    action: 'sample',
                    ...(result.motivations ? { items: result.motivations } : {}),
                });
            }
            return result;
        },
    );
    target.appendChild(wrap);
}
