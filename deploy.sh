#!/bin/bash

# Скрипт развертывания EMEX системы на сервере

echo "🚀 Развертывание EMEX системы..."

# Проверяем Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker не установлен! Установите Docker и попробуйте снова."
    exit 1
fi

# Проверяем docker-compose
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose не установлен! Установите Docker Compose и попробуйте снова."
    exit 1
fi

# Проверяем .env файл
if [ ! -f ".env" ]; then
    echo "❌ Файл .env не найден!"
    echo "💡 Скопируйте env_example.txt в .env и заполните настройки:"
    echo "   cp env_example.txt .env"
    echo "   nano .env"
    exit 1
fi

echo "✅ Проверки пройдены"

# Останавливаем старые контейнеры
echo "🛑 Останавливаем старые контейнеры..."
docker-compose down

# Собираем новый образ
echo "🔨 Собираем новый образ..."
docker-compose build --no-cache

# Запускаем контейнеры
echo "🚀 Запускаем контейнеры..."
docker-compose up -d

# Проверяем статус
echo "📊 Проверяем статус..."
sleep 5
docker-compose ps

echo ""
echo "✅ Развертывание завершено!"
echo ""
echo "📋 Полезные команды:"
echo "   Просмотр логов:     docker-compose logs -f"
echo "   Остановка:          docker-compose down"
echo "   Перезапуск:         docker-compose restart"
echo "   Запуск вручную:     docker-compose exec emex-processor python main.py"
echo ""
echo "🔗 Ваш фид доступен по адресу:"
echo "   https://raw.githubusercontent.com/$(grep GITHUB_REPO .env | cut -d '=' -f2)/main/price_for_emex.csv" 