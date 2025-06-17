# 🐳 Развертывание EMEX системы на сервере

## 📋 Требования

- **Docker** >= 20.10
- **Docker Compose** >= 2.0
- **Сервер** с доступом в интернет
- **Git** для клонирования репозитория

## 🚀 Быстрое развертывание

### Шаг 1: Клонирование репозитория
```bash
git clone https://github.com/beton18/emex-co_project.git
cd emex-co_project
```

### Шаг 2: Настройка окружения
```bash
# Копируем шаблон конфигурации
cp env_example.txt .env

# Редактируем настройки
nano .env
```

**Заполните .env файл:**
```
EMAIL=ваш@email.com
PASSWORD=ваш_пароль_приложения_gmail
GITHUB_TOKEN=ваш_github_token
GITHUB_REPO=username/repository
FEED_URL=https://username.github.io/repository/price_for_emex.csv
```

### Шаг 3: Запуск системы
```bash
# Делаем скрипт исполняемым
chmod +x deploy.sh

# Запускаем развертывание
./deploy.sh
```

## 🔧 Ручное развертывание

### Сборка образа
```bash
docker build -t emex-processor .
```

### Запуск контейнера
```bash
docker run -d \
  --name emex-processor \
  --env-file .env \
  -v $(pwd)/downloads:/app/downloads \
  -v $(pwd)/result:/app/result \
  emex-processor
```

### Или используйте Docker Compose
```bash
docker-compose up -d
```

## 📊 Управление контейнерами

### Основные команды
```bash
# Просмотр логов
docker-compose logs -f

# Остановка
docker-compose down

# Перезапуск
docker-compose restart

# Запуск обработки вручную
docker-compose exec emex-processor python main.py

# Обновление образа
docker-compose build --no-cache
```

### Просмотр состояния
```bash
# Статус контейнеров
docker-compose ps

# Использование ресурсов
docker stats

# Логи в реальном времени
docker-compose logs -f emex-processor
```

## ⏰ Автоматизация (Cron)

### Настройка автоматического запуска
```bash
# Открываем crontab
crontab -e

# Добавляем задачу (каждый день в 6:00)
0 6 * * * cd /path/to/emex-co_project && docker-compose exec emex-processor python main.py
```

**Примеры расписания:**
- `0 6 * * *` - каждый день в 6:00
- `0 */6 * * *` - каждые 6 часов
- `0 9 * * 1,3,5` - понедельник, среда, пятница в 9:00

## 🔍 Мониторинг

### Проверка работы системы
```bash
# Проверка последних логов
docker-compose logs --tail=50 emex-processor

# Проверка файлов результата
ls -la result/

# Проверка фида
curl -I https://raw.githubusercontent.com/ваш-username/ваш-repo/main/price_for_emex.csv
```

### Отладка проблем
```bash
# Вход в контейнер для отладки
docker-compose exec emex-processor bash

# Запуск обработки с подробным выводом
docker-compose exec emex-processor python -u main.py

# Проверка переменных окружения
docker-compose exec emex-processor env | grep -E "EMAIL|GITHUB"
```

## 📁 Структура папок на сервере

```
/opt/emex-system/
├── .env                    # Конфигурация
├── docker-compose.yml     # Конфигурация Docker
├── main.py                # Основной скрипт
├── requirements.txt       # Зависимости Python
├── downloads/             # Временные файлы (монтируется)
├── result/                # Результаты (монтируется)
└── logs/                  # Логи (опционально)
```

## 🔒 Безопасность

### Рекомендации
1. **Никогда не комитьте .env файл** в репозиторий
2. **Ограничьте права доступа** к .env файлу: `chmod 600 .env`
3. **Регулярно обновляйте** Docker образы
4. **Мониторьте логи** на предмет ошибок

### Резервное копирование
```bash
# Создание бэкапа настроек
tar -czf emex-backup-$(date +%Y%m%d).tar.gz .env docker-compose.yml

# Восстановление из бэкапа
tar -xzf emex-backup-20250617.tar.gz
```

## 🚨 Устранение проблем

### Частые проблемы

**1. Ошибка подключения к Gmail**
```bash
# Проверьте настройки в .env
grep -E "EMAIL|PASSWORD" .env

# Убедитесь что пароль приложения правильный
```

**2. Ошибка загрузки в GitHub**
```bash
# Проверьте токен GitHub
grep GITHUB_TOKEN .env

# Проверьте права репозитория
```

**3. Контейнер не запускается**
```bash
# Проверьте логи
docker-compose logs emex-processor

# Проверьте синтаксис docker-compose.yml
docker-compose config
```

## 📈 Масштабирование

### Для больших объемов данных
1. **Увеличьте ресурсы** контейнера в docker-compose.yml
2. **Настройте мониторинг** производительности
3. **Рассмотрите использование** внешней базы данных

### Высокая доступность
1. **Запустите на нескольких серверах** с балансировщиком
2. **Используйте внешнее хранилище** для .env файлов
3. **Настройте алерты** при сбоях

## 📞 Поддержка

При возникновении проблем:
1. Проверьте логи: `docker-compose logs -f`
2. Убедитесь в правильности .env настроек
3. Проверьте доступность Gmail и GitHub API 