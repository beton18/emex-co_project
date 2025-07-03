import imaplib
import email
from email.header import decode_header
import os
import zipfile
import pandas as pd
import re
import requests
import base64
from datetime import datetime
from dotenv import load_dotenv
import hashlib
import logging
import gspread
from google.oauth2.service_account import Credentials

# Загрузка переменных окружения из .env файла
load_dotenv()

# Настройка логирования
def setup_logging():
    """Настраивает логирование в файл и консоль"""
    # Создаем папку logs если её нет
    os.makedirs('logs', exist_ok=True)
    log_filename = f"logs/emex_log_{datetime.now().strftime('%Y-%m-%d')}.log"
    
    # Создаем форматтер
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Настраиваем root logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # Очищаем существующие handlers
    logger.handlers.clear()
    
    # Handler для файла
    file_handler = logging.FileHandler(log_filename, encoding='utf-8')
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)
    logger.addHandler(file_handler)
    
    # Handler для консоли
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)
    logger.addHandler(console_handler)
    
    return logger

# Инициализируем логгер
logger = setup_logging()

def log_and_print(message, level="info"):
    """Функция для одновременного логирования и вывода в консоль"""
    if level == "error":
        logger.error(message)
    elif level == "warning":
        logger.warning(message)
    else:
        logger.info(message)

# Функция для проверки уже обработанных архивов
def is_email_processed(subject):
    """Проверяет, было ли уже обработано письмо с данной темой"""
    # Сохраняем файл в корне проекта (примонтированная папка)
    processed_file = "/app/processed_emails.txt"
    if os.path.exists(processed_file):
        with open(processed_file, 'r', encoding='utf-8') as f:
            processed = f.read().splitlines()
        
        # Проверяем только тему письма (первая часть до |)
        processed_subjects = [line.split('|')[0] for line in processed if '|' in line]
        return subject in processed_subjects
    return False

def mark_email_processed(subject):
    """Отмечает письмо как обработанное по теме"""
    # Сохраняем файл в корне проекта (примонтированная папка)
    processed_file = "/app/processed_emails.txt"
    
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    entry = f"{subject}|{timestamp}"
    
    with open(processed_file, 'a', encoding='utf-8') as f:
        f.write(f"{entry}\n")
    log_and_print(f"📝 Письмо '{subject}' отмечено как обработанное")

# Функции для работы с Google Sheets
def get_google_sheets_client():
    """Создает клиент для работы с Google Sheets"""
    try:
        # Определяем области доступа
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        
        # Загружаем учетные данные из файла
        creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=scopes)
        client = gspread.authorize(creds)
        
        log_and_print("✅ Подключение к Google Sheets установлено")
        return client
    except Exception as e:
        log_and_print(f"❌ Ошибка подключения к Google Sheets: {e}", "error")
        return None

def load_google_sheets_data():
    """Загружает данные из Google таблицы"""
    if not SPREADSHEET_ID:
        log_and_print("⚠️ SPREADSHEET_ID не установлен", "warning")
        return pd.DataFrame()
    
    try:
        client = get_google_sheets_client()
        if not client:
            return pd.DataFrame()
        
        # Открываем таблицу
        sheet = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)
        
        # Получаем все данные
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        
        log_and_print(f"📊 Загружено {len(df)} записей из Google таблицы")
        
        # Проверяем наличие нужных столбцов
        required_columns = ['Артикул', 'Наименование', 'Бренд', 'Цена', 'Кол-во', 'Кратность']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            log_and_print(f"⚠️ Отсутствуют столбцы в Google таблице: {missing_columns}", "warning")
            return pd.DataFrame()
        
        return df
        
    except Exception as e:
        log_and_print(f"❌ Ошибка загрузки данных из Google Sheets: {e}", "error")
        return pd.DataFrame()

