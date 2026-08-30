import csv

INPUT = "app/ml/train/dataset.csv"
OUTPUT = "app/ml/train/dataset_fixed.csv"

FRONT_COLS = ["id", "call_language", "scam_category", "trigger_phrase"]
BACK_COLS = ["scam_pattern", "demand_type", "demand_amount", "urgency_level", "threat_consequence", "tags"]
NEW_HEADER = FRONT_COLS + ["keywords_detected"] + BACK_COLS

fixed_rows = []
skipped = 0

with open(INPUT, encoding="utf-8-sig") as f:
    reader = csv.reader(f)
    header = next(reader)  # skip old header
    for i, row in enumerate(reader, start=2):
        if len(row) < len(FRONT_COLS) + len(BACK_COLS) + 1:
            skipped += 1
            print(f"⚠️ Row {i} too short, skipped: {row}")
            continue
        front = row[:4]
        back = row[-6:]
        middle = row[4:-6]                       # extra keyword fields
        keywords = ", ".join(m.strip() for m in middle if m.strip())
        fixed_rows.append(front + [keywords] + back)

with open(OUTPUT, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
    writer.writerow(NEW_HEADER)
    writer.writerows(fixed_rows)

print(f"✅ Done. {len(fixed_rows)} rows fixed, {skipped} skipped.")
print(f"📁 Output: {OUTPUT}")
