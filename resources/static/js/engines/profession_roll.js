/**
 * engines/profession_roll.js — Profession roll engine renderer.
 * Supports: herbs, ores, trophies (location-based) and theft/cache (district-based).
 */

import { makeWidget, makeOptionGrid, makeActionButton, showPopup, callAction } from './base.js';

export async function render(container, rec, gameId, postLog) {
    const widget = makeWidget(rec.meta?.name || 'Профессии');
    container.appendChild(widget);

    // ── Step 1: Choose profession ─────────────────────────────────────────
    const label1 = document.createElement('div');
    label1.className = 'engine-widget-title';
    label1.style.marginTop = '0';
    label1.textContent = 'Профессия';
    widget.appendChild(label1);

    const meta = rec.meta || {};
    const actions = meta.actions || [];

    // Parse available sub-types from engine meta
    let professions = [];
    let stealModes  = [];

    for (const a of actions) {
        if (a.id === 'get_professions') {
            // Will fetch dynamically
        } else if (a.id === 'roll') {
            // Standard location-based roll
        }
    }

    // Fetch profession list
    let profList = [];
    try {
        const res = await callAction(gameId, rec, 'get_professions', {});
        profList = res.professions || [];
    } catch {
        profList = [];
    }

    if (!profList.length) {
        widget.appendChild(Object.assign(document.createElement('div'), {
            className: 'engine-loading',
            textContent: 'Нет доступных профессий',
        }));
        return;
    }

    let selectedProf = null;
    let selectedLoc  = null;
    let selectedParam1 = null;
    let selectedParam2 = null;

    const locArea = document.createElement('div');
    locArea.className = 'engine-widget';
    locArea.style.display = 'none';

    const param2Area = document.createElement('div');
    param2Area.className = 'engine-widget';
    param2Area.style.display = 'none';

    const effCfg    = rec.effective_config || rec.config || {};
    const rollLabel = effCfg.roll_label || 'Бросить';
    const showPrice = effCfg.show_price ?? false;

    const { wrap: btnWrap, popup, btn: rollBtn } = makeActionButton(rollLabel, async () => {
        let result;
        if (selectedProf === 'Воровство' || selectedProf === 'Разбой') {
            if (!selectedParam1 || !selectedParam2) throw new Error('Выберите тип и район');
            const stealAction = selectedParam1 === 'steal' ? 'roll_steal' : 'roll_cache';
            result = await callAction(gameId, rec, stealAction, {
                district: selectedParam2,
            });
        } else {
            if (!selectedLoc) throw new Error('Выберите локацию');
            result = await callAction(gameId, rec, 'roll', {
                profession: selectedProf,
                location: selectedLoc.key,
            });
        }

        const logData = {
            icon: '⚔',
            name: result.name,
            timestamp: new Date().toISOString(),
            action: 'profession_roll',
            profession: selectedProf,
        };
        if (result.gold != null) logData.gold = result.gold;
        if (result.items?.length) logData.items = result.items;
        if (showPrice && result.price != null) logData.price = result.price;
        if (result.weight != null) logData.weight = result.weight;
        await postLog(logData);

        // Strip price from popup if not configured to show
        const display = showPrice ? result : { ...result, price: undefined };
        return display;
    });

    // Profession grid
    const profGrid = makeOptionGrid(profList, async (key, name) => {
        selectedProf  = key;
        selectedLoc   = null;
        selectedParam1 = null;
        selectedParam2 = null;
        locArea.style.display = '';
        locArea.innerHTML     = '';
        param2Area.style.display = 'none';
        rollBtn.disabled = true;

        const isTheft = key === 'Воровство' || key === 'Разбой';
        if (isTheft) {
            let res;
            try {
                res = await callAction(gameId, rec, 'get_locations', { profession: key });
            } catch { res = {}; }

            const renderDistricts = (parentArea, stealMode) => {
                const distLabel = document.createElement('div');
                distLabel.className = 'engine-widget-title';
                distLabel.textContent = 'Район';
                parentArea.appendChild(distLabel);

                const districts = res.locations || [];
                parentArea.appendChild(makeOptionGrid(districts, (dKey) => {
                    selectedParam1 = stealMode;
                    selectedParam2 = dKey;
                    rollBtn.disabled = false;
                }));
            };

            if (res.modes) {
                // Two modes — show mode selector first
                const modesLabel = document.createElement('div');
                modesLabel.className = 'engine-widget-title';
                modesLabel.textContent = 'Тип';
                locArea.appendChild(modesLabel);

                locArea.appendChild(makeOptionGrid(res.modes, async (mKey, mName) => {
                    selectedParam1 = mKey;
                    selectedParam2 = null;
                    param2Area.style.display = '';
                    param2Area.innerHTML = '';
                    rollBtn.disabled = true;

                    let distRes;
                    try {
                        distRes = await callAction(gameId, rec, 'get_locations', { profession: key, param1: mKey });
                    } catch { distRes = { locations: [] }; }

                    const distLabel = document.createElement('div');
                    distLabel.className = 'engine-widget-title';
                    distLabel.textContent = 'Район';
                    param2Area.appendChild(distLabel);

                    param2Area.appendChild(makeOptionGrid(distRes.locations || [], (dKey) => {
                        selectedParam2 = dKey;
                        rollBtn.disabled = false;
                    }));
                    widget.insertBefore(param2Area, btnWrap);
                }));
            } else if (res.locations) {
                // Single mode — skip mode selector, show districts directly
                const singleMode = res._mode || 'steal';
                renderDistricts(locArea, singleMode);
            }

        } else {
            // Location-based roll
            const locLabel = document.createElement('div');
            locLabel.className = 'engine-widget-title';
            locLabel.textContent = 'Локация';
            locArea.appendChild(locLabel);

            let locs = [];
            try {
                const r = await callAction(gameId, rec, 'get_locations', { profession: key });
                locs = r.locations || [];
            } catch { locs = []; }

            locArea.appendChild(makeOptionGrid(locs, (locKey, locName) => {
                selectedLoc = { key: locKey, name: locName };
                rollBtn.disabled = false;
            }));
        }
    });

    widget.appendChild(profGrid);
    widget.appendChild(locArea);
    widget.appendChild(param2Area);
    widget.appendChild(btnWrap);

    rollBtn.disabled = true;
}
