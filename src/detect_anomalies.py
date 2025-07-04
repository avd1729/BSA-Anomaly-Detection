import fitz
import json
import os
import re

# ========== Configuration ==========
POSITION_THRESHOLD = 30  # pixels
FONT_SIZE_THRESHOLD = 1.5  # points

# ========== Bank Detection Utilities ==========

def extract_first_page_text(pdf_path):
    """Extract text from the first page of a PDF."""
    try:
        doc = fitz.open(pdf_path)
        if doc.page_count > 0:
            return doc[0].get_text()
    except Exception as e:
        print(f"[!] Could not read {pdf_path}: {e}")
    return ""

def extract_first_ifsc(text):
    """Extract IFSC code from text using multiple patterns."""
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
    """Map IFSC prefix to bank name."""
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

# ========== Field Extraction ==========

def extract_field_occurrences(pdf_path, field_list):
    """Extract field occurrences from a single PDF for anomaly detection."""
    occurrences = {}
    try:
        doc = fitz.open(pdf_path)
        page = doc[0]
        blocks = page.get_text("dict")["blocks"]

        for block in blocks:
            if "lines" not in block:
                continue
            for line in block["lines"]:
                line_text = " ".join(span["text"] for span in line["spans"])
                for field in field_list:
                    # Normalize text for comparison
                    norm_field = re.sub(r'[^A-Za-z0-9]', '', field).lower()
                    norm_line = re.sub(r'[^A-Za-z0-9]', '', line_text).lower()
                    
                    if norm_field in norm_line:
                        for span in line["spans"]:
                            if norm_field in re.sub(r'[^A-Za-z0-9]', '', span["text"]).lower():
                                occurrences[field] = {
                                    "x": span["bbox"][0],
                                    "y": span["bbox"][1],
                                    "width": span["bbox"][2] - span["bbox"][0],
                                    "height": span["bbox"][3] - span["bbox"][1],
                                    "font": span["font"],
                                    "size": span["size"],
                                    "bold": "Bold" in span["font"],
                                    "italic": "Italic" in span["font"]
                                }
                                break
                        break
        return occurrences
    except Exception as e:
        print(f"[!] Failed to extract metadata: {e}")
        return {}

# ========== Template Comparison ==========

def compare_with_template(template, actual):
    """Compare actual field positions with template to detect anomalies."""
    anomalies = []
    
    for field, expected in template.items():
        if field not in actual:
            anomalies.append({
                "field": field,
                "type": "major",
                "reason": "Field missing from document"
            })
            continue

        act = actual[field]

        # Position range check
        xr, yr = expected["position_range"]["x"], expected["position_range"]["y"]
        
        if not (xr[0] - POSITION_THRESHOLD <= act["x"] <= xr[1] + POSITION_THRESHOLD and
                yr[0] - POSITION_THRESHOLD <= act["y"] <= yr[1] + POSITION_THRESHOLD):
            anomalies.append({
                "field": field,
                "type": "minor",
                "reason": f"Position out of expected range: ({act['x']:.1f}, {act['y']:.1f}) vs expected ({xr[0]:.1f}-{xr[1]:.1f}, {yr[0]:.1f}-{yr[1]:.1f})"
            })

        # Font size check
        size_range = expected["font_size_range"]
        if not (size_range[0] <= act["size"] <= size_range[1]):
            anomalies.append({
                "field": field,
                "type": "minor",
                "reason": f"Font size mismatch: {act['size']:.1f} vs expected range [{size_range[0]:.1f}-{size_range[1]:.1f}]"
            })

        # Font/style check
        normalized_font = act["font"].lower().replace("-", "").replace("mt", "").strip()
        font_name_mismatch = normalized_font not in expected["fonts"]
        bold_mismatch = act["bold"] != expected["bold"]
        italic_mismatch = act["italic"] != expected["italic"]

        if font_name_mismatch or bold_mismatch or italic_mismatch:
            style_issues = []
            if font_name_mismatch:
                style_issues.append(f"font '{normalized_font}' not in expected {expected['fonts']}")
            if bold_mismatch:
                style_issues.append(f"bold: {act['bold']} vs expected: {expected['bold']}")
            if italic_mismatch:
                style_issues.append(f"italic: {act['italic']} vs expected: {expected['italic']}")
            
            anomalies.append({
                "field": field,
                "type": "minor",
                "reason": "Style mismatch: " + ", ".join(style_issues)
            })

    return anomalies

