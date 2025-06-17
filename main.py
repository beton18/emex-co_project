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

# Загрузка переменных окружения из .env файла
load_dotenv()

# Функция для проверки уже обработанных архивов
def is_archive_processed(filename):
    """Проверяет, был ли уже обработан данный архив"""
    processed_file = "processed_archives.txt"
    if os.path.exists(processed_file):
        with open(processed_file, 'r', encoding='utf-8') as f:
            processed = f.read().splitlines()
        
        # Проверяем только имя файла (первая часть до |)
        processed_names = [line.split('|')[0] for line in processed if '|' in line]
        return os.path.basename(filename) in processed_names
    return False

def mark_archive_processed(filename):
    """Отмечает архив как обработанный с датой и хешем"""
    processed_file = "processed_archives.txt"
    
    # Вычисляем хеш файла
    file_hash = "unknown"
    if os.path.exists(filename):
        with open(filename, 'rb') as f:
            file_hash = hashlib.md5(f.read()).hexdigest()[:8]
    
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    entry = f"{os.path.basename(filename)}|{timestamp}|{file_hash}"
    
    with open(processed_file, 'a', encoding='utf-8') as f:
        f.write(f"{entry}\n")
    print(f"📝 Архив {os.path.basename(filename)} отмечен как обработанный (хеш: {file_hash})")

