"""Transactional incremental loading, shared DuckDB/Snowflake modeling SQL."""

import argparse
import csv
import hashlib
import json
import logging
import os
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIELDS = [
    "order_id",
    "order_date",
    "customer_id",
    "product_id",
    "store_id",
    "quantity",
    "unit_price_cents",
    "updated_at",
]
LOG = logging.getLogger(__name__)


class Warehouse:
    def __init__(self, path=None, backend="duckdb"):
        self.backend = backend
        if backend == "duckdb":
            import duckdb

            path = str(path or os.getenv("WAREHOUSE_PATH", "artifacts/retail.duckdb"))
            if path != ":memory:":
                Path(path).parent.mkdir(parents=True, exist_ok=True)
            self.conn = duckdb.connect(path)
            self.placeholder = "?"
        elif backend == "snowflake":
            import snowflake.connector

            names = ["account", "user", "password", "warehouse", "database", "role"]
            settings = {n: os.getenv("SNOWFLAKE_" + n.upper()) for n in names}
            if not all(settings.values()):
                raise ValueError("Set all Snowflake environment variables in .env.example")
            self.conn = snowflake.connector.connect(**settings, autocommit=True)
            self.placeholder = "%s"
        else:
            raise ValueError("Unknown backend")
        self.run_sql("001_schema.sql")
        self.run_sql("002_models.sql")

    def execute(self, sql, params=()):
        if self.backend == "duckdb":
            return self.conn.execute(sql, params)
        return self.conn.cursor().execute(sql, params)

    def rows(self, sql, params=()):
        result = self.execute(sql, params)
        try:
            return result.fetchall()
        finally:
            if self.backend == "snowflake":
                result.close()

    def run_sql(self, name):
        # These source files contain no procedural blocks or semicolons in literals.
        for statement in (ROOT / "sql" / name).read_text().split(";"):
            if statement.strip():
                result = self.execute(statement)
                if self.backend == "snowflake":
                    result.close()

    def close(self):
        self.conn.close()

    def insert(self, table, rows, width):
        if rows:
            sql = f"INSERT INTO {table} VALUES (" + ",".join([self.placeholder] * width) + ")"
            if self.backend == "duckdb":
                self.conn.executemany(sql, rows)
            else:
                cur = self.conn.cursor()
                try:
                    cur.executemany(sql, rows)
                finally:
                    cur.close()

    def seed_dimensions(self):
        """Initialize once; fail rather than silently overwrite another seed."""
        if self.rows("SELECT COUNT(*) FROM marts.dim_product")[0][0]:
            return
        self.execute("BEGIN")
        try:
            for name, table in [
                ("products", "marts.dim_product"),
                ("stores", "marts.dim_store"),
                ("customers", "raw.customer_history"),
            ]:
                with (ROOT / "data" / f"{name}.csv").open(newline="") as f:
                    rows = [tuple(r.values()) for r in csv.DictReader(f)]
                self.insert(table, rows, len(rows[0]))
            self.execute("COMMIT")
        except Exception:
            self.execute("ROLLBACK")
            raise

    def load(self, source, customer_changes=None):
        source = Path(source)
        change_bytes = Path(customer_changes).read_bytes() if customer_changes else b""
        batch_hash = hashlib.sha256(source.read_bytes() + b"\0" + change_bytes).hexdigest()
        rows = read_sales(source)
        changes = []
        if customer_changes:
            with Path(customer_changes).open(newline="") as f:
                for r in csv.DictReader(f):
                    if not r["customer_id"] or not r["region"]:
                        raise ValueError("Empty customer attributes")
                    date.fromisoformat(r["valid_from"])
                    changes.append(tuple(r[k] for k in ["customer_id", "region", "valid_from"]))
        self.execute("BEGIN")
        try:
            if self.rows(
                "SELECT COUNT(*) FROM raw.batches WHERE batch_hash=" + self.placeholder,
                (batch_hash,),
            )[0][0]:
                self.execute("ROLLBACK")
                return {
                    "source": source.name,
                    "status": "replayed",
                    "rows": 0,
                    "batch_hash": batch_hash,
                }
            # Conflicting updates at identical timestamps are ambiguous; refuse them.
            for r in rows:
                old = self.rows(
                    "SELECT order_date,customer_id,product_id,store_id,quantity,unit_price_cents FROM raw.sales WHERE order_id="
                    + self.placeholder
                    + " AND updated_at="
                    + self.placeholder,
                    (r[0], r[7]),
                )
                if old and any(tuple(map(str, o)) != tuple(map(str, r[1:7])) for o in old):
                    raise ValueError("Conflicting order version: " + r[0])
            self.insert("raw.sales", [r + (batch_hash,) for r in rows], 9)
            self.insert("raw.customer_history", changes, 3)
            self.run_sql("003_merge.sql")
            quality = self.rows((ROOT / "sql/004_quality.sql").read_text())
            failures = {name: int(n) for name, n in quality if n}
            if failures:
                raise ValueError("Quality gate failed: " + json.dumps(failures))
            self.insert("raw.batches", [(batch_hash, source.name, len(rows))], 3)
            self.execute("COMMIT")
            LOG.info(
                "batch_committed source=%s rows=%s hash=%s", source.name, len(rows), batch_hash
            )
            return {
                "source": source.name,
                "status": "loaded",
                "rows": len(rows),
                "batch_hash": batch_hash,
            }
        except Exception:
            self.execute("ROLLBACK")
            LOG.error("batch_rolled_back source=%s", source.name)
            raise