def update_google_sheets_stock(stock_updates):
    """Обновляет остатки в Google таблице по артикулам"""
    if not SPREADSHEET_ID or stock_updates.empty:
        return False
    
    try:
        client = get_google_sheets_client()
        if not client:
            return False
        
        # Открываем таблицу
        sheet = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)
        
        # Получаем все значения для поиска артикулов
        all_values = sheet.get_all_values()
        
        if not all_values:
            log_and_print("❌ Google таблица пуста", "error")
            return False
        
        # Находим индекс столбца "Кол-во" (E - это 5-й столбец)
        header_row = all_values[0]
        qty_col_index = None
        article_col_index = None
        
        for i, col_name in enumerate(header_row):
            if 'кол-во' in col_name.lower():
                qty_col_index = i
            if 'артикул' in col_name.lower():
                article_col_index = i
        
        if qty_col_index is None or article_col_index is None:
            log_and_print("❌ Не найдены столбцы 'Артикул' или 'Кол-во' в Google таблице", "error")
            return False
        
        log_and_print(f"🔍 Найдены столбцы: Артикул (индекс {article_col_index}), Кол-во (индекс {qty_col_index})")
        
        updated_count = 0
        
        # Обновляем остатки построчно
        for row_idx in range(1, len(all_values)):  # Пропускаем заголовок
            article = all_values[row_idx][article_col_index].strip()
            
            # Ищем артикул в данных остатков
            matching_stock = stock_updates[stock_updates['№ Детали'] == article]
            
            if not matching_stock.empty:
                new_qty = int(matching_stock.iloc[0]['Количество, шт'])
                
                # Обновляем ячейку с количеством (row_idx + 1 потому что gspread использует 1-based индексацию)
                cell = sheet.cell(row_idx + 1, qty_col_index + 1)
                if cell.value != str(new_qty):
                    sheet.update_cell(row_idx + 1, qty_col_index + 1, new_qty)
                    updated_count += 1
                    log_and_print(f"✅ Обновлен остаток для {article}: {new_qty}")
        
        log_and_print(f"📊 Обновлено {updated_count} записей в Google таблице")
        return True
        
    except Exception as e:
        log_and_print(f"❌ Ошибка обновления Google Sheets: {e}", "error")
        return False

"""
ИСТОРИЯ ИЗМЕНЕНИЙ:

v3.0 - ФУНДАМЕНТАЛЬНЫЕ ИЗМЕНЕНИЯ - Интеграция с Google Sheets:
- Кардинальное изменение архитектуры: цены теперь берутся из Google таблицы
- Остатки по-прежнему обновляются из почты (1С выгрузки)
- Добавлена интеграция с Google Sheets API через gspread
- Структура Google таблицы: Артикул | Наименование | Бренд | Цена | Кол-во | Кратность
- Логика работы:
  1. Загружаем остатки из email (только Артикул + Кол-во)
  2. Обновляем столбец "Кол-во" в Google таблице по артикулам
  3. Загружаем всю обновленную Google таблицу
  4. Фильтруем товары с нулевыми остатками
  5. Добавляем заголовки столбцов в итоговый файл
  6. Загружаем на GitHub как Excel с заголовками
- Добавлены новые зависимости: google-auth, gspread, google-api-python-client
- Добавлены переменные окружения: SPREADSHEET_ID, SHEET_NAME
- Изменена функция upload_feed_to_github: теперь принимает DataFrame и добавляет заголовки

v2.1 - Адаптация под новую почтовую рассылку:
- Обновлён паттерн поиска писем: "Остатки Подольск от" вместо "Прайс-лист от"
- Адаптирована логика парсинга файла остатков под новую структуру:
  * Автоматический поиск строки с заголовками "Артикул"
  * Гибкий поиск столбцов "Артикул" и "В наличии"/"Сейчас"
  * Поддержка нового формата с названием "Остатки и доступность товаров"
- Уточнена логика кратности: 2 только для "диск тормозной", 1 для остальных
- Переименованы выходные файлы в "price_for_emex.csv" и "price_for_emex.xlsx"
- Исключены товары с нулевыми остатками из итогового датасета
- Обновлены названия столбцов: № детали, Наименование, Марка, Цена, Количество, Партионность
- Добавлена автоматическая загрузка фида на GitHub Pages для EMEX
- Добавлена поддержка .env файлов для безопасного хранения конфиденциальных данных
- Создан .gitignore для исключения конфиденциальных файлов из Git

v2.0 - Обновления структуры данных:
- Изменён порядок столбцов: Артикул, Наименование, Бренд, Цена, Остатки, Кратность
- Переименованы столбцы: № Детали → Артикул, Наименование детали → Наименование, 
  Марка → Бренд, Цена детали → Цена, Количество шт → Остатки
- Добавлена наценка 20% к ценам с округлением до сотых
- Ограничены остатки: максимум 10 штук (если больше, показываем 10)
- Добавлен столбец "Кратность": 1 по умолчанию, 2 для товаров со словом "диск"
- Реализована группировка по артикулам с суммированием остатков (убраны дубликаты)

v1.0 - Базовая функциональность:
- Извлечение прайс-листов из Gmail
- Объединение данных о ценах и остатках
- Экспорт в CSV и XLSX форматы
"""

