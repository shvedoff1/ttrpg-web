/**
 * Система уведомлений о новом changelog
 * Проверяет хеш changelog и показывает уведомление если изменился
 */

const CHANGELOG_COOKIE = 'changelogHash';
const COOKIE_EXPIRY_DAYS = 365;

function setCookie(name, value, days = COOKIE_EXPIRY_DAYS) {
    const date = new Date();
    date.setTime(date.getTime() + (days * 24 * 60 * 60 * 1000));
    const expires = `expires=${date.toUTCString()}`;
    document.cookie = `${name}=${value};${expires};path=/`;
}

function getCookie(name) {
    const nameEQ = name + "=";
    const cookies = document.cookie.split(';');
    for (let c of cookies) {
        c = c.trim();
        if (c.indexOf(nameEQ) === 0) {
            return c.substring(nameEQ.length);
        }
    }
    return null;
}

async function checkChangelogUpdate() {
    try {
        // Добавляем timestamp для избежания кеша браузера
        const response = await fetch('/api/changelog/hash?t=' + Date.now());
        const data = await response.json();
        const currentHash = data.hash;
        const savedHash = getCookie(CHANGELOG_COOKIE);

        console.log('Current hash:', currentHash, 'Saved hash:', savedHash);

        // Если хеш отличается или cookie не установлена, показываем уведомление
        if (currentHash && (!savedHash || savedHash !== currentHash)) {
            showChangelogNotification();
            // Сохраняем новый хеш
            setCookie(CHANGELOG_COOKIE, currentHash);
        }
    } catch (error) {
        console.error('Failed to check changelog:', error);
    }
}

function showChangelogNotification() {
    // Проверяем, есть ли уже уведомление
    if (document.getElementById('changelogNotification')) {
        return;
    }

    // Создаем backdrop
    const backdrop = document.createElement('div');
    backdrop.id = 'changelogBackdrop';
    backdrop.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(0, 0, 0, 0.5);
        z-index: 9999;
        display: flex;
        align-items: center;
        justify-content: center;
    `;

    const notification = document.createElement('div');
    notification.id = 'changelogNotification';
    notification.innerHTML = `
        <div class="changelog-modal" style="
            background: white;
            border-radius: 12px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.3);
            padding: 40px;
            max-width: 500px;
            width: 90%;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            text-align: center;
        ">
            <div style="font-size: 48px; margin-bottom: 20px;">📋</div>
            <h2 style="
                font-size: 28px;
                font-weight: 700;
                margin: 0 0 12px 0;
                color: #333;
            ">Есть обновления!</h2>
            <p style="
                font-size: 16px;
                color: #666;
                margin: 0 0 30px 0;
                line-height: 1.5;
            ">Разработчик обновил changelog с новыми изменениями. Рекомендуем ознакомиться!</p>
            <div style="display: flex; gap: 12px; justify-content: center;">
                <button onclick="closeChangelogNotification(); window.open('/changelog', '_blank')" style="
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    border: none;
                    padding: 12px 32px;
                    border-radius: 6px;
                    font-weight: 600;
                    cursor: pointer;
                    font-size: 14px;
                ">Посмотреть changelog</button>
                <button onclick="closeChangelogNotification()" style="
                    background: #f0f0f0;
                    color: #333;
                    border: none;
                    padding: 12px 32px;
                    border-radius: 6px;
                    font-weight: 600;
                    cursor: pointer;
                    font-size: 14px;
                ">Позже</button>
            </div>
        </div>
    `;
    backdrop.appendChild(notification);
    document.body.appendChild(backdrop);

    // Автоматически закрыть через 15 секунд
    setTimeout(() => {
        closeChangelogNotification();
    }, 15000);
}

function closeChangelogNotification() {
    const backdrop = document.getElementById('changelogBackdrop');
    if (backdrop) {
        backdrop.style.opacity = '0';
        backdrop.style.transition = 'opacity 0.3s ease-out';
        setTimeout(() => backdrop.remove(), 300);
    }
}

// Проверяем при загрузке страницы
document.addEventListener('DOMContentLoaded', checkChangelogUpdate);
