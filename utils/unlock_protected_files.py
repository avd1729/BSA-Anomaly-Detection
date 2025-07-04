import os
import csv
from PyPDF2 import PdfReader, PdfWriter

def load_password_map(csv_path):
    password_map = {}
    with open(csv_path, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            app_id = row['app_id'].strip()
            password = row['statement_password'].strip()
            password_map[app_id] = password
    return password_map

def unlock_pdf(pdf_path, password):
    try:
        with open(pdf_path, 'rb') as f:
            reader = PdfReader(f)
            if reader.is_encrypted:
                result = reader.decrypt(password)
                if result == 0:
                    print(f"[!] Failed to decrypt {pdf_path} with password '{password}'")
                    return

            writer = PdfWriter()
            for page in reader.pages:
                writer.add_page(page)

            with open(pdf_path, 'wb') as out_f:
                writer.write(out_f)

        print(f"[✓] Unlocked and overwritten: {pdf_path}")
    except Exception as e:
        print(f"[!] Error processing {pdf_path}: {e}")

def unlock_pdfs_by_folder(root_folder, password_map):
    for dirpath, dirnames, filenames in os.walk(root_folder):
        # Get the immediate folder name
        folder_name = os.path.basename(dirpath)
        if folder_name in password_map:
            password = password_map[folder_name]
            for filename in filenames:
                if filename.lower().endswith('.pdf'):
                    full_path = os.path.join(dirpath, filename)
                    unlock_pdf(full_path, password)


csv_path = "C:/Users/Aravind/Bluetooth/bank_statement_anomalies/passwords.csv"
root_directory = "C:/Users/Aravind/Bluetooth/bank_statement_anomalies/data/data"

password_map = load_password_map(csv_path)
unlock_pdfs_by_folder(root_directory, password_map)
