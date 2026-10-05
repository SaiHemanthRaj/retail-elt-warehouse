from pathlib import Path
import csv
import random

ROOT = Path(__file__).resolve().parents[1]


def csv_write(name, fields, rows):
    p = ROOT / "data" / name
    p.parent.mkdir(exist_ok=True)
    with p.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(fields)
        w.writerows(rows)


rng = random.Random(41)
regions = ["North", "South", "East"]
csv_write(
    "customers.csv",
    ["customer_id", "region", "valid_from"],
    [(f"C{i:03}", regions[(i - 1) % 3], "2026-09-01") for i in range(1, 61)],
)
csv_write(
    "products.csv",
    ["product_id", "category"],
    [(f"P{i:03}", ["Grocery", "Home", "Personal"][i % 3]) for i in range(1, 16)],
)
csv_write(
    "stores.csv", ["store_id", "store_name"], [(f"S{i:02}", f"Store {i}") for i in range(1, 5)]
)
fields = [
    "order_id",
    "order_date",
    "customer_id",
    "product_id",
    "store_id",
    "quantity",
    "unit_price_cents",
    "updated_at",
]
rows = []
for i in range(1, 1201):
    rows.append(
        [
            f"O{i:05}",
            f"2026-09-{1 + (i % 20):02}",
            f"C{1 + i % 60:03}",
            f"P{1 + i % 15:03}",
            f"S{1 + i % 4:02}",
            rng.randint(1, 5),
            rng.choice([549, 999, 1999, 4999]),
            "2026-09-21T00:00:00",
        ]
    )
csv_write("batch_01.csv", fields, rows)
updates = [r.copy() for r in rows[:30]]
for r in updates:
    r[5] = 7
    r[7] = "2026-09-22T00:00:00"
late = [
    [
        f"L{i:05}",
        "2026-09-05" if i % 2 else "2026-09-15",
        "C001",
        "P001",
        "S01",
        1,
        1999,
        "2026-09-22T00:00:00",
    ]
    for i in range(1, 21)
]
stale = [r.copy() for r in rows[:5]]
for r in stale:
    r[5] = 1
    r[7] = "2026-09-20T00:00:00"
csv_write("batch_02.csv", fields, updates + late + stale)
csv_write(
    "customer_changes.csv",
    ["customer_id", "region", "valid_from"],
    [(f"C{i:03}", "West", "2026-09-10") for i in range(1, 7)],
)