# Настройки почты
EMAIL = os.getenv("EMAIL", "daniil.syryh@gmail.com")
PASSWORD = os.getenv("PASSWORD", "adgr vgml pqye ljnq")  # Используй пароль приложения
IMAP_SERVER = os.getenv("IMAP_SERVER", "imap.gmail.com")
SAVE_DIR = "downloads"
RESULT_DIR = "result"

# Настройки для загрузки фида на GitHub
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")  # Токен GitHub из .env файла
GITHUB_REPO = os.getenv("GITHUB_REPO", "")    # Например: "username/emex-feed"
FEED_URL = os.getenv("FEED_URL", "")          # Будущая ссылка на фид

# Настройки для Google Sheets
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID", "")
SHEET_NAME = os.getenv("SHEET_NAME", "Sheet1")
CREDENTIALS_FILE = "credentials.json"

# Фильтр по теме письма
SUBJECT_PATTERN = re.compile(r"Остатки Подольск от")

# Получение ZIP вложения
def get_mail_attachments():
    log_and_print("🔍 Начинаем поиск писем с прайс-листами...")
    
    if not os.path.exists(SAVE_DIR):
        os.makedirs(SAVE_DIR)

    mail = imaplib.IMAP4_SSL(IMAP_SERVER)
    mail.login(EMAIL, PASSWORD)
    mail.select("inbox")
    log_and_print("✅ Подключение к почте установлено")

    status, messages = mail.search(None, 'ALL')
    email_ids = messages[0].split()
    log_and_print(f"📧 Найдено {len(email_ids)} писем в почтовом ящике")

    for email_id in reversed(email_ids):
        status, msg_data = mail.fetch(email_id, "RFC822")
        if status != 'OK':
            continue

        msg = email.message_from_bytes(msg_data[0][1])
        subject_header = decode_header(msg["Subject"])
        subject_parts = []
        for s, enc in subject_header:
            if isinstance(s, bytes):
                s = s.decode(enc if enc else "utf-8")
            subject_parts.append(s)
        subject = ''.join(subject_parts)

        log_and_print(f"🔍 Проверка письма с темой: {subject}")

        if not SUBJECT_PATTERN.search(subject):
            continue

        # Проверяем, не обработано ли уже это письмо
        if is_email_processed(subject):
            log_and_print(f"📧 Письмо '{subject}' уже обработано. Пропускаем.")
            continue

        log_and_print(f"🎯 Найдено новое письмо: {subject}")

        for part in msg.walk():
            if part.get_content_maintype() == 'multipart':
                continue
            if part.get('Content-Disposition') is None:
                continue

            filename = part.get_filename()
            if filename:
                decoded_filename = decode_header(filename)[0][0]
                if isinstance(decoded_filename, bytes):
                    decoded_filename = decoded_filename.decode()

                if decoded_filename.endswith(".zip"):
                    filepath = os.path.join(SAVE_DIR, decoded_filename)
                    with open(filepath, "wb") as f:
                        f.write(part.get_payload(decode=True))
                    log_and_print(f"📦 Скачан архив: {decoded_filename}")
                    
                    # Возвращаем кортеж: путь к архиву и тему письма
                    return filepath, subject
    
    log_and_print("📭 Новых писем с архивами не найдено")
    return None, None

# Распаковка архива
def unzip_archive(zip_path, extract_to=SAVE_DIR):
    extracted_files = []
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_to)
        extracted_files = zip_ref.namelist()
    log_and_print(f"📁 Распакованы файлы: {extracted_files}")
    return [os.path.join(extract_to, f) for f in extracted_files]

