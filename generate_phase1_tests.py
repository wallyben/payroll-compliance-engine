from pathlib import Path
import csv
import random

OUTPUT_DIR = Path("phase1_test_files")
OUTPUT_DIR.mkdir(exist_ok=True)

def write_csv(name, rows):
    path = OUTPUT_DIR / name
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["employee_id", "gross_pay", "net_pay", "pay_date"])
        writer.writerows(rows)
    print(f"Created {path}")

# 1️⃣ Clean file
write_csv("01_clean.csv", [
    ["E001", 1000, 800, "31/01/2026"],
    ["E002", 1200, 950, "2026-01-31"],
    ["E003", 900, 700, 45500],
])

# 2️⃣ Broken date
write_csv("02_broken_date.csv", [
    ["E001", 1000, 800, "31/01/2026"],
    ["E002", 1200, 950, "32/01/2026"],
    ["E003", 900, 700, 45500],
])

# 3️⃣ Garbage date
write_csv("03_garbage_date.csv", [
    ["E001", 1000, 800, "31/01/2026"],
    ["E002", 1200, 950, "banana"],
    ["E003", 900, 700, 45500],
])

# 4️⃣ Non-numeric gross pay
write_csv("04_bad_gross.csv", [
    ["E001", 1000, 800, "31/01/2026"],
    ["E002", "abc", 950, "2026-01-31"],
    ["E003", 900, 700, 45500],
])

# 5️⃣ Empty file
write_csv("05_empty.csv", [])

# 6️⃣ Mixed chaos
write_csv("06_mixed.csv", [
    ["E001", 1000, 800, "31/01/2026"],
    ["E002", "", 950, "31/01/2026"],
    ["E003", 900, 700, "banana"],
    ["E004", "abc", 700, "2026-01-31"],
    ["E005", 1100, 850, "01-02-2026"],
])

# 7️⃣ Corrupt-style row
write_csv("07_corrupt_style.csv", [
    ["E001", 1000, 800, "31/01/2026"],
    ["", "", "", ""],
    ["E002", 1200, 950, "2026-01-31"],
])

# 8️⃣ Large file stress test
large_rows = []
for i in range(2000):
    large_rows.append([f"E{i}", random.randint(800,1500), random.randint(600,1200), "31/01/2026"])

write_csv("08_large.csv", large_rows)

print("\nAll Phase 1 test files generated.")
