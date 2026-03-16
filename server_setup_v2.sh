#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Запускать ОДИН РАЗ на сервере для настройки v2-окружения.
# Создаёт systemd-сервис для v2 и обновляет nginx для роутинга по хидеру.
#
# Роутинг: заголовок X-Use-V2: 1  →  порт 8081 (v2)
#          без заголовка           →  порт 8080 (prod)
#
# Использование:
#   scp -P 8988 server_setup_v2.sh centos@90.156.216.115:/tmp/
#   ssh -p 8988 centos@90.156.216.115 "sudo bash /tmp/server_setup_v2.sh"
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

DEPLOY_DIR="/opt/gotika-bot-v2"
SERVICE_NAME="gotika-bot-v2"
SERVICE_USER="${SUDO_USER:-centos}"
PORT=8081
NGINX_CONF="/etc/nginx/conf.d/tbrpg.conf"

echo "═══════════════════════════════════"
echo "  Gotika Bot v2  —  Server Setup"
echo "  Port: ${PORT}  |  Header: X-Use-V2: 1"
echo "═══════════════════════════════════"

[[ $EUID -ne 0 ]] && echo "✗ Запускай через sudo" && exit 1

# ─── Python3 ─────────────────────────────────────────────────────────────────
echo "── Проверка Python3 ──"
python3 --version || (yum install -y python3 python3-venv || apt-get install -y python3 python3-venv)
echo "✓ Python3 OK"

# ─── Директория деплоя ───────────────────────────────────────────────────────
echo "── Директория ${DEPLOY_DIR} ──"
mkdir -p "${DEPLOY_DIR}"
chown "${SERVICE_USER}:${SERVICE_USER}" "${DEPLOY_DIR}"
echo "✓ ${DEPLOY_DIR}"

# ─── Systemd сервис ──────────────────────────────────────────────────────────
echo "── Systemd сервис: ${SERVICE_NAME} ──"
cat > "/etc/systemd/system/${SERVICE_NAME}.service" <<SERVICE
[Unit]
Description=Gotika Web App v2
After=network.target

[Service]
Type=simple
User=${SERVICE_USER}
WorkingDirectory=${DEPLOY_DIR}/resources
ExecStart=${DEPLOY_DIR}/venv/bin/uvicorn web_app:app --host 127.0.0.1 --port ${PORT}
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
echo "✓ Сервис ${SERVICE_NAME} создан"

# ─── Nginx: роутинг по хидеру ────────────────────────────────────────────────
echo "── Обновляем nginx конфиг: ${NGINX_CONF} ──"

# Бэкап оригинала
cp "${NGINX_CONF}" "${NGINX_CONF}.bak"
echo "✓ Бэкап: ${NGINX_CONF}.bak"

cat > "${NGINX_CONF}" <<'NGINX'
map $http_x_use_v2 $backend_port {
    "1"     "127.0.0.1:8081";
    default "127.0.0.1:8080";
}

server {
    listen 80;
    server_name tbrpg.online;
    return 301 https://$host$request_uri;
}

server {
    listen 8443 ssl;
    server_name tbrpg.online;

    ssl_certificate     /etc/ssl/certs/bundle.crt;
    ssl_certificate_key /etc/ssl/certs/priv.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    access_log /var/log/nginx/tbrpg.log;
    error_log  /var/log/nginx/tbrpg.log;

    location / {
        proxy_pass         http://$backend_port;
        proxy_http_version 1.1;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
    }
}
NGINX

nginx -t && systemctl reload nginx
echo "✓ Nginx обновлён и перезагружен"

echo
echo "═══════════════════════════════════"
echo "✓ Setup завершён"
echo "  Роутинг: заголовок X-Use-V2: 1 → порт 8081"
echo "  Теперь запусти ./deploy_v2.sh с локальной машины"
echo "═══════════════════════════════════"
