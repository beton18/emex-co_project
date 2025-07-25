# EMEX Автоматизированная система обработки прайс-листов v3.0

## Описание

Автоматизированная система для обработки остатков товаров и создания прайс-листов для платформы EMEX. Система получает остатки товаров из email (выгрузки 1С), обновляет их в Google таблице, и создает итоговый фид для загрузки на GitHub Pages.

## Новая архитектура v3.0

### Источники данных:
- **Остатки**: Email архивы из 1С (как раньше)
- **Цены и номенклатура**: Google таблица

### Логика работы:
1. 📧 Получение email с остатками из 1С ("Остатки Подольск от...")
2. 📊 Извлечение данных об остатках (Артикул + Кол-во)
3. 🔄 Обновление столбца "Кол-во" в Google таблице по артикулам
4. 📋 Загрузка всех данных из обновленной Google таблицы
5. 🔍 Фильтрация товаров с нулевыми остатками
6. 📤 Загрузка итогового Excel файла с заголовками на GitHub Pages

### Структура Google таблицы:
| Артикул | Наименование | Бренд | Цена | Кол-во | Кратность |
|---------|-------------|-------|------|---------|-----------|
| 11.5215900-01 | Щетка стеклоочистителя... | AVTOPRIBOR | 393 | 10 | 1 |

## Установка и настройка

### 1. Зависимости
```bash
pip install -r requirements.txt
```

### 2. Переменные окружения (.env)
```bash
# Gmail настройки
EMAIL=your_email@gmail.com
PASSWORD=your_app_password

# GitHub настройки
GITHUB_TOKEN=your_github_token
GITHUB_REPO=username/repository-name

# Google Sheets настройки
SPREADSHEET_ID=your_google_spreadsheet_id
SHEET_NAME=Sheet1
```

### 3. Google Sheets API
- Создайте сервисный аккаунт в Google Cloud Console
- Скачайте `credentials.json` в корень проекта
- Добавьте email сервисного аккаунта в Google таблицу с правами редактора

### 4. Docker развертывание
```bash
docker-compose up --build
```

### 5. Cron настройка
```bash
# Добавить в crontab для ежедневного запуска в 5:50 утра
50 5 * * * cd /path/to/project && docker-compose run --rm emex_processor >> logs/cron.log 2>&1
```

## Структура проекта

```
emex_project/
├── main.py                 # Основной код
├── requirements.txt        # Python зависимости
├── docker-compose.yml      # Docker конфигурация
├── Dockerfile             # Docker образ
├── .env                   # Переменные окружения (не в git)
├── credentials.json       # Google API ключи (не в git)
├── processed_emails.txt   # Отслеживание обработанных писем
├── logs/                  # Логи системы
├── downloads/             # Временные файлы email
├── result/               # Итоговые файлы
└── changes.md           # Лог изменений
```

## Функциональность

### Обработка email
- Поиск писем с темой "Остатки Подольск от"
- Скачивание ZIP архивов
- Извлечение Excel файлов с остатками
- Отслеживание обработанных писем

### Работа с Google Sheets
- Подключение через Google Sheets API
- Поиск артикулов в столбце A
- Обновление остатков в столбце E ("Кол-во")
- Загрузка полных данных таблицы

### Обработка данных
- Фильтрация товаров с нулевыми остатками
- Ограничение остатков до 10 штук максимум
- Очистка и валидация данных

### Загрузка на GitHub
- Создание Excel файла с заголовками
- Автоматическая загрузка через GitHub API
- Проверка изменений (загрузка только при обновлениях)

## Логирование

Система ведет подробные логи:
- Файл: `logs/emex_log_YYYY-MM-DD.log`
- Вывод в консоль и файл одновременно
- Уровни: INFO, WARNING, ERROR

## Мониторинг

- Логи cron: проверка работы расписания
- Логи приложения: детальная трассировка обработки
- Файл `processed_emails.txt`: история обработанных писем

## Безопасность

- Все секретные данные в `.env` файле
- `credentials.json` и `.env` исключены из git
- Использование токенов и сервисных аккаунтов

## Версии

### v3.0 (текущая)
- Интеграция с Google Sheets
- Остатки из email + цены из Google таблицы
- Заголовки в итоговом файле

### v2.1
- Адаптация под "Остатки Подольск от"
- Использование столбца "Доступно"

### v2.0
- Группировка по артикулам
- Ограничение остатков до 10 штук

### v1.0
- Базовая обработка email и Excel файлов

## Контакты

Для вопросов по настройке и эксплуатации системы обращайтесь к разработчику.
