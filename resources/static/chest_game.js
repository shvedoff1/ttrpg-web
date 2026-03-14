// ── Chest Game Module ──────────────────────────────────────
// Mini-game for opening chests: guess direction sequence

const ChestGame = (() => {
    let gameId = null;
    let gameLength = 0;
    let guessed = [];  // [up, down, left, right] with icons
    let attempts = 0;
    let availableDirections = [];  // directions available for this chest type

    const DIR_ICONS = { up: '↑', down: '↓', left: '←', right: '→' };

    console.log('✓ ChestGame module initialized');

    async function _apiCall(action, payload) {
        const gameId = window.currentGameId;
        const user   = window.currentUser;
        if (user && gameId) {
            const token = localStorage.getItem('access_token');
            const r = await fetch(`/api/games/${gameId}/engines/chest_game/action`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
                },
                body: JSON.stringify({ action, payload }),
            });
            if (!r.ok) throw new Error('Failed');
            return r.json();
        }
        // fallback: direct API
        const endpoint = action === 'start' ? '/api/play/chest-start' : '/api/play/chest-guess';
        const r = await fetch(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        if (!r.ok) throw new Error('Failed');
        return r.json();
    }

    async function start(chestKey) {
        console.log('ChestGame.start called with:', chestKey);
        try {
            const data = await _apiCall('start', { chest: chestKey });
            console.log('Game started:', data);
            gameId = data.game_id;
            gameLength = data.length;
            availableDirections = data.directions || ['up', 'down', 'left', 'right'];
            guessed = [];
            attempts = 0;
            showAvailableButtons();
            render();
            console.log('Game rendered');
        } catch (e) {
            console.error('ChestGame.start:', e);
            alert('Ошибка при открытии сундука');
        }
    }

    async function guess(direction) {
        if (!gameId) return;
        try {
            const data = await _apiCall('guess', { game_id: gameId, direction });
            guessed = data.guessed || [];
            attempts = data.attempts || 0;

            // Animate button feedback
            const btn = document.querySelector(`.dir-btn[data-dir="${direction}"]`);
            if (btn) {
                btn.classList.add(data.correct ? 'correct' : 'wrong');
                setTimeout(() => {
                    btn.classList.remove('correct', 'wrong');
                }, 300);
            }

            if (data.done) {
                // Game complete: show result
                hide();
                setTimeout(() => {
                    if (data.result) {
                        showResultPopup(data.result);
                        // Log: attempt count included
                        logChestResult(data.result, attempts, window.selectedChestName);
                    }
                }, 300);
            } else {
                render();
            }
        } catch (e) {
            console.error('ChestGame.guess:', e);
        }
    }

    function render() {
        const progressEl = document.getElementById('chestGameProgress');
        if (!progressEl) return;

        // Clear progress
        progressEl.innerHTML = '';

        // Render slots
        for (let i = 0; i < gameLength; i++) {
            const slot = document.createElement('div');
            slot.className = 'progress-slot';
            if (i < guessed.length) {
                slot.textContent = guessed[i];
                slot.classList.add('guessed');
            } else {
                slot.textContent = '?';
            }
            progressEl.appendChild(slot);
        }

        // Update attempts counter
        const attemptsEl = document.getElementById('chestGameAttempts');
        if (attemptsEl) {
            attemptsEl.textContent = `Неверные попытки: ${attempts}`;
        }
    }

    function showAvailableButtons() {
        // Show only buttons for available directions
        const allDirs = ['up', 'down', 'left', 'right'];
        allDirs.forEach(dir => {
            const btn = document.querySelector(`.dir-btn[data-dir="${dir}"]`);
            if (btn) {
                if (availableDirections.includes(dir)) {
                    btn.style.display = '';
                    btn.disabled = false;
                } else {
                    btn.style.display = 'none';
                    btn.disabled = true;
                }
            }
        });
    }

    function show() {
        const area = document.getElementById('chestGameArea');
        if (area) area.style.display = '';
    }

    function hide() {
        const area = document.getElementById('chestGameArea');
        if (area) area.style.display = 'none';
    }

    return { start, guess, show, hide, render };
})();

// Button handlers for direction buttons
function guessDir(direction) {
    ChestGame.guess(direction);
}

// Helper to log chest result
function logChestResult(result, attempts, chestName) {
    if (!currentUser) return;
    const logEntry = {
        profIcon: '📦',
        profName: 'Сундуки',
        locName: chestName || result.name,
        result: { ...result, attempts },
        time: new Date().toLocaleTimeString('ru-RU', { hour12: false }),
    };
    postLog(logEntry);
}
