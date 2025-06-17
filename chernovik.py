import imaplib
import email
from email.header import decode_header
import os
import zipfile
import pandas as pd
import datetime
import re

# Настройки почты
EMAIL = "daniil.syryh@gmail.com"
PASSWORD = "adgr vgml pqye ljnq"  # Используй пароль приложения
IMAP_SERVER = "imap.gmail.com"
SAVE_DIR = "downloads"

# Фильтр по теме письма
SUBJECT_PATTERN = re.compile(r"Прайс-лист от")

# Подключение к почте и поиск нужных писем
def get_mail_attachments():
    if not os.path.exists(SAVE_DIR):
        os.makedirs(SAVE_DIR)

    mail = imaplib.IMAP4_SSL(IMAP_SERVER)
    mail.login(EMAIL, PASSWORD)
    mail.select("inbox")

    status, messages = mail.search(None, 'ALL')
    email_ids = messages[0].split()

    for email_id in reversed(email_ids):  # Смотрим с последнего письма
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
                    return filepath  # только первый архив
    return None

# Распаковка архива
def unzip_archive(zip_path, extract_to=SAVE_DIR):
    extracted_files = []
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_to)
        extracted_files = zip_ref.namelist()
    print(f"Распакованы файлы: {extracted_files}")
    return [os.path.join(extract_to, f) for f in extracted_files]

# Конвертация xlsx в csv
def convert_xlsx_to_csv(xlsx_files):
    for file_path in xlsx_files:
        if file_path.endswith('.xlsx'):
            df = pd.read_excel(file_path)
            csv_path = file_path.replace(".xlsx", ".csv")
            df.to_csv(csv_path, index=False)
            print(f"Сохранен CSV: {csv_path}")

if __name__ == "__main__":
    zip_file = get_mail_attachments()
    if zip_file:
        extracted = unzip_archive(zip_file)
        convert_xlsx_to_csv(extracted)
    else:
        print("Архив не найден.")