"""
ИСТОРИЯ ИЗМЕНЕНИЙ:

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

# Фильтр по теме письма
SUBJECT_PATTERN = re.compile(r"Остатки Подольск от")

# Получение ZIP вложения
def get_mail_attachments():
    if not os.path.exists(SAVE_DIR):
        os.makedirs(SAVE_DIR)

    mail = imaplib.IMAP4_SSL(IMAP_SERVER)
    mail.login(EMAIL, PASSWORD)
    mail.select("inbox")

    status, messages = mail.search(None, 'ALL')
    email_ids = messages[0].split()

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

        print(f"Проверка письма с темой: {subject}")

        if not SUBJECT_PATTERN.search(subject):
            continue

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
                    print(f"Скачан архив: {decoded_filename}")
                    return filepath
    return None

# Распаковка архива
def unzip_archive(zip_path, extract_to=SAVE_DIR):
    extracted_files = []
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_to)
        extracted_files = zip_ref.namelist()
    print(f"Распакованы файлы: {extracted_files}")
    return [os.path.join(extract_to, f) for f in extracted_files]

# Загрузка таблицы остатков
def load_stock_data(files):
    for f in files:
        if 'остатки' in f.lower() and f.endswith('.xlsx'):
            print(f"Загружаем остатки из файла: {f}")
            
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
                print("Не найдена строка с заголовками 'Артикул'")
                continue
                
            df = pd.read_excel(f, skiprows=header_row)
            print(f"Найдены заголовки на строке {header_row + 1}")
            print("Столбцы:", list(df.columns))
            
            # Ищем столбцы с артикулом и количеством
            article_col = None
            quantity_col = None
            
            for col in df.columns:
                col_str = str(col).lower()
                if 'артикул' in col_str:
                    article_col = col
                elif 'в наличии' in col_str or 'сейчас' in col_str:
                    quantity_col = col
            
            if article_col is None or quantity_col is None:
                print(f"Не найдены нужные столбцы. Артикул: {article_col}, Количество: {quantity_col}")
                continue
                
            print(f"Используем столбцы: '{article_col}' (артикул), '{quantity_col}' (количество)")
            
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
            
            print(f"Загружено {len(stock_df)} записей об остатках")
            print("Первые 5 записей:")
            print(stock_df.head())
            
            return stock_df
    
    print("Файл с остатками не найден")
    return pd.DataFrame(columns=['№ Детали', 'Количество, шт'])

# Загрузка фида на GitHub Pages
def upload_feed_to_github(csv_file_path):
    """Загружает CSV файл в GitHub репозиторий для создания фида"""
    if not GITHUB_TOKEN or not GITHUB_REPO:
        print("⚠️ GitHub настройки не заполнены. Пропускаем загрузку фида.")
        print("Заполните GITHUB_TOKEN и GITHUB_REPO в настройках.")
        return False
    
    try:
        # Читаем содержимое файла (убираем BOM для корректного сравнения)
        with open(csv_file_path, 'r', encoding='utf-8-sig') as file:
            content = file.read()
        
        # Убираем BOM если есть для корректного сравнения
        if content.startswith('\ufeff'):
            content = content[1:]
            
        # Данные для GitHub API
        url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/price_for_emex.csv"
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
            # Декодируем существующее содержимое
            current_content = base64.b64decode(file_data['content']).decode('utf-8')
        
        # Проверяем, изменилось ли содержимое
        if current_content == content:
            print("📄 Данные не изменились, загрузка не требуется")
            return True
        
        print("📄 Обнаружены изменения в данных, загружаем...")
        
        # Дополнительное логирование для отладки
        if current_content:
            print(f"🔍 Длина старого файла: {len(current_content)} символов")
            print(f"🔍 Длина нового файла: {len(content)} символов")
            if len(current_content) > 100 and len(content) > 100:
                print(f"🔍 Первые 100 символов старого: {repr(current_content[:100])}")
                print(f"🔍 Первые 100 символов нового: {repr(content[:100])}")
        else:
            print("🔍 Старый файл не найден - это первая загрузка")
        
        # Кодируем в base64 для GitHub API
        encoded_content = base64.b64encode(content.encode('utf-8')).decode('utf-8')
        
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
            feed_url = f"https://raw.githubusercontent.com/{GITHUB_REPO}/refs/heads/main/price_for_emex.csv"
            print(f"✅ Фид успешно загружен!")
            print(f"🔗 Ссылка на фид: {feed_url}")
            return True
        else:
            print(f"❌ Ошибка загрузки фида: {response.status_code}")
            print(f"Ответ: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка при загрузке фида: {e}")
        return False

# Обработка прайс-листов
def process_price_files(xlsx_files, stock_df):
    if not os.path.exists(RESULT_DIR):
        os.makedirs(RESULT_DIR)

    for file_path in xlsx_files:
        if 'прайс' in file_path.lower() and file_path.endswith('.xlsx'):
            try:
                print(f"Обрабатываем прайс-лист: {file_path}")
                df = pd.read_excel(file_path, header=None, skiprows=5)
                selected = df[[0, 5, 13]].copy()
                selected.columns = ['№ Детали', 'Наименование', 'Цена']
                selected.insert(1, 'Марка', 'AVTOPRIBOR')
                selected = selected.dropna(subset=['№ Детали', 'Цена'])
                selected['№ Детали'] = selected['№ Детали'].astype(str).str.strip()

                # Очистка наименования
                def clean_name(row):
                    article = row['№ Детали']
                    name = str(row['Наименование']).strip()
                    if name.startswith(article):
                        name = name[len(article):].strip()
                    name = name.replace('"', '').replace(',', '')
                    return name

                selected['Наименование'] = selected.apply(clean_name, axis=1)

                # Подстановка количества
                print(f"Объединяем с данными об остатках...")
                merged = pd.merge(selected, stock_df, on='№ Детали', how='left')
                merged['Количество, шт'] = merged['Количество, шт'].fillna(0)
                
                # Форматируем количество как целое число (убираем .0)
                merged['Количество, шт'] = merged['Количество, шт'].astype(int)
                
                # Добавляем наценку 20% к цене и округляем до сотых
                merged['Цена'] = (merged['Цена'] * 1.2).round(2)
                
                # Определяем кратность: 2 только для тормозных дисков, 1 для остального
                merged['Кратность'] = merged['Наименование'].apply(
                    lambda x: 2 if 'диск тормозной' in str(x).lower() else 1
                )
                
                # Группируем по артикулу и суммируем остатки
                grouped = merged.groupby('№ Детали').agg({
                    'Наименование': 'first',
                    'Марка': 'first', 
                    'Цена': 'first',
                    'Количество, шт': 'sum',
                    'Кратность': 'first'
                }).reset_index()
                
                # Ограничиваем остатки до 10 после группировки
                grouped['Остатки'] = grouped['Количество, шт'].apply(lambda x: min(x, 10) if x > 0 else 0)
                
                # Исключаем товары с нулевыми остатками
                grouped = grouped[grouped['Остатки'] > 0]
                print(f"После исключения товаров с нулевыми остатками: {len(grouped)} записей")

                # Замена точки на запятую в цене (только для CSV)
                grouped_csv = grouped.copy()
                grouped_csv['Цена'] = grouped_csv['Цена'].astype(str).str.replace('.', ',', regex=False)

                # Переупорядочиваем столбцы в новом порядке
                final_csv = grouped_csv[['№ Детали', 'Наименование', 'Марка', 'Цена', 'Остатки', 'Кратность']]
                
                final_xlsx = grouped[['№ Детали', 'Наименование', 'Марка', 'Цена', 'Остатки', 'Кратность']]
                final_xlsx.columns = ['№ детали', 'Наименование', 'Марка', 'Цена', 'Количество', 'Партионность']

                # Сохраняем CSV файл
                result_path_csv = os.path.join(RESULT_DIR, "price_for_emex.csv")
                final_csv.to_csv(result_path_csv, index=False, header=False, sep=',', encoding='utf-8-sig')
                print(f"Создан CSV файл: {result_path_csv}")
                
                # Сохраняем XLSX файл
                result_path_xlsx = os.path.join(RESULT_DIR, "price_for_emex.xlsx")
                final_xlsx.to_excel(result_path_xlsx, index=False, engine='openpyxl')
                print(f"Создан XLSX файл: {result_path_xlsx}")
                
                print(f"Обработано {len(final_csv)} уникальных артикулов (только с остатками)")
                
                # Показываем статистику
                print(f"В итоговом датасете: {len(final_csv)} товаров с остатками > 0")
                print(f"Цены увеличены на 20% и округлены до сотых, остатки сгруппированы и ограничены до 10 штук")
                
                # Загружаем фид на GitHub Pages
                print("\n📡 Загрузка фида в интернет...")
                upload_feed_to_github(result_path_csv)
                
            except Exception as e:
                print(f"Ошибка при обработке {file_path}: {e}")

# Основной запуск
if __name__ == "__main__":
    zip_file = get_mail_attachments()
    if zip_file:
        if is_archive_processed(zip_file):
            print(f"Архив {zip_file} уже обработан. Пропускаем обработку.")
        else:
            extracted = unzip_archive(zip_file)
            stock_df = load_stock_data(extracted)
            process_price_files(extracted, stock_df)
            mark_archive_processed(zip_file)
    else:
        print("Архив не найден.")