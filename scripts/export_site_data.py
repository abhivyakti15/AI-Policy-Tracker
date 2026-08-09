import csv
import json
import os

ROOT = os.path.join(os.path.dirname(__file__), "..")
CSV_PATH = os.path.join(ROOT, "data", "ai_policy_india.csv")


def write_data_js(rows, out_path):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("const AI_POLICY_RECORDS =" + json.dumps(rows, indent=2, ensure_ascii=False) + ";\n")
    print(f"Wrote {out_path} with {len(rows)} records.")

def main():
    with open(CSV_PATH, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    output_paths = [os.path.join(ROOT, "site", "data.js")]
    docs_dir = os.path.join(ROOT, "docs")
    if os.path.isdir(docs_dir):
        output_paths.append(os.path.join(docs_dir, "data.js"))

    for out_path in output_paths:
        write_data_js(rows, out_path)

if __name__ == "__main__":
    main()