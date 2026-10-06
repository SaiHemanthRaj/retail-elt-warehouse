"""Run the existing warehouse loader in a caller-rights Snowpark procedure."""

import csv
import hashlib
import json
from datetime import datetime, timezone

from .pipeline import FIELDS, ROOT, Warehouse


class Result:
    def __init__(self, rows):
        self.values = rows

    def fetchall(self):
        return self.values

    def close(self):
        pass


class SnowparkWarehouse(Warehouse):
    def __init__(self, session):
        self.session = session
        self.backend = "snowflake"
        self.placeholder = "?"
        database = session.get_current_database()
        if not database or not database.strip('"').upper().startswith("PORTFOLIO_"):
            raise ValueError("Use a dedicated PORTFOLIO_ sandbox database")
        self.run_sql("001_schema.sql")
        self.run_sql("002_models.sql")

    def execute(self, sql, params=()):
        return Result(self.session.sql(sql, params=list(params)).collect())

    def insert(self, table, rows, width):
        allowed = {
            "raw.sales",
            "raw.batches",
            "raw.customer_history",
            "marts.dim_product",
            "marts.dim_store",
        }
        if table not in allowed:
            raise ValueError("Unexpected insertion target")
        for offset in range(0, len(rows), 100):
            chunk = rows[offset : offset + 100]
            if any(len(row) != width for row in chunk):
                raise ValueError("Row width does not match insert contract")
            template = "(" + ",".join(["?"] * width) + ")"
            self.execute(
                f"INSERT INTO {table} VALUES " + ",".join([template] * len(chunk)),
                [value for row in chunk for value in row],
            )

    def close(self):
        # The caller owns the active Snowpark session.
        pass


def snapshot(db):
    return {
        "facts": [tuple(r) for r in db.rows("SELECT * FROM marts.fact_sales ORDER BY order_id")],
        "raw_sales": int(db.rows("SELECT COUNT(*) FROM raw.sales")[0][0]),
        "customer_versions": int(db.rows("SELECT COUNT(*) FROM raw.customer_history")[0][0]),
        "batches": int(db.rows("SELECT COUNT(*) FROM raw.batches")[0][0]),
    }


def write_row(path, row):
    with path.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerow(row)


def run_demo(session):
    db = SnowparkWarehouse(session)
    db.seed_dimensions()
    batches = [
        db.load(ROOT / "data/batch_01.csv"),
        db.load(ROOT / "data/batch_02.csv", ROOT / "data/customer_changes.csv"),
    ]
    before = snapshot(db)
    replay = db.load(ROOT / "data/batch_02.csv", ROOT / "data/customer_changes.csv")
    checks = {"replay_unchanged": replay["status"] == "replayed" and snapshot(db) == before}
    checks["corrected_order_quantity"] = (
        db.rows("SELECT quantity FROM marts.fact_sales WHERE order_id='O00001'")[0][0] == 7
    )
    for order, region in [("L00001", "North"), ("L00002", "West")]:
        checks["historical_region_" + order] = (
            db.rows(
                "SELECT region FROM marts.fact_sales f JOIN marts.dim_customer c USING(customer_key) WHERE order_id=?",
                [order],
            )[0][0]
            == region
        )

    with (ROOT / "data/batch_01.csv").open() as file:
        original = next(csv.DictReader(file))
    quality_row = dict(original, order_id="ROLLBACK_PROBE", product_id="UNKNOWN_PRODUCT")
    quality_path = ROOT / "data/rollback_probe.csv"
    write_row(quality_path, quality_row)
    changes_path = ROOT / "data/rollback_changes.csv"
    changes_path.write_text("customer_id,region,valid_from\nC001,Probe,2026-10-01\n")
    try:
        db.load(quality_path, changes_path)
    except ValueError as error:
        checks["quality_failure_rolled_back"] = (
            "Quality gate" in str(error) and snapshot(db) == before
        )
    else:
        checks["quality_failure_rolled_back"] = False

    conflict_path = ROOT / "data/conflict_probe.csv"
    write_row(conflict_path, dict(original, quantity="99"))
    try:
        db.load(conflict_path)
    except ValueError as error:
        checks["conflict_rejected"] = "Conflicting" in str(error) and snapshot(db) == before
    else:
        checks["conflict_rejected"] = False

    duplicate_path = ROOT / "data/duplicate_probe.csv"
    write_row(duplicate_path, dict(original, order_id="DUPLICATE_PROBE"))
    changes_path.write_text("customer_id,region,valid_from\nC001,Probe,2026-09-01\n")
    try:
        db.load(duplicate_path, changes_path)
    except Exception as error:
        checks["duplicate_history_rolled_back"] = (
            "Duplicate customer history" in str(error) or "Duplicate key" in str(error)
        ) and snapshot(db) == before
    else:
        checks["duplicate_history_rolled_back"] = False

    count, revenue = db.rows("SELECT COUNT(*), SUM(revenue_cents) FROM marts.fact_sales")[0]
    quality = {name: int(n) for name, n in db.rows((ROOT / "sql/004_quality.sql").read_text())}
    checks["expected_totals"] = (int(count), int(revenue)) == (1220, 7821134)
    checks["customer_versions"] = before["customer_versions"] == 66
    checks["all_quality_checks_zero"] = all(n == 0 for n in quality.values())
    if not all(checks.values()):
        raise ValueError("Cloud assertions failed: " + json.dumps(checks))
    return {
        "backend": "snowflake-snowpark",
        "verified_at_utc": datetime.now(timezone.utc).isoformat(),
        "fact_rows": int(count),
        "revenue_cents": int(revenue),
        "raw_sales_rows": before["raw_sales"],
        "customer_versions": before["customer_versions"],
        "committed_batches": before["batches"],
        "batches": batches + [replay],
        "quality": quality,
        "assertions": checks,
        "source_hashes": {
            path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(ROOT.rglob("*"))
            if path.is_file()
            and path.suffix in {".py", ".csv", ".sql"}
            and "probe" not in path.name
            and "rollback" not in path.name
        },
    }
