import os
import fitz
import json
import re

def load_field_list(field_txt_path):
    with open(field_txt_path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f.readlines() if line.strip()]

def find_field_occurrences(pdf, field_keywords):
    field_metadata = {}

    for page_num in range(len(pdf)):
        page = pdf[page_num]
        blocks = page.get_text("dict")["blocks"]

        for block in blocks:
            if "lines" not in block:
                continue

            for line in block["lines"]:
                line_text = " ".join([span["text"] for span in line["spans"]])
                for keyword in field_keywords:
                    # Try loose match, case insensitive, remove symbols
                    clean_keyword = re.sub(r'[^a-zA-Z0-9]', '', keyword).lower()
                    clean_line = re.sub(r'[^a-zA-Z0-9]', '', line_text).lower()

                    if clean_keyword in clean_line:
                        for span in line["spans"]:
                            field_metadata.setdefault(keyword, []).append({
                                "page": page_num,
                                "x": span["bbox"][0],
                                "y": span["bbox"][1],
                                "width": span["bbox"][2] - span["bbox"][0],
                                "height": span["bbox"][3] - span["bbox"][1],
                                "font": span["font"],
                                "size": span["size"],
                                "bold": "Bold" in span["font"],
                                "italic": "Italic" in span["font"]
                            })
                        break
    return field_metadata

def average_field_metadata(field_meta):
    averaged_template = {}
    for field, spans in field_meta.items():
        if not spans:
            continue

        # Compute average positions and font size
        x = sum(s["x"] for s in spans) / len(spans)
        y = sum(s["y"] for s in spans) / len(spans)
        w = sum(s["width"] for s in spans) / len(spans)
        h = sum(s["height"] for s in spans) / len(spans)
        size = sum(s["size"] for s in spans) / len(spans)
        bold = any(s["bold"] for s in spans)
        italic = any(s["italic"] for s in spans)
        fonts = list(set(s["font"] for s in spans))

        averaged_template[field] = {
            "avg_position": {"x": x, "y": y, "width": w, "height": h},
            "font_size": round(size, 2),
            "fonts": fonts,
            "bold": bold,
            "italic": italic
        }
    return averaged_template

def process_bank_folder(bank_folder_path, fields_txt_path, output_template_path):
    field_list = load_field_list(fields_txt_path)
    all_metadata = {}

    for filename in os.listdir(bank_folder_path):
        if filename.lower().endswith(".pdf"):
            pdf_path = os.path.join(bank_folder_path, filename)
            print(f"📄 Processing {filename}...")

            try:
                pdf = fitz.open(pdf_path)
                pdf_meta = find_field_occurrences(pdf, field_list)
                for k, v in pdf_meta.items():
                    all_metadata.setdefault(k, []).extend(v)
            except Exception as e:
                print(f"[!] Error reading {pdf_path}: {e}")

    averaged = average_field_metadata(all_metadata)
    with open(output_template_path, "w", encoding="utf-8") as f:
        json.dump(averaged, f, indent=2)
    print(f"✅ Template saved: {output_template_path}")


root_bank_dir = "banks"
field_def_dir = "fields"
output_dir = "templates"
os.makedirs(output_dir, exist_ok=True)

for bank_folder in os.listdir(root_bank_dir):
    bank_path = os.path.join(root_bank_dir, bank_folder)
    field_file = os.path.join(field_def_dir, f"{bank_folder}.txt")
    output_template = os.path.join(output_dir, f"template_{bank_folder}.json")

    if not os.path.isdir(bank_path) or not os.path.isfile(field_file):
        print(f"[!] Skipping {bank_folder}: Missing folder or field file")
        continue

    process_bank_folder(bank_path, field_file, output_template)