# Загрузка таблицы остатков
def load_stock_data(files):
    for f in files:
        if 'остатки' in f.lower() and f.endswith('.xlsx'):
            log_and_print(f"Загружаем остатки из файла: {f}")
            
            # Ищем строку с заголовками "Артикул" и "В наличии"
            header_row = None
            for i in range(15):  # Проверяем первые 15 строк
                try:
                    df_check = pd.read_excel(f, skiprows=i, nrows=1)
                    columns = [str(col).lower() for col in df_check.columns]
                    if any('артикул' in col for col in columns):
                        header_row = i
                        break
                except:
                    continue
            
            if header_row is None:
                log_and_print("Не найдена строка с заголовками 'Артикул'")
                continue
                
            df = pd.read_excel(f, skiprows=header_row)
            log_and_print(f"Найдены заголовки на строке {header_row + 1}")
            log_and_print("Столбцы:", list(df.columns))
            
            # Ищем столбцы с артикулом и количеством
            article_col = None
            quantity_col = None
            
            for col in df.columns:
                col_str = str(col).lower()
                if 'артикул' in col_str:
                    article_col = col
                elif 'доступно' in col_str:
                    quantity_col = col
            
            if article_col is None or quantity_col is None:
                log_and_print(f"Не найдены нужные столбцы. Артикул: {article_col}, Количество: {quantity_col}")
                continue
                
            log_and_print(f"Используем столбцы: '{article_col}' (артикул), '{quantity_col}' (количество)")
            
            # Извлекаем нужные столбцы
            stock_df = df[[article_col, quantity_col]].copy()
            stock_df.columns = ['№ Детали', 'Количество, шт']
            
            # Очищаем артикулы
            stock_df['№ Детали'] = stock_df['№ Детали'].astype(str).str.strip()
            
            # Убираем пустые строки по артикулу
            stock_df = stock_df.dropna(subset=['№ Детали'])
            
            # Убираем строки где артикул это 'nan'
            stock_df = stock_df[stock_df['№ Детали'] != 'nan']
            
            # Обработка количества
            stock_df['Количество, шт'] = pd.to_numeric(stock_df['Количество, шт'], errors='coerce').fillna(0)
            
            log_and_print(f"Загружено {len(stock_df)} записей об остатках")
            log_and_print("Первые 5 записей:")
            log_and_print(stock_df.head())
            
            return stock_df
    
    log_and_print("Файл с остатками не найден")
    return pd.DataFrame(columns=['№ Детали', 'Количество, шт'])

# Загрузка фида на GitHub Pages
def upload_feed_to_github(df_data, filename="price_for_emex.xlsx"):
    """Загружает DataFrame в Excel формате в GitHub репозиторий с заголовками"""
    if not GITHUB_TOKEN or not GITHUB_REPO:
        log_and_print("⚠️ GitHub настройки не заполнены. Пропускаем загрузку фида.", "warning")
        log_and_print("Заполните GITHUB_TOKEN и GITHUB_REPO в настройках.", "warning")
        return False
    
    try:
        # Создаем Excel файл в памяти с заголовками
        log_and_print("📊 Создаем Excel файл с заголовками...")
        import io
        excel_buffer = io.BytesIO()
        df_data.to_excel(excel_buffer, index=False, header=True, engine='openpyxl')
        excel_content = excel_buffer.getvalue()
        
        # Данные для GitHub API
        url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{filename}"
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        # Проверяем, существует ли файл (для обновления нужен SHA)
        get_response = requests.get(url, headers=headers)
        sha = None
        current_content = None
        
        if get_response.status_code == 200:
            file_data = get_response.json()
            sha = file_data['sha']
            # Декодируем существующее содержимое (Excel файл)
            current_content = base64.b64decode(file_data['content'])
        
        # Проверяем, изменилось ли содержимое
        if current_content == excel_content:
            log_and_print("📄 Данные не изменились, загрузка не требуется")
            return True
        
        log_and_print("📄 Обнаружены изменения в данных, загружаем...")
        
        # Дополнительное логирование для отладки
        if current_content:
            log_and_print(f"🔍 Размер старого файла: {len(current_content)} байт")
            log_and_print(f"🔍 Размер нового файла: {len(excel_content)} байт")
        else:
            log_and_print("🔍 Старый файл не найден - это первая загрузка")
        
        # Кодируем в base64 для GitHub API
        encoded_content = base64.b64encode(excel_content).decode('utf-8')
        
        # Данные для создания/обновления файла
        data = {
            "message": f"Обновление фида EMEX - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "content": encoded_content
        }
        
        if sha:
            data["sha"] = sha
        
        # Отправляем запрос
        response = requests.put(url, json=data, headers=headers)
        
        if response.status_code in [200, 201]:
            feed_url = f"https://raw.githubusercontent.com/{GITHUB_REPO}/refs/heads/main/{filename}"
            log_and_print(f"✅ Excel фид успешно загружен!")
            log_and_print(f"🔗 Ссылка на фид: {feed_url}")
            return True
        else:
            log_and_print(f"❌ Ошибка загрузки фида: {response.status_code}", "error")
            log_and_print(f"Ответ: {response.text}", "error")
            return False
            
    except Exception as e:
        log_and_print(f"❌ Ошибка при загрузке фида: {e}", "error")
        return False

