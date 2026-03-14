#!/usr/bin/env bash
set -euo pipefail

# ─────────────────────────────────────────────────────────────────────────────
# Деплой ветки v2 на v2.tbrpg.online
# ─────────────────────────────────────────────────────────────────────────────
SERVER_HOST="90.156.216.115"
SERVER_USER="centos"
SERVER_PATH="/opt/gotika-bot-v2"
SERVICE_NAME="gotika-bot-v2"
SSH_KEY=""
# ─────────────────────────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ARCHIVE_NAME="gotika-bot-v2-$(date +%Y%m%d-%H%M%S).tar.gz"
ARCHIVE_PATH="/tmp/${ARCHIVE_NAME}"
REMOTE_TMP="/tmp/${ARCHIVE_NAME}"

if [[ -n "${SSH_KEY}" && -f "${SSH_KEY}" ]]; then
    SSH="ssh -i ${SSH_KEY} -o StrictHostKeyChecking=accept-new"
    SCP="scp -i ${SSH_KEY}"
else
    SSH="ssh -o StrictHostKeyChecking=accept-new -p 8988"
    SCP="scp -P 8988"
fi
REMOTE="${SERVER_USER}@${SERVER_HOST}"

log()  { echo "  $*"; }
ok()   { echo "✓ $*"; }
fail() { echo "✗ $*" >&2; exit 1; }
step() { echo; echo "── $* ──"; }

echo "═══════════════════════════════════"
echo "  Gotika Bot v2  —  Deploy"
echo "  → ${REMOTE}:${SERVER_PATH}"
echo "═══════════════════════════════════"

# ─── 1. Сборка архива ────────────────────────────────────────────────────────
step "Сборка архива"
log "Исключаем: venv/, __pycache__, .git, *.pyc"

tar -czf "${ARCHIVE_PATH}" \
    --exclude="./.git" \
    --exclude="./.claude" \
    --exclude="./.idea" \
    --exclude="./.DS_Store" \
    --exclude="./venv" \
    --exclude="./newRes" \
    --exclude="./res_back.json" \
    --exclude="./resources.zip" \
    --exclude="./__pycache__" \
    --exclude="./resources/__pycache__" \
    --exclude="*.pyc" \
    --exclude='._*' \
    --exclude="./resources/ttrpg.db" \
    -C "${SCRIPT_DIR}" .

ARCHIVE_SIZE=$(du -sh "${ARCHIVE_PATH}" | cut -f1)
ok "Архив: ${ARCHIVE_PATH} (${ARCHIVE_SIZE})"

# ─── 2. Загрузка на сервер ───────────────────────────────────────────────────
step "Загрузка на сервер"
${SCP} "${ARCHIVE_PATH}" "${REMOTE}:${REMOTE_TMP}"
ok "Файл загружен → ${REMOTE}:${REMOTE_TMP}"

# ─── 3. Раскатка и перезапуск ────────────────────────────────────────────────
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

echo "  → Удаляем macOS-метаданные (._*)"
find "\${DEPLOY_DIR}" -name '._*' -delete

echo "  → Удаляем архив с сервера"
rm -f "\${ARCHIVE}"

echo "  → Обновляем зависимости"
cd "\${DEPLOY_DIR}"
if [ ! -d "venv" ]; then
    echo "  → Создаём venv (первый запуск)"
    python3 -m venv venv
fi
venv/bin/python -m pip install -q --upgrade pip
venv/bin/python -m pip install -q -r requirements.txt

echo "  → Применяем миграции БД"
cd "\${DEPLOY_DIR}"
venv/bin/python -m alembic upgrade head

echo "  → Перезапускаем сервис \${SERVICE}"
if systemctl is-active --quiet "\${SERVICE}" 2>/dev/null; then
    sudo systemctl restart "\${SERVICE}"
    echo "  → Сервис перезапущен"
elif systemctl is-enabled --quiet "\${SERVICE}" 2>/dev/null; then
    sudo systemctl start "\${SERVICE}"
    echo "  → Сервис запущен"
else
    echo "  ⚠ Сервис '\${SERVICE}' не найден"
    echo "    Запусти server_setup_v2.sh для первоначальной настройки"
fi
EOF

# ─── 4. Очистка ──────────────────────────────────────────────────────────────
rm -f "${ARCHIVE_PATH}"

echo
echo "═══════════════════════════════════"
ok "Деплой v2 завершён → https://v2.tbrpg.online"
echo "═══════════════════════════════════"