# ========== Visualization ==========

def draw_expected_and_actual_boxes(pdf_path, template, actual_metadata, output_path):
    """Draw bounding boxes on PDF to visualize expected vs actual positions."""
    try:
        doc = fitz.open(pdf_path)
        page = doc[0]

        for field, expected in template.items():
            # 🔵 Expected box using range
            xr, yr = expected["position_range"]["x"], expected["position_range"]["y"]
            wr, hr = expected["position_range"]["width"], expected["position_range"]["height"]
            
            # Draw expected range as a rectangle
            expected_rect = fitz.Rect(xr[0], yr[0], xr[1] + wr[1], yr[0] + hr[1])
            page.draw_rect(expected_rect, color=(0, 0, 1), width=1)  # Blue
            page.insert_text((xr[0], yr[0] - 8), f"{field} (expected)", fontsize=6, color=(0, 0, 1))

            # 🔴 Actual box (if found)
            if field in actual_metadata:
                act = actual_metadata[field]
                actual_rect = fitz.Rect(act["x"], act["y"], act["x"] + act["width"], act["y"] + act["height"])
                page.draw_rect(actual_rect, color=(1, 0, 0), width=1)  # Red
                page.insert_text((act["x"], act["y"] - 8), f"{field} (actual)", fontsize=6, color=(1, 0, 0))

        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        doc.save(output_path)
        doc.close()
        print(f"🖍️  Annotated PDF saved: {output_path}")
    except Exception as e:
        print(f"[!] Failed to draw boxes: {e}")

# ========== Main Validation Function ==========

def validate_pdf(pdf_path, templates_dir="templates", output_dir="output"):
    """Main function to validate a PDF against its template."""
    print(f"🔍 Validating: {os.path.basename(pdf_path)}")
    
    # Detect bank from PDF content
    text = extract_first_page_text(pdf_path)
    ifsc = extract_first_ifsc(text)
    bank = bank_from_ifsc_prefix(ifsc)
    print(f"🏦 Detected bank: {bank} (IFSC: {ifsc})")

    # Load corresponding template
    template_path = os.path.join(templates_dir, f"template_{bank}.json")
    if not os.path.exists(template_path):
        print(f"[!] Template not found: {template_path}")
        return None

    try:
        with open(template_path, "r", encoding="utf-8") as f:
            template = json.load(f)
        print(f"📋 Loaded template with {len(template)} fields")
    except Exception as e:
        print(f"[!] Failed to load template: {e}")
        return None

    # Extract field occurrences from PDF
    actual_metadata = extract_field_occurrences(pdf_path, template.keys())
    print(f"📊 Found {len(actual_metadata)} fields in PDF")

    # Compare with template
    anomalies = compare_with_template(template, actual_metadata)

    # Report results
    print(f"\n🔍 Anomaly Detection Results:")
    if not anomalies:
        print("✅ No anomalies detected - Document appears legitimate")
    else:
        print(f"⚠️  Found {len(anomalies)} anomalies:")
        major_count = sum(1 for a in anomalies if a['type'] == 'major')
        minor_count = sum(1 for a in anomalies if a['type'] == 'minor')
        
        print(f"   • Major anomalies: {major_count}")
        print(f"   • Minor anomalies: {minor_count}")
        
        for a in anomalies:
            icon = "🚨" if a['type'] == 'major' else "⚠️"
            print(f"   {icon} [{a['type'].upper()}] {a['field']}: {a['reason']}")

    # Create annotated PDF
    output_file = os.path.join(output_dir, f"annotated_{os.path.basename(pdf_path)}")
    draw_expected_and_actual_boxes(pdf_path, template, actual_metadata, output_file)

    return {
        "pdf_path": pdf_path,
        "bank": bank,
        "ifsc": ifsc,
        "anomalies": anomalies,
        "fields_found": len(actual_metadata),
        "total_fields": len(template),
        "annotated_pdf": output_file
    }


# ========== Main Execution ==========

def main():
    
    # 1. Validate a single PDF
    # validate_pdf("banks/hdfc/5f4f1a22-960c-4a94-af48-48866068a6a5_Acct Statement_XX2487_24112024.pdf")
    
    pass

if __name__ == "__main__":
    main()