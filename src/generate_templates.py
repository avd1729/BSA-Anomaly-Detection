import os
import fitz  # PyMuPDF
import json
import re
import statistics

# ========== Configuration ==========
MARGIN = 15  # Pixels around median for bounding box

# ========== Utility Functions ==========

def load_field_list(field_txt_path):
    """Load field list from text file."""
    with open(field_txt_path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]

def normalize_font(font):
    """Normalize font name for comparison."""
    return font.lower().replace("-", "").replace("mt", "").strip()

# ========== Field Extraction ==========

def find_field_occurrences(pdf, field_keywords):
    """Find all occurrences of field keywords in PDF."""
    field_metadata = {}

    for page_num in range(len(pdf)):
        page = pdf[page_num]
        blocks = page.get_text("dict")["blocks"]

        for block in blocks:
            if "lines" not in block:
                continue

            for line in block["lines"]:
                spans = line["spans"]
                line_text = " ".join(span["text"] for span in spans)
                
                for keyword in field_keywords:
                    norm_keyword = re.sub(r'\W+', '', keyword).lower()
                    norm_line = re.sub(r'\W+', '', line_text).lower()

                    if norm_keyword in norm_line:
                        for span in spans:
                            if norm_keyword in re.sub(r'\W+', '', span["text"]).lower():
                                field_metadata.setdefault(keyword, []).append({
                                    "page": page_num,
                                    "x": span["bbox"][0],
                                    "y": span["bbox"][1],
                                    "width": span["bbox"][2] - span["bbox"][0],
                                    "height": span["bbox"][3] - span["bbox"][1],
                                    "font": span["font"],
                                    "size": span["size"],
                                    "bold": "Bold" in span["font"],
                                    "italic": "Italic" in span["font"],
                                })
                                break
    return field_metadata

# ========== Template Building ==========

def build_position_range_metadata(field_meta):
    """Build template with position ranges from field metadata."""
    template = {}

    for field, spans in field_meta.items():
        if not spans:
            continue

        x_vals = [s["x"] for s in spans]
        y_vals = [s["y"] for s in spans]
        w_vals = [s["width"] for s in spans]
        h_vals = [s["height"] for s in spans]
        sizes = [s["size"] for s in spans]

        try:
            x_med = statistics.median(x_vals)
            y_med = statistics.median(y_vals)
            w_med = statistics.median(w_vals)
            h_med = statistics.median(h_vals)
            size_med = statistics.median(sizes)
        except statistics.StatisticsError:
            continue

        fonts = list(set(normalize_font(s["font"]) for s in spans))
        bold = any(s["bold"] for s in spans)
        italic = any(s["italic"] for s in spans)
        pages = sorted(list(set(s["page"] for s in spans)))

        template[field] = {
            "position_range": {
                "x": [x_med - MARGIN, x_med + MARGIN],
                "y": [y_med - MARGIN, y_med + MARGIN],
                "width": [w_med - 5, w_med + 5],
                "height": [h_med - 3, h_med + 3]
            },
            "font_size_range": [size_med - 0.5, size_med + 0.5],
            "fonts": fonts,
            "bold": bold,
            "italic": italic,
            "pages": pages
        }

    return template

# ========== Template Processing ==========

def process_bank_folder(bank_folder_path, fields_txt_path, output_template_path):
    """Process all PDFs in a bank folder to generate template."""
    field_list = load_field_list(fields_txt_path)
    all_metadata = {}

    print(f"🏦 Processing bank folder: {os.path.basename(bank_folder_path)}")
    print(f"📋 Loading fields from: {fields_txt_path}")

    for filename in os.listdir(bank_folder_path):
        if filename.lower().endswith(".pdf"):
            pdf_path = os.path.join(bank_folder_path, filename)
            print(f"📄 Processing {filename}...")

            try:
                pdf = fitz.open(pdf_path)
                pdf_meta = find_field_occurrences(pdf, field_list)
                
                # Accumulate metadata from all PDFs
                for field, occurrences in pdf_meta.items():
                    all_metadata.setdefault(field, []).extend(occurrences)
                    
                pdf.close()
            except Exception as e:
                print(f"[!] Error reading {pdf_path}: {e}")

    if not all_metadata:
        print(f"[!] No field metadata found for {bank_folder_path}")
        return

    # Build template from accumulated metadata
    final_template = build_position_range_metadata(all_metadata)

    # Save template
    os.makedirs(os.path.dirname(output_template_path), exist_ok=True)
    with open(output_template_path, "w", encoding="utf-8") as f:
        json.dump(final_template, f, indent=2)
    
    print(f"✅ Template saved: {output_template_path}")
    print(f"📊 Template contains {len(final_template)} fields")

def generate_all_templates(root_bank_dir="banks", field_def_dir="fields", output_dir="templates"):
    """Generate templates for all banks."""
    print(f"🚀 Starting template generation...")
    print(f"📂 Bank folders: {root_bank_dir}")
    print(f"📝 Field definitions: {field_def_dir}")
    print(f"💾 Output directory: {output_dir}")
    
    os.makedirs(output_dir, exist_ok=True)

    processed_count = 0
    for bank_folder in os.listdir(root_bank_dir):
        bank_path = os.path.join(root_bank_dir, bank_folder)
        field_file = os.path.join(field_def_dir, f"{bank_folder}.txt")
        output_template = os.path.join(output_dir, f"template_{bank_folder}.json")

        if not os.path.isdir(bank_path):
            print(f"[!] Skipping {bank_folder}: Not a directory")
            continue
            
        if not os.path.isfile(field_file):
            print(f"[!] Skipping {bank_folder}: Field file not found ({field_file})")
            continue

        print(f"\n{'='*50}")
        process_bank_folder(bank_path, field_file, output_template)
        processed_count += 1

    print(f"\n🎉 Template generation complete!")
    print(f"📊 Processed {processed_count} banks")

# ========== Main Execution ==========

def main():
    
    # 1. Generate templates for all banks
    # generate_all_templates()
    
    # 2. Generate template for a specific bank
    # process_bank_folder("banks/sbi", "fields/sbi.txt", "templates/template_sbi.json")
    
    # 3. Custom configuration
    # generate_all_templates(
    #     root_bank_dir="my_banks",
    #     field_def_dir="my_fields", 
    #     output_dir="my_templates"
    # )
    
    pass

if __name__ == "__main__":
    main()