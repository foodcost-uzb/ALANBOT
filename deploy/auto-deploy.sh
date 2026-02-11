#!/bin/bash
# Auto-deploy script for ALANBOT
# Автоматически деплоит изменения на сервер Contabo VPS

set -e

SERVER="myuser@161.97.68.205"
SERVER_PASS="rudena20051976"
LOCAL_DIR="/Users/novyjpolzovatel/ALANBOT"
REMOTE_DIR="~/alanbot"

# SSH/SCP команды с паролем
SSH_CMD="sshpass -p '$SERVER_PASS' ssh -o StrictHostKeyChecking=no"
SCP_CMD="sshpass -p '$SERVER_PASS' scp -o StrictHostKeyChecking=no"
RSYNC_CMD="sshpass -p '$SERVER_PASS' rsync -avz -e 'ssh -o StrictHostKeyChecking=no'"

echo "=== ALANBOT Auto-Deploy ==="
echo "Server: $SERVER"
echo ""

# Проверка sshpass
if ! command -v sshpass &> /dev/null; then
    echo "❌ sshpass не установлен. Установите: brew install hudochenkov/sshpass/sshpass"
    exit 1
fi

# Проверка подключения
echo "🔗 Проверка подключения..."
if ! eval "$SSH_CMD $SERVER 'echo OK'" > /dev/null 2>&1; then
    echo "❌ Не удалось подключиться к серверу"
    exit 1
fi
echo "✅ Подключение успешно"
echo ""

# Скачать БД с сервера
if [ "$1" == "--sync-db" ] || [ "$1" == "-s" ]; then
    echo "📥 Скачивание базы данных с сервера..."
    mkdir -p "$LOCAL_DIR/data"
    eval "$SCP_CMD $SERVER:$REMOTE_DIR/data/bot.db '$LOCAL_DIR/data/bot.db'"
    echo "✅ База данных скачана в data/bot.db"
    exit 0
fi

# Просмотр логов
if [ "$1" == "--logs" ] || [ "$1" == "-l" ]; then
    echo "📊 Логи ALANBOT:"
    eval "$SSH_CMD $SERVER 'echo $SERVER_PASS | sudo -S journalctl -u alanbot -n 50 --no-pager 2>/dev/null'"
    exit 0
fi

# Живые логи
if [ "$1" == "--follow" ] || [ "$1" == "-f" ]; then
    echo "📊 Живые логи ALANBOT (Ctrl+C для выхода):"
    eval "$SSH_CMD $SERVER 'echo $SERVER_PASS | sudo -S journalctl -u alanbot -f 2>/dev/null'"
    exit 0
fi

# Статус
if [ "$1" == "--status" ]; then
    eval "$SSH_CMD $SERVER 'echo $SERVER_PASS | sudo -S systemctl status alanbot --no-pager 2>/dev/null'"
    exit 0
fi

# Деплой кода
echo "📦 Загрузка файлов..."

# Python модули бота
eval "$RSYNC_CMD \
  --exclude='.git' --exclude='__pycache__' --exclude='.claude' \
  --exclude='venv' --exclude='data/bot.db' --exclude='.env' \
  '$LOCAL_DIR/' $SERVER:$REMOTE_DIR/"

echo "✅ Файлы загружены"
echo ""

# Обновить зависимости (если указан флаг)
if [ "$1" == "--deps" ] || [ "$1" == "-d" ] || [ "$1" == "--all" ] || [ "$1" == "-a" ]; then
    echo "📦 Обновление зависимостей..."
    eval "$SSH_CMD $SERVER '$REMOTE_DIR/venv/bin/pip install --quiet -r $REMOTE_DIR/requirements.txt'"
    echo "✅ Зависимости обновлены"
    echo ""
fi

# Обновить .env (только с явным флагом)
if [ "$1" == "--env" ] || [ "$1" == "--all" ] || [ "$1" == "-a" ]; then
    echo "⚙️  Обновление .env..."
    eval "$SCP_CMD '$LOCAL_DIR/.env' $SERVER:$REMOTE_DIR/.env"
    echo "✅ .env обновлён"
    echo ""
fi

# Перезапуск сервисов
echo "🔄 Перезапуск ALANBOT..."
eval "$SSH_CMD $SERVER 'echo $SERVER_PASS | sudo -S systemctl restart alanbot 2>/dev/null'"
eval "$SSH_CMD $SERVER 'echo $SERVER_PASS | sudo -S systemctl restart alanbot-web 2>/dev/null'"
sleep 2

# Проверка статуса
echo "📊 Статус:"
eval "$SSH_CMD $SERVER 'echo $SERVER_PASS | sudo -S systemctl is-active alanbot 2>/dev/null'" || true
echo -n "Web: "
eval "$SSH_CMD $SERVER 'echo $SERVER_PASS | sudo -S systemctl is-active alanbot-web 2>/dev/null'" || true
echo ""

echo "🎉 Деплой завершён!"
echo ""
echo "Использование:"
echo "  ./deploy/auto-deploy.sh            # Деплой кода + рестарт"
echo "  ./deploy/auto-deploy.sh -d         # + обновить зависимости"
echo "  ./deploy/auto-deploy.sh -a         # + зависимости + .env"
echo "  ./deploy/auto-deploy.sh -s         # Скачать БД с сервера"
echo "  ./deploy/auto-deploy.sh -l         # Последние 50 строк логов"
echo "  ./deploy/auto-deploy.sh -f         # Живые логи (follow)"
echo "  ./deploy/auto-deploy.sh --status   # Статус сервиса"