# Обработка данных из Google таблицы и остатков
def process_google_sheets_with_stock(stock_df):
    """Обновляет остатки в Google таблице и создает финальный фид"""
    if not os.path.exists(RESULT_DIR):
        os.makedirs(RESULT_DIR)
    
    try:
        # Шаг 1: Обновляем остатки в Google таблице
        log_and_print("🔄 Обновляем остатки в Google таблице...")
        update_success = update_google_sheets_stock(stock_df)
        
        if not update_success:
            log_and_print("❌ Ошибка обновления Google таблицы", "error")
            return False
        
        # Шаг 2: Загружаем обновленные данные из Google таблицы
        log_and_print("📊 Загружаем данные из Google таблицы...")
        google_df = load_google_sheets_data()
        
        if google_df.empty:
            log_and_print("❌ Не удалось загрузить данные из Google таблицы", "error")
            return False
        
        log_and_print(f"📋 Загружено {len(google_df)} записей из Google таблицы")
        
        # Шаг 3: Обрабатываем данные
        # Очищаем данные и приводим к нужным типам
        google_df['Артикул'] = google_df['Артикул'].astype(str).str.strip()
        google_df['Кол-во'] = pd.to_numeric(google_df['Кол-во'], errors='coerce').fillna(0).astype(int)
        google_df['Цена'] = pd.to_numeric(google_df['Цена'], errors='coerce').fillna(0)
        google_df['Кратность'] = pd.to_numeric(google_df['Кратность'], errors='coerce').fillna(1).astype(int)
        
        # Исключаем товары с нулевыми остатками
        filtered_df = google_df[google_df['Кол-во'] > 0].copy()
        log_and_print(f"🔍 После фильтрации товаров с нулевыми остатками: {len(filtered_df)} записей")
        
        if filtered_df.empty:
            log_and_print("⚠️ После фильтрации не осталось товаров с положительными остатками", "warning")
            return False
        
        # Ограничиваем остатки до 10 штук
        filtered_df['Кол-во'] = filtered_df['Кол-во'].apply(lambda x: min(x, 10))
        
        # Переименовываем столбцы для итогового файла
        final_df = filtered_df.copy()
        final_df.columns = ['Артикул', 'Наименование', 'Бренд', 'Цена', 'Кол-во', 'Кратность']
        
        # Сохраняем локальные копии (для отладки)
        result_path_csv = os.path.join(RESULT_DIR, "price_for_emex.csv")
        result_path_xlsx = os.path.join(RESULT_DIR, "price_for_emex.xlsx")
        
        final_df.to_csv(result_path_csv, index=False, sep=',', encoding='utf-8-sig')
        final_df.to_excel(result_path_xlsx, index=False, engine='openpyxl')
        
        log_and_print(f"💾 Созданы локальные файлы: {result_path_csv}, {result_path_xlsx}")
        log_and_print(f"📊 Финальный датасет: {len(final_df)} товаров")
        
        # Шаг 4: Загружаем на GitHub Pages
        log_and_print("\n📡 Загрузка фида на GitHub Pages...")
        upload_success = upload_feed_to_github(final_df, "price_for_emex.xlsx")
        
        if upload_success:
            log_and_print("✅ Обработка завершена успешно!")
            return True
        else:
            log_and_print("⚠️ Локальные файлы созданы, но загрузка на GitHub не удалась", "warning")
            return False
            
    except Exception as e:
        log_and_print(f"❌ Ошибка при обработке данных: {e}", "error")
        return False

# Основной запуск
if __name__ == "__main__":
    log_and_print("🚀 ===== ЗАПУСК ОБРАБОТКИ EMEX =====")
    log_and_print(f"⏰ Время запуска: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        zip_file, subject = get_mail_attachments()
        if zip_file and subject:
            log_and_print(f"🎯 Обрабатываем новое письмо с остатками: {subject}")
            
            # Извлекаем данные об остатках из архива
            extracted = unzip_archive(zip_file)
            stock_df = load_stock_data(extracted)
            
            if stock_df.empty:
                log_and_print("❌ Не удалось загрузить данные об остатках", "error")
            else:
                log_and_print(f"📊 Загружено {len(stock_df)} записей об остатках")
                
                # Обрабатываем данные с Google таблицей
                success = process_google_sheets_with_stock(stock_df)
                
                if success:
                    mark_email_processed(subject)
                    log_and_print(f"✅ Обработка письма '{subject}' завершена успешно")
                else:
                    log_and_print(f"❌ Ошибка при обработке письма '{subject}'", "error")
        else:
            log_and_print("📭 Новых писем с остатками для обработки не найдено.")
    
    except Exception as e:
        log_and_print(f"❌ КРИТИЧЕСКАЯ ОШИБКА: {e}", "error")
        import traceback
        log_and_print(f"📋 Трассировка: {traceback.format_exc()}", "error")
    
    finally:
        log_and_print("🏁 ===== ЗАВЕРШЕНИЕ ОБРАБОТКИ EMEX =====")