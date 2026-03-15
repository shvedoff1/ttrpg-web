/**
 * primitives/generic_roll.js — Simple single-button roll renderer.
 * Used for: weighted_roll, cascade_roll, pool_sample
 */

import { makeWidget, makeActionButton, callAction } from '../base.js';

const ROLL_ICONS = {
    weighted_roll: '🎲',
    cascade_roll:  '💎',
    pool_sample:   '🏪',
};

export async function render(container, rec, gameId, postLog) {
    const meta = rec.meta || {};
    const effCfg = rec.effective_config || {};
    const primitiveId = rec.engine_id || '';
    const isCategory = !!rec._categoryRoute;
    let target;
    if (isCategory) {
        target = container;
    } else {
        target = makeWidget(meta.name || 'Бросок');
        container.appendChild(target);
    }

    const showPrice = effCfg.show_price ?? false;

    const { wrap } = makeActionButton(
        effCfg.roll_label || meta.effective_config?.roll_label || 'Бросить',
        async () => {
            const action = (meta.mechanics?.[0]?.action) || 'roll';
            const result = await callAction(gameId, rec, action);
            if (postLog) {
                const logData = {
                    icon: ROLL_ICONS[primitiveId] || '🎲',
                    name: result.name || '—',
                    timestamp: new Date().toISOString(),
                    action: primitiveId || 'roll',
                    ...(result.category ? { category: result.category } : {}),
                };
                if (showPrice && result.price != null) logData.price = result.price;
                if (result.weight != null) logData.weight = result.weight;
                postLog(logData);
            }
            const display = showPrice ? result : { ...result, price: undefined };
            return display;
        },
    );
    target.appendChild(wrap);
}
