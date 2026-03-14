/**
 * engines/chest_game.js — Chest mini-game engine renderer.
 * Delegates to existing chest_game.js logic where possible, or re-implements.
 */

import { makeWidget, makeActionButton, callAction } from './base.js';

export async function render(container, rec, gameId, postLog) {
    const widget = makeWidget(rec.meta?.name || 'Сундуки');
    container.appendChild(widget);

    // Fetch chest list
    let chests = [];
    try {
        const res = await callAction(gameId, rec, 'list', {});
        chests = res.chests || [];
    } catch { chests = []; }

    if (!chests.length) {
        widget.appendChild(Object.assign(document.createElement('div'), {
            className: 'engine-loading',
            textContent: 'Нет доступных сундуков',
        }));
        return;
    }

    let selectedChest = null;
    let gameState     = null;

    const gameArea = document.createElement('div');
    gameArea.className = 'engine-widget';
    gameArea.style.display = 'none';

    // Chest selection grid
    const chestLabel = document.createElement('div');
    chestLabel.className = 'engine-widget-title';
    chestLabel.style.marginTop = '0';
    chestLabel.textContent = 'Тип сундука';
    widget.appendChild(chestLabel);

    const chestGrid = document.createElement('div');
    chestGrid.className = 'option-grid';
    let activeChestBtn = null;

    chests.forEach(chest => {
        const btn = document.createElement('button');
        btn.className = 'option-btn';
        btn.textContent = chest.name || chest.key;
        btn.addEventListener('click', async () => {
            if (activeChestBtn) activeChestBtn.classList.remove('active');
            btn.classList.add('active');
            activeChestBtn = btn;
            selectedChest = chest.key;
            await startGame();
        });
        chestGrid.appendChild(btn);
    });

    widget.appendChild(chestGrid);
    widget.appendChild(gameArea);

    async function startGame() {
        gameArea.style.display = '';
        gameArea.innerHTML = '<div class="engine-loading">Запуск...</div>';

        try {
            const res = await callAction(gameId, rec, 'start', { chest: selectedChest });
            gameState = res;

            // Log combination immediately for admin
            if (res.combination) {
                await postLog({
                    icon: '🔒',
                    name: `Комбинация: ${res.combination.join(' ')}`,
                    timestamp: new Date().toISOString(),
                    action: 'chest_combination',
                }, 'admin');
            }

            renderGame(res);
        } catch (e) {
            gameArea.innerHTML = `<div class="engine-loading">Ошибка: ${e.message}</div>`;
        }
    }

    function renderGame(state) {
        gameArea.innerHTML = '';

        const info = document.createElement('div');
        info.className = 'engine-widget-title';
        info.textContent = `Угадай последовательность (${state.length || 3} шага)`;
        gameArea.appendChild(info);

        const guessedSoFar = state.guessed || [];
        const seqLen = state.length || 3;
        const allIcons = { up: '⬆', down: '⬇', left: '⬅', right: '➡' };
        const available = state.directions || ['up', 'down', 'left', 'right'];

        // Sequence progress boxes
        const seqProgress = document.createElement('div');
        seqProgress.className = 'seq-progress';
        for (let i = 0; i < seqLen; i++) {
            const box = document.createElement('div');
            box.className = 'seq-box' + (i < guessedSoFar.length ? ' filled' : '');
            if (i < guessedSoFar.length) {
                box.textContent = guessedSoFar[i];
            }
            seqProgress.appendChild(box);
        }
        gameArea.appendChild(seqProgress);

        // Attempts (wrong guesses only)
        const attemptsEl = document.createElement('div');
        attemptsEl.className = 'engine-widget-title';
        attemptsEl.style.fontSize = '0.9rem';
        attemptsEl.style.opacity = '0.7';
        attemptsEl.textContent = `Промахи: ${state.attempts || 0}`;
        gameArea.appendChild(attemptsEl);

        const dirGrid = document.createElement('div');
        dirGrid.className = 'option-grid';

        available.forEach((dir) => {
            const btn = document.createElement('button');
            btn.className = 'option-btn';
            btn.textContent = allIcons[dir] || dir;
            btn.style.fontSize = '1.4rem';
            btn.style.minWidth = '60px';
            btn.addEventListener('click', async () => {
                dirGrid.querySelectorAll('.option-btn').forEach(b => b.disabled = true);
                try {
                    const res = await callAction(gameId, rec, 'guess', {
                        game_id: state.game_id,
                        direction: dir,
                    });

                    if (res.done) {
                        await renderResult({ loot: res.result, attempts: res.attempts || 0 }, true);
                    } else if (!res.correct) {
                        // Wrong guess — shake buttons
                        dirGrid.querySelectorAll('.option-btn').forEach(b => {
                            b.classList.add('wrong');
                            b.disabled = false;
                        });
                        setTimeout(() => {
                            dirGrid.querySelectorAll('.option-btn').forEach(b => b.classList.remove('wrong'));
                        }, 400);
                        attemptsEl.textContent = `Промахи: ${res.attempts || 0}`;
                    } else {
                        renderGame({ ...state, guessed: res.guessed || [], game_id: state.game_id, directions: state.directions, attempts: res.attempts || 0 });
                    }
                } catch (e) {
                    gameArea.innerHTML = `<div class="engine-loading">Ошибка: ${e.message}</div>`;
                }
            });
            dirGrid.appendChild(btn);
        });

        gameArea.appendChild(dirGrid);
    }

    async function renderResult(res, won) {
        gameArea.innerHTML = '';

        const resultLine = document.createElement('div');
        resultLine.className = 'engine-widget-title';
        resultLine.textContent = won
            ? `🎉 Открыт! (попыток: ${res.attempts || 0})`
            : '💀 Неверно';
        gameArea.appendChild(resultLine);

        if (won && res.loot) {
            const lootArea = document.createElement('div');
            lootArea.style.textAlign = 'center';
            lootArea.style.marginTop = '0.5rem';

            if (res.loot.gold) {
                const g = document.createElement('div');
                g.className = 'result-name';
                g.textContent = `🪙 ${res.loot.gold}`;
                lootArea.appendChild(g);
            }
            if (res.loot.items?.length) {
                res.loot.items.forEach(item => {
                    const d = document.createElement('div');
                    d.className = 'result-sub';
                    d.textContent = `• ${item}`;
                    lootArea.appendChild(d);
                });
            }
            gameArea.appendChild(lootArea);

            await postLog({
                icon: '🗝',
                name: `Сундук открыт`,
                gold: res.loot.gold,
                items: res.loot.items,
                timestamp: new Date().toISOString(),
                action: 'chest_game',
            });
        }

        // Restart button
        const { wrap: restartWrap } = makeActionButton('Новый сундук', () => {
            gameArea.style.display = 'none';
            if (activeChestBtn) {
                activeChestBtn.classList.remove('active');
                activeChestBtn = null;
            }
            selectedChest = null;
        });
        gameArea.appendChild(restartWrap);
    }
}
