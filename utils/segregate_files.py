# # Extract only the first page text (in uppercase for case-insensitive matching)
# def extract_first_page_text(pdf_path):
#     try:
#         doc = fitz.open(pdf_path)
#         if doc.page_count > 0:
#             return doc[0].get_text().upper()
#         else:
#             return ""
#     except Exception as e:
#         print(f"[!] Could not read {pdf_path}: {e}")
#         return ""

# # Match IFSC prefix to bank name
# def identify_bank_from_ifsc(text):
#     if "IBKL" in text:
#         return "idbi"
#     elif "FDRL" in text:
#         return "federal"
#     elif "HDFC" in text:
#         return "hdfc"
#     elif "SBIN" in text:
#         return "sbi"
#     elif "CNRB" in text:
#         return "canara"
#     else:
#         return "others"

# # Move file to bank-specific folder
# def move_pdf(pdf_path, output_root, bank_name):
#     dest_folder = os.path.join(output_root, bank_name)
#     os.makedirs(dest_folder, exist_ok=True)
#     dest_path = os.path.join(dest_folder, os.path.basename(pdf_path))
#     shutil.move(pdf_path, dest_path)
#     print(f"[✓] {os.path.basename(pdf_path)} → {bank_name}")

# # Runner: Classify all PDFs in a directory
# def classify_pdfs_by_bank(input_folder, output_root):
#     for dirpath, _, filenames in os.walk(input_folder):
#         for filename in filenames:
#             if filename.lower().endswith(".pdf"):
#                 pdf_path = os.path.join(dirpath, filename)
#                 first_page_text = extract_first_page_text(pdf_path)
#                 bank_name = identify_bank_from_ifsc(first_page_text)
#                 move_pdf(pdf_path, output_root, bank_name)


# source_dir = "C:/Users/Aravind/Bluetooth/bank_statement_anomalies/data/data"
# destination_dir = "C:/Users/Aravind/Bluetooth/bank_statement_anomalies/banks"
# classify_pdfs_by_bank(source_dir, destination_dir)

import fitz
import os
import shutil
import re

# Extract text from the first page of the PDF
def extract_first_page_text(pdf_path):
    try:
        doc = fitz.open(pdf_path)
        if doc.page_count > 0:
            return doc[0].get_text()
    except Exception as e:
        print(f"[!] Could not read {pdf_path}: {e}")
    return ""

def extract_first_ifsc(text):
    text_upper = text.upper()

    # 1. Look for "RTGS/NEFT IFSC" label (specific pattern)
    label_match = re.search(r'RTGS/NEFT IFSC\s*:\s*([A-Z]{4}0[A-Z0-9]{6})', text_upper)
    if label_match:
        return label_match.group(1)

    # 2. Fallback: match any IFSC-looking string
    generic_match = re.search(r'\b([A-Z]{4}0[A-Z0-9]{6})\b', text_upper)
    if generic_match:
        return generic_match.group(1)

    # 3. Fallback: mention of HDFC BANK
    if "HDFC BANK" in text_upper:
        return "HDFC0000000"  # Dummy IFSC to trigger classification
    return None

def bank_from_ifsc_prefix(ifsc):
    if not ifsc:
        return "others"

    prefix = ifsc[:4]
    return {
        "HDFC": "hdfc",
        "SBIN": "sbi",
        "ICIC": "icici",
        "CNRB": "canara",
        "IBKL": "idbi",
        "IDIB": "indian",
        "UTIB": "axis",
        "BARB": "bob",
        "FDRL": "federal",
        "TMBL": "tmb",
        "UBIN": "union",
        "CIUB": "city_union",
        "IDFB": "idfc",
        "DLXB": "dhanlaxmi",
        "PUNB": "punjab_national"
    }.get(prefix, "others")

def move_pdf(pdf_path, output_root, correct_bank):
    dest_folder = os.path.join(output_root, correct_bank)
    os.makedirs(dest_folder, exist_ok=True)

    dest_path = os.path.join(dest_folder, os.path.basename(pdf_path))

    if os.path.abspath(os.path.dirname(pdf_path)) == os.path.abspath(dest_folder):
        print(f"[=] Already in correct folder: {os.path.basename(pdf_path)}")
        return

    shutil.move(pdf_path, dest_path)
    print(f"[✓] Moved to {correct_bank}: {os.path.basename(pdf_path)}")

def reclassify_pdfs(root_folder):
    for dirpath, _, filenames in os.walk(root_folder):
        for filename in filenames:
            if filename.lower().endswith(".pdf"):
                pdf_path = os.path.join(dirpath, filename)
                print(f"\n📄 Processing: {filename}")

                text = extract_first_page_text(pdf_path)
                ifsc = extract_first_ifsc(text)
                bank = bank_from_ifsc_prefix(ifsc)

                print(f"🏦 IFSC Detected: {ifsc} → Bank: {bank}")
                move_pdf(pdf_path, root_folder, bank)

bank_folders_path = "C:/Users/Aravind/Bluetooth/bank_statement_anomalies/banks"
reclassify_pdfs(bank_folders_path)
