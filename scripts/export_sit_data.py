import csv
import json
import os

ROOT = os.path.join(os.path.dirname(__file__), "..")
CSV_PATH = os.path.join(ROOT, "data", "ai_policy_india.csv")
OUT_PATH = os.path.join(ROOT, "site", "data.js")

def main():
    with open(CSV_PATH, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write("const AI_POLICY_RECORDS =" + json.dumps(rows, indent=2, ensure_ascii=False) + ";\n")
    print(f"Wrote {OUT_PATH} with {len(rows)} records.")

if __name__ == "__main__":
    main()