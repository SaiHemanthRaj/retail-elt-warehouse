"""Local adapter contract; real cloud evidence is recorded separately."""

import duckdb
import pytest

from warehouse.pipeline import ROOT
from warehouse.snowpark import SnowparkWarehouse, run_demo


class LocalSession:
    def __init__(self, database="PORTFOLIO_ADAPTER_TEST"):
        self.database = database
        self.connection = duckdb.connect(":memory:")

    def get_current_database(self):
        return self.database

    def sql(self, sql, params):
        connection = self.connection

        class Frame:
            def collect(self):
                return connection.execute(sql, params).fetchall()

        return Frame()


def test_adapter_runs_loader_with_chunked_inserts_replay_and_rollback():
    session = LocalSession()
    try:
        report = run_demo(session)
        assert report["fact_rows"] == 1220
        assert report["revenue_cents"] == 7821134
        assert all(report["assertions"].values())
        assert report["committed_batches"] == 2
    finally:
        session.connection.close()
        for name in [
            "rollback_probe.csv",
            "rollback_changes.csv",
            "conflict_probe.csv",
            "duplicate_probe.csv",
        ]:
            (ROOT / "data" / name).unlink(missing_ok=True)


def test_adapter_refuses_a_non_portfolio_database_before_any_ddl():
    session = LocalSession("OTHER_DATABASE")
    try:
        with pytest.raises(ValueError, match="dedicated"):
            SnowparkWarehouse(session)
        assert session.connection.execute("SHOW TABLES").fetchall() == []
    finally:
        session.connection.close()
