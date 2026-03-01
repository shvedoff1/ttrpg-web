#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Запускать ОДИН РАЗ на сервере для первоначальной настройки.
# Создаёт systemd-сервис для веб-приложения (основной).
#
# Использование:
#   scp server_setup.sh user@host:/tmp/
#   ssh user@host "sudo bash /tmp/server_setup.sh"
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

# ─── Конфигурация ────────────────────────────────────────────────────────────
DEPLOY_DIR="/opt/gotika-bot"
SERVICE_NAME="gotika-bot"        # основной сервис (веб-приложение)
SERVICE_USER="${SUDO_USER:-ubuntu}"   # от какого пользователя запускать
# ─────────────────────────────────────────────────────────────────────────────

echo "═══════════════════════════════════"
echo "  Gotika Bot  —  Server Setup"
echo "═══════════════════════════════════"

[[ $EUID -ne 0 ]] && echo "✗ Запускай через sudo" && exit 1

# Python3
echo "── Проверка Python3 ──"
python3 --version || (apt-get update -q && apt-get install -y python3 python3-venv python3-pip)
echo "✓ Python3 OK"

# Директория деплоя
echo "── Директория ──"
mkdir -p "${DEPLOY_DIR}"
chown "${SERVICE_USER}:${SERVICE_USER}" "${DEPLOY_DIR}"
echo "✓ ${DEPLOY_DIR}"

# newRes директория
mkdir -p "${DEPLOY_DIR}/newRes"
chown "${SERVICE_USER}:${SERVICE_USER}" "${DEPLOY_DIR}/newRes"

# ─── Основной сервис: веб-приложение ─────────────────────────────────────────
echo "── Systemd сервис: ${SERVICE_NAME} (веб-приложение) ──"
cat > "/etc/systemd/system/${SERVICE_NAME}.service" <<SERVICE
[Unit]
Description=Gotika Web App
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=${SERVICE_USER}
WorkingDirectory=${DEPLOY_DIR}/resources
ExecStart=${DEPLOY_DIR}/venv/bin/uvicorn web_app:app --host 0.0.0.0 --port 8080
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
SERVICE

systemctl daemon-reload
systemctl enable "${SERVICE_NAME}"
echo "✓ Сервис ${SERVICE_NAME} (веб-приложение) создан и включён в автозапуск"
echo "  Веб-интерфейс будет доступен на http://<server>:8080"

# ─── Второй сервис: Telegram-бот (пока выключен) ─────────────────────────────
echo "── Telegram-бот: создаём сервис gotika-telegram (не включаем) ──"
cat > "/etc/systemd/system/gotika-telegram.service" <<SERVICE
[Unit]
Description=Gotika Telegram Bot
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=${SERVICE_USER}
WorkingDirectory=${DEPLOY_DIR}
ExecStart=${DEPLOY_DIR}/venv/bin/python resources.py
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
SERVICE

systemctl daemon-reload
echo "✓ Сервис gotika-telegram создан (не включён)"
echo "  Чтобы включить бота: systemctl enable gotika-telegram && systemctl start gotika-telegram"

echo
echo "═══════════════════════════════════"
echo "✓ Setup завершён"
echo "  Теперь запусти ./deploy.sh с локальной машины"
echo "═══════════════════════════════════"