def read_sales(path):
    rows = []
    versions = {}
    with Path(path).open(newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != FIELDS:
            raise ValueError("Unexpected sales schema")
        for line, r in enumerate(reader, 2):
            if any(not r.get(k) for k in FIELDS):
                raise ValueError(f"Missing field on line {line}")
            order_date = date.fromisoformat(r["order_date"])
            timestamp = datetime.fromisoformat(r["updated_at"])
            if timestamp.tzinfo is not None:
                raise ValueError("updated_at must be naive UTC")
            q = int(r["quantity"])
            p = int(r["unit_price_cents"])
            if q <= 0 or p < 0 or q > 1_000_000 or p > 1_000_000_000:
                raise ValueError("Invalid quantity or price")
            row = (
                r["order_id"],
                order_date,
                r["customer_id"],
                r["product_id"],
                r["store_id"],
                q,
                p,
                timestamp,
            )
            key = (row[0], timestamp)
            if key in versions and versions[key] != row:
                raise ValueError("Conflicting order versions in batch")
            versions[key] = row
            rows.append(row)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--backend",
        choices=["duckdb", "snowflake"],
        default=os.getenv("WAREHOUSE_BACKEND", "duckdb"),
    )
    parser.add_argument("--source", type=Path)
    parser.add_argument("--customer-changes", type=Path)
    parser.add_argument("--demo", action="store_true")
    args = parser.parse_args()
    if not args.demo and not args.source:
        parser.error("Use --demo or --source")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    db = Warehouse(backend=args.backend)
    try:
        db.seed_dimensions()
        batches = []
        if args.demo:
            batches.append(db.load(ROOT / "data/batch_01.csv"))
            batches.append(db.load(ROOT / "data/batch_02.csv", ROOT / "data/customer_changes.csv"))
            batches.append(db.load(ROOT / "data/batch_02.csv", ROOT / "data/customer_changes.csv"))
        else:
            batches.append(db.load(args.source, args.customer_changes))
        count, revenue = db.rows(
            "SELECT COUNT(*),COALESCE(SUM(revenue_cents),0) FROM marts.fact_sales"
        )[0]
        report = {
            "backend": args.backend,
            "batches": batches,
            "fact_rows": int(count),
            "revenue_cents": int(revenue),
            "quality": {k: int(n) for k, n in db.rows((ROOT / "sql/004_quality.sql").read_text())},
            "regional_sales": [
                dict(zip(["region", "orders", "revenue_cents", "rank"], r))
                for r in db.rows((ROOT / "sql/005_analytics.sql").read_text())
            ],
        }
        out = Path("artifacts")
        out.mkdir(exist_ok=True)
        (out / "run_report.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2))
    finally:
        db.close()


if __name__ == "__main__":
    main()
