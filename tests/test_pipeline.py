import csv
import pytest
from warehouse.pipeline import Warehouse, ROOT, FIELDS


@pytest.fixture
def db(tmp_path):
    w = Warehouse(tmp_path / "test.duckdb")
    w.seed_dimensions()
    yield w
    w.close()


def mutate(tmp_path, **changes):
    with (ROOT / "data/batch_01.csv").open() as f:
        row = next(csv.DictReader(f))
    row.update(changes)
    p = tmp_path / "input.csv"
    with p.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerow(row)
    return p


def test_incremental_replay_and_stale_updates(db):
    assert db.load(ROOT / "data/batch_01.csv")["status"] == "loaded"
    assert (
        db.load(ROOT / "data/batch_02.csv", ROOT / "data/customer_changes.csv")["status"]
        == "loaded"
    )
    before = db.rows("SELECT * FROM marts.fact_sales ORDER BY order_id")
    assert len(before) == 1220
    assert (
        db.load(ROOT / "data/batch_02.csv", ROOT / "data/customer_changes.csv")["status"]
        == "replayed"
    )
    assert db.rows("SELECT * FROM marts.fact_sales ORDER BY order_id") == before
    assert db.rows("SELECT quantity FROM marts.fact_sales WHERE order_id='O00001'")[0][0] == 7


def test_scd2_late_arrivals_have_historical_region(db):
    db.load(ROOT / "data/batch_01.csv")
    db.load(ROOT / "data/batch_02.csv", ROOT / "data/customer_changes.csv")
    assert (
        db.rows(
            "SELECT region FROM marts.fact_sales f JOIN marts.dim_customer c USING(customer_key) WHERE order_id='L00001'"
        )[0][0]
        == "North"
    )
    assert (
        db.rows(
            "SELECT region FROM marts.fact_sales f JOIN marts.dim_customer c USING(customer_key) WHERE order_id='L00002'"
        )[0][0]
        == "West"
    )
    assert db.rows("SELECT COUNT(*) FROM marts.dim_customer")[0][0] == 66


@pytest.mark.parametrize(
    "changes",
    [{"quantity": "0"}, {"unit_price_cents": "-1"}, {"order_date": "bad"}, {"customer_id": ""}],
)
def test_bad_inputs_leave_no_state(db, tmp_path, changes):
    with pytest.raises(ValueError):
        db.load(mutate(tmp_path, **changes))
    assert db.rows("SELECT COUNT(*) FROM raw.sales")[0][0] == 0
    assert db.rows("SELECT COUNT(*) FROM raw.batches")[0][0] == 0


@pytest.mark.parametrize(
    "changes", [{"customer_id": "unknown"}, {"product_id": "unknown"}, {"store_id": "unknown"}]
)
def test_quality_failure_rolls_back_fact_and_raw(db, tmp_path, changes):
    with pytest.raises(ValueError, match="Quality gate"):
        db.load(mutate(tmp_path, **changes))
    assert db.rows("SELECT COUNT(*) FROM raw.sales")[0][0] == 0
    assert db.rows("SELECT COUNT(*) FROM marts.fact_sales")[0][0] == 0
    assert db.rows("SELECT COUNT(*) FROM raw.batches")[0][0] == 0


def test_conflicting_version_rejected(db, tmp_path):
    db.load(ROOT / "data/batch_01.csv")
    with pytest.raises(ValueError, match="Conflicting"):
        db.load(mutate(tmp_path, quantity="99"))
    assert db.rows("SELECT COUNT(*) FROM raw.batches")[0][0] == 1


def test_reconciliation_is_zero(db):
    db.load(ROOT / "data/batch_01.csv")
    db.load(ROOT / "data/batch_02.csv", ROOT / "data/customer_changes.csv")
    assert all(n == 0 for _, n in db.rows((ROOT / "sql/004_quality.sql").read_text()))


def test_dimension_change_failure_is_atomic(db, tmp_path):
    db.load(ROOT / "data/batch_01.csv")
    changes = tmp_path / "customers.csv"
    changes.write_text("customer_id,region,valid_from\nC001,West,2026-09-01\n")
    with pytest.raises(Exception):
        db.load(ROOT / "data/batch_02.csv", changes)
    assert db.rows("SELECT COUNT(*) FROM raw.customer_history")[0][0] == 60
    assert db.rows("SELECT COUNT(*) FROM raw.sales")[0][0] == 1200


def test_duplicate_customer_history_is_rejected_without_enforced_primary_key(db, tmp_path):
    # Snowflake standard tables expose PK metadata but do not enforce it.
    db.execute("CREATE OR REPLACE TABLE raw.customer_history AS SELECT * FROM raw.customer_history")
    db.load(ROOT / "data/batch_01.csv")
    changes = tmp_path / "duplicate_customers.csv"
    changes.write_text("customer_id,region,valid_from\nC001,West,2026-09-01\n")
    with pytest.raises(ValueError, match="Duplicate customer history"):
        db.load(ROOT / "data/batch_02.csv", changes)
    assert db.rows("SELECT COUNT(*) FROM raw.customer_history")[0][0] == 60
    assert db.rows("SELECT COUNT(*) FROM raw.sales")[0][0] == 1200
    assert db.rows("SELECT COUNT(*) FROM raw.batches")[0][0] == 1
