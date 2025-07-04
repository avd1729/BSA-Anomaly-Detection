import fitz
import json
import os
import re

POSITION_THRESHOLD = 30  # pixels
FONT_SIZE_THRESHOLD = 1.5  # points

# ========== Bank Detection Utilities ==========

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
    label_match = re.search(r'RTGS/NEFT IFSC\s*:\s*([A-Z]{4}0[A-Z0-9]{6})', text_upper)
    if label_match:
        return label_match.group(1)

    generic_match = re.search(r'\b([A-Z]{4}0[A-Z0-9]{6})\b', text_upper)
    if generic_match:
        return generic_match.group(1)

    if "HDFC BANK" in text_upper:
        return "HDFC0000000"
    return None

def bank_from_ifsc_prefix(ifsc):
    if not ifsc:
        return "others"
    prefix = ifsc[:4]
    return {
        "HDFC": "hdfc", "SBIN": "sbi", "ICIC": "icici", "CNRB": "canara",
        "IBKL": "idbi", "IDIB": "indian", "UTIB": "axis", "BARB": "bob",
        "FDRL": "federal", "TMBL": "tmb", "UBIN": "union", "CIUB": "city_union",
        "IDFB": "idfc", "DLXB": "dhanlaxmi", "PUNB": "punjab_national"
    }.get(prefix, "others")

# ========== Field Extraction ==========

def extract_field_occurrences(pdf_path, field_list):
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
                    if re.sub(r'[^A-Za-z0-9]', '', field).lower() in re.sub(r'[^A-Za-z0-9]', '', line_text).lower():
                        for span in line["spans"]:
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
        return occurrences
    except Exception as e:
        print(f"[!] Failed to extract metadata: {e}")
        return {}

# ========== Template Comparison ==========

def compare_with_template(template, actual):
    anomalies = []
    for field, expected in template.items():
        if field not in actual:
            anomalies.append({
                "field": field,
                "type": "major",
                "reason": "Field missing"
            })
            continue

        act = actual[field]

        # Position range check
        xr, yr = expected["position_range"]["x"], expected["position_range"]["y"]
        wr, hr = expected["position_range"]["width"], expected["position_range"]["height"]

        if not (xr[0] - POSITION_THRESHOLD <= act["x"] <= xr[1] + POSITION_THRESHOLD and
                yr[0] - POSITION_THRESHOLD <= act["y"] <= yr[1] + POSITION_THRESHOLD):
            anomalies.append({
                "field": field,
                "type": "minor",
                "reason": f"Position out of expected range: ({act['x']}, {act['y']})"
            })

        # Font size check
        size_range = expected["font_size_range"]
        if not (size_range[0] <= act["size"] <= size_range[1]):
            anomalies.append({
                "field": field,
                "type": "minor",
                "reason": f"Font size mismatch: {act['size']} vs range {size_range}"
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
                style_issues.append("bold mismatch")
            if italic_mismatch:
                style_issues.append("italic mismatch")
            anomalies.append({
                "field": field,
                "type": "minor",
                "reason": "Style mismatch: " + ", ".join(style_issues)
            })

    return anomalies

# ========== Drawing Comparison Boxes ==========

def draw_expected_and_actual_boxes(pdf_path, template, actual_metadata, output_path):
    try:
        doc = fitz.open(pdf_path)
        page = doc[0]

        for field, expected in template.items():
            # 🔵 Expected box using range
            xr, yr = expected["position_range"]["x"], expected["position_range"]["y"]
            wr, hr = expected["position_range"]["width"], expected["position_range"]["height"]
            expected_rect = fitz.Rect(xr[0], yr[0], xr[1] + wr[1], yr[0] + hr[1])
            page.draw_rect(expected_rect, color=(0, 0, 1), width=1)
            page.insert_text((xr[0], yr[0] - 8), f"{field} (expected)", fontsize=6, color=(0, 0, 1))

            # 🔴 Actual box
            if field in actual_metadata:
                act = actual_metadata[field]
                actual_rect = fitz.Rect(act["x"], act["y"], act["x"] + act["width"], act["y"] + act["height"])
                page.draw_rect(actual_rect, color=(1, 0, 0), width=1)
                page.insert_text((act["x"], act["y"] - 8), f"{field} (actual)", fontsize=6, color=(1, 0, 0))

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        doc.save(output_path)
        print(f"🖍️  Annotated PDF saved: {output_path}")
    except Exception as e:
        print(f"[!] Failed to draw boxes: {e}")

# ========== Main Entry ==========

def validate_pdf(pdf_path, templates_dir="templates"):
    text = extract_first_page_text(pdf_path)
    ifsc = extract_first_ifsc(text)
    bank = bank_from_ifsc_prefix(ifsc)
    print(f"🏦 Detected bank: {bank} (IFSC: {ifsc})")

    template_path = os.path.join(templates_dir, f"template_{bank}.json")
    if not os.path.exists(template_path):
        print(f"[!] Template not found for {bank}")
        return

    with open(template_path, "r", encoding="utf-8") as f:
        template = json.load(f)

    actual_metadata = extract_field_occurrences(pdf_path, template.keys())
    anomalies = compare_with_template(template, actual_metadata)

    print(f"\n🔍 Anomalies in {os.path.basename(pdf_path)}:")
    if not anomalies:
        print("✅ No anomalies detected.")
    else:
        for a in anomalies:
            print(f" - [{a['type'].upper()}] {a['field']}: {a['reason']}")

    output_file = os.path.join("output", f"annotated_{os.path.basename(pdf_path)}")
    draw_expected_and_actual_boxes(pdf_path, template, actual_metadata, output_file)



# test_pdf = "banks/sbi/6c58de8a-221d-41bc-a3f6-961eeac7543c_june.pdf"
# validate_pdf(test_pdf)
