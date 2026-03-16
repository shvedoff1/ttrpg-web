/**
 * engines/item_generator.js — Item generator engine renderer.
 */

import { makeWidget, makeOptionGrid, makeActionButton, callAction } from './base.js';

export async function render(container, rec, gameId, postLog) {
    const widget = makeWidget(rec.meta?.name || 'Генератор предметов');
    container.appendChild(widget);

    // Fetch available types
    let types = [];
    try {
        const res = await callAction(gameId, rec, 'get_types', {});
        types = res.types || [];
    } catch { types = []; }

    if (!types.length) {
        widget.appendChild(Object.assign(document.createElement('div'), {
            className: 'engine-loading',
            textContent: 'Нет доступных типов',
        }));
        return;
    }

    let selectedType    = null;
    let selectedSubtype = null;

    const subtypeArea = document.createElement('div');
    subtypeArea.className = 'engine-widget';
    subtypeArea.style.display = 'none';

    const resultArea = document.createElement('div');
    resultArea.className = 'item-gen-result';
    resultArea.style.display = 'none';
    widget.appendChild(resultArea);

    const { wrap, btn: genBtn } = makeActionButton('Сгенерировать', async () => {
        if (!selectedType || !selectedSubtype) throw new Error('Выберите тип и подтип');
        const result = await callAction(gameId, rec, 'generate', {
            type: selectedType,
            subtype: selectedSubtype,
            count: 1,
        });

        const item = (result.items || [result])[0];
        if (item) {
            resultArea.style.display = '';
            resultArea.innerHTML = `
                <div class="item-gen-name">${item.name || '—'}</div>
                <div class="item-gen-parts">${(item.parts || []).join(', ')}</div>
                ${item.properties?.length ? `<div class="item-gen-props">${item.properties.join(' • ')}</div>` : ''}
            `;
        }

        await postLog({
            icon: '⚒',
            name: item?.name || '—',
            description: (item?.properties || []).join(', '),
            timestamp: new Date().toISOString(),
            action: 'item_gen',
        });

        return result;
    });

    // Type label
    const typeLabel = document.createElement('div');
    typeLabel.className = 'engine-widget-title';
    typeLabel.style.marginTop = '0';
    typeLabel.textContent = 'Тип';
    widget.appendChild(typeLabel);

    widget.appendChild(makeOptionGrid(types, async (typeKey) => {
        selectedType    = typeKey;
        selectedSubtype = null;
        genBtn.disabled = true;
        subtypeArea.style.display = '';
        subtypeArea.innerHTML     = '';

        const subLabel = document.createElement('div');
        subLabel.className = 'engine-widget-title';
        subLabel.textContent = 'Подтип';
        subtypeArea.appendChild(subLabel);

        let subtypes = [];
        try {
            const r = await callAction(gameId, rec, 'get_types', { type: typeKey });
            subtypes = r.subtypes || [];
        } catch { subtypes = []; }

        subtypeArea.appendChild(makeOptionGrid(subtypes, (subKey) => {
            selectedSubtype = subKey;
            genBtn.disabled = false;
        }));
    }));

    widget.appendChild(subtypeArea);
    widget.appendChild(resultArea);
    widget.appendChild(wrap);
    genBtn.disabled = true;
}
