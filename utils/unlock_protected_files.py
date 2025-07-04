import os
import csv
from PyPDF2 import PdfReader, PdfWriter

def load_password_map(csv_path):
    """Load app_id to password mapping from CSV file"""
    password_map = {}
    with open(csv_path, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            app_id = row['app_id'].strip()
            password = row['statement_password'].strip()
            password_map[app_id] = password
    return password_map

def unlock_pdf(pdf_path, password):
    """Decrypt and overwrite PDF file with given password"""
    try:
        with open(pdf_path, 'rb') as f:
            reader = PdfReader(f)
            if reader.is_encrypted:
                result = reader.decrypt(password)
                if result == 0:
                    print(f"[!] Failed to decrypt {pdf_path} with password '{password}'")
                    return
            
            # Create new PDF without encryption
            writer = PdfWriter()
            for page in reader.pages:
                writer.add_page(page)
            
            # Overwrite original file
            with open(pdf_path, 'wb') as out_f:
                writer.write(out_f)
        
        print(f"[✓] Unlocked and overwritten: {pdf_path}")
    except Exception as e:
        print(f"[!] Error processing {pdf_path}: {e}")

def unlock_pdfs_by_folder(root_folder, password_map):
    """Walk through folders and unlock PDFs using folder name as app_id"""
    for dirpath, dirnames, filenames in os.walk(root_folder):
        folder_name = os.path.basename(dirpath)
        if folder_name in password_map:
            password = password_map[folder_name]
            for filename in filenames:
                if filename.lower().endswith('.pdf'):
                    full_path = os.path.join(dirpath, filename)
                    unlock_pdf(full_path, password)

def main():
    # File paths
    csv_path = "bank_statement_anomalies/passwords.csv"
    root_directory = "bank_statement_anomalies/data/data"
    
    # Load password mappings and unlock PDFs
    password_map = load_password_map(csv_path)
    unlock_pdfs_by_folder(root_directory, password_map)

if __name__ == "__main__":
    main()