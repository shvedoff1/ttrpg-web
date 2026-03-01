#!/usr/bin/env bash
set -euo pipefail

# ─────────────────────────────────────────────────────────────────────────────
# КОНФИГУРАЦИЯ  ←  заполни перед первым запуском
# ─────────────────────────────────────────────────────────────────────────────
SERVER_HOST="90.156.216.115"           # IP или hostname сервера
SERVER_USER="centos"                   # SSH-пользователь
SERVER_PATH="/opt/gotika-bot"          # куда распаковываем на сервере
SERVICE_NAME="gotika-bot"             # имя systemd-сервиса
SSH_KEY=""         # путь к SSH-ключу (оставь пустым для дефолта)
# ─────────────────────────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ARCHIVE_NAME="gotika-bot-$(date +%Y%m%d-%H%M%S).tar.gz"
ARCHIVE_PATH="/tmp/${ARCHIVE_NAME}"
REMOTE_TMP="/tmp/${ARCHIVE_NAME}"

# SSH-команда (с ключом или без)
if [[ -n "${SSH_KEY}" && -f "${SSH_KEY}" ]]; then
    SSH="ssh -i ${SSH_KEY} -o StrictHostKeyChecking=accept-new"
    SCP="scp -i ${SSH_KEY}"
else
    SSH="ssh -o StrictHostKeyChecking=accept-new -p 8988"
    SCP="scp -P 8988"
fi
REMOTE="${SERVER_USER}@${SERVER_HOST}"

# ─────────────────────────────────────────────────────────────────────────────

log()  { echo "  $*"; }
ok()   { echo "✓ $*"; }
fail() { echo "✗ $*" >&2; exit 1; }
step() { echo; echo "── $* ──"; }

echo "═══════════════════════════════════"
echo "  Gotika Bot  —  Deploy"
echo "  → ${REMOTE}:${SERVER_PATH}"
echo "═══════════════════════════════════"

# Проверка конфига
[[ "${SERVER_HOST}" == "your.server.ip" ]] && fail "Заполни SERVER_HOST в deploy.sh"

# ─── 1. Генерация res.json ───────────────────────────────────────────────────
# step "Генерация res.json"
# cd "${SCRIPT_DIR}/resources"
# if python generator.py 2>&1 | tail -3; then
#     ok "res.json обновлён"
# else
#     fail "generator.py завершился с ошибкой"
# fi
# cd "${SCRIPT_DIR}"

# ─── 2. Сборка архива ────────────────────────────────────────────────────────
step "Сборка архива"
log "Исключаем: venv/, newRes/, __pycache__, .git, *.pyc, *.zip"

tar -czf "${ARCHIVE_PATH}" \
    --exclude="./.git" \
    --exclude="./.claude" \
    --exclude="./.idea" \
    --exclude="./.DS_Store" \
    --exclude="./venv" \
    --exclude="./newRes" \
    --exclude="./res_back.json" \
    --exclude="./resources.zip" \
    --exclude="./тест_лог" \
    --exclude="./__pycache__" \
    --exclude="./resources/__pycache__" \
    --exclude="*.pyc" \
    --exclude='._*' \
    -C "${SCRIPT_DIR}" .

ARCHIVE_SIZE=$(du -sh "${ARCHIVE_PATH}" | cut -f1)
ok "Архив: ${ARCHIVE_PATH} (${ARCHIVE_SIZE})"

# ─── 3. Загрузка на сервер ───────────────────────────────────────────────────
step "Загрузка на сервер"
${SCP} "${ARCHIVE_PATH}" "${REMOTE}:${REMOTE_TMP}"
ok "Файл загружен → ${REMOTE}:${REMOTE_TMP}"

# ─── 4. Раскатка и перезапуск ────────────────────────────────────────────────
step "Раскатка и перезапуск"
${SSH} "${REMOTE}" bash <<EOF
set -euo pipefail

DEPLOY_DIR="${SERVER_PATH}"
ARCHIVE="${REMOTE_TMP}"
SERVICE="${SERVICE_NAME}"

echo "  → Создаём директорию \${DEPLOY_DIR}"
mkdir -p "\${DEPLOY_DIR}"

echo "  → Распаковываем архив"
tar -xzf "\${ARCHIVE}" -C "\${DEPLOY_DIR}"

echo "  → Удаляем архив с сервера"
rm -f "\${ARCHIVE}"

echo "  → Обновляем зависимости"
cd "\${DEPLOY_DIR}"
if [ ! -d "venv" ]; then
    echo "  → Создаём venv (первый запуск)"
    apt-get install -y -q python3-pip python3-venv 2>/dev/null || true
    python3 -m venv venv
fi
venv/bin/python -m pip install -q --upgrade pip
venv/bin/python -m pip install -q -r requirements.txt

echo "  → Перезапускаем сервис \${SERVICE}"
if systemctl is-active --quiet "\${SERVICE}" 2>/dev/null; then
    sudo systemctl restart "\${SERVICE}"
    echo "  → Сервис перезапущен"
else
    echo "  ⚠ Сервис '\${SERVICE}' не найден или не активен"
    echo "    Запусти server_setup.sh для первоначальной настройки"
fi
EOF

# ─── 5. Очистка ──────────────────────────────────────────────────────────────
rm -f "${ARCHIVE_PATH}"

echo
echo "═══════════════════════════════════"
ok "Деплой завершён успешно"
echo "═══════════════════════════════════"
