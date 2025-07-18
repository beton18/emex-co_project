# Лог изменений проекта EMEX

## 2024-12-19 - ЗАВЕРШЕНИЕ РАЗРАБОТКИ v3.0 ✅

**Статус:** Разработка завершена, готово к тестированию
**Результат:** Все компоненты системы переписаны под новую архитектуру с Google Sheets
**Готово к production:** Требуется только настройка credentials.json и обновление .env
**Следующий шаг:** Пользовательское тестирование и развертывание

------

## 2024-12-19 - ФУНДАМЕНТАЛЬНЫЕ ИЗМЕНЕНИЯ v3.0

**Проблема:** Необходимость изменения источника данных - теперь цены должны браться из Google таблицы, а не из 1С
**Причина:** Изменение бизнес-процессов - цены теперь ведутся в Google таблице, остатки по-прежнему приходят из 1С
**Решение:** Кардинальная реструктуризация системы с интеграцией Google Sheets API
**Изменения:**
- Добавлены зависимости для Google Sheets API: google-auth, gspread, google-api-python-client
- Добавлены переменные окружения: SPREADSHEET_ID, SHEET_NAME в env_example.txt
- Новые функции: get_google_sheets_client(), load_google_sheets_data(), update_google_sheets_stock()
- Изменена функция upload_feed_to_github() - теперь принимает DataFrame и добавляет заголовки столбцов
- Переписана логика process_google_sheets_with_stock() (была process_price_files())
- Изменен основной flow: остатки из email → обновление Google таблицы → загрузка данных → фильтрация → GitHub
- Структура Google таблицы: Артикул | Наименование | Бренд | Цена | Кол-во | Кратность
- Товары с нулевыми остатками исключаются из итогового файла
- Файл на GitHub теперь содержит заголовки столбцов
**Результат:** Система теперь работает с Google таблицей как основным источником данных, остатки обновляются из 1С

------

## 2024-12-19 - Изменение источника данных об остатках

**Проблема:** конфликт временного индекса при регистрации  
**Причина:** Неправильный источник данных - использовался столбец "В наличии" (G) вместо "Доступно" (J)
**Решение:** Изменен источник данных в функции load_stock_data() на столбец "Доступно"
**Результат:** Система корректно извлекает остатки из правильного столбца Excel файла

------

## Ранее 2024-12-19 - Устранение бесконечного цикла

**Проблема:** RAG не работает, бот не отвечает на сообщения по базе знаний - система зацикливалась, обрабатывая одни и те же письма
**Причина:** Отсутствие отслеживания обработанных писем, неправильная настройка Docker restart policy
**Решение:** 
- Добавлена система отслеживания processed_emails.txt
- Изменен restart policy в docker-compose.yml с "unless-stopped" на "no"
- Исправлена cron команда с docker-compose exec на docker-compose run --rm
- Добавлено комплексное логирование
**Результат:** Система работает корректно, каждое письмо обрабатывается только один раз, контейнер завершается после обработки 