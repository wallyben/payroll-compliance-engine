import csv
from pathlib import Path

def test_rule_inventory_integrity():
    inventory_path = Path("docs/rule_inventory_matrix.csv")
    assert inventory_path.exists(), "Rule inventory matrix missing."

    rule_ids = set()
    with inventory_path.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            rid = row["rule_id"]
            assert rid not in rule_ids, f"Duplicate rule_id in inventory: {rid}"
            rule_ids.add(rid)

    assert len(rule_ids) > 0, "Inventory must contain rules."
