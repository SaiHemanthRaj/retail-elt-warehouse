"""Package vetted project code and synthetic fixtures as a caller-rights procedure."""

import argparse
import base64
import io
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build(database):
    if not re.fullmatch(r"PORTFOLIO_[A-Z0-9_]+", database):
        raise ValueError("Use an uppercase PORTFOLIO_ sandbox identifier")
    files = sorted(
        list((ROOT / "warehouse").glob("*.py"))
        + list((ROOT / "sql").glob("*.sql"))
        + [
            ROOT / "data" / name
            for name in [
                "batch_01.csv",
                "batch_02.csv",
                "customers.csv",
                "customer_changes.csv",
                "products.csv",
                "stores.csv",
            ]
        ]
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            info = zipfile.ZipInfo(
                path.relative_to(ROOT).as_posix(), date_time=(2020, 1, 1, 0, 0, 0)
            )
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())
    payload = base64.b64encode(buffer.getvalue()).decode()
    return f"""-- Original synthetic data and project code; no credentials or external access.
-- Run only in your dedicated, empty PORTFOLIO_ sandbox. See docs/snowflake.md.
USE DATABASE {database};
USE SCHEMA PUBLIC;
ALTER SESSION SET DATE_OUTPUT_FORMAT='YYYY-MM-DD', TIMESTAMP_TYPE_MAPPING='TIMESTAMP_NTZ', ERROR_ON_NONDETERMINISTIC_MERGE=TRUE;
CREATE OR REPLACE PROCEDURE {database}.PUBLIC.RUN_RETAIL_DEMO()
RETURNS VARIANT
LANGUAGE PYTHON
RUNTIME_VERSION='3.12'
PACKAGES=('snowflake-snowpark-python==1.55.0')
HANDLER='run'
EXECUTE AS CALLER
AS $$
import base64
import io
import sys
import tempfile
import zipfile
from pathlib import Path

PAYLOAD = '{payload}'

def run(session):
    with tempfile.TemporaryDirectory() as directory:
        with zipfile.ZipFile(io.BytesIO(base64.b64decode(PAYLOAD))) as archive:
            for name in archive.namelist():
                if name.startswith('/') or '..' in Path(name).parts:
                    raise ValueError('Unsafe packaged path')
            archive.extractall(directory)
        sys.path.insert(0, directory)
        try:
            for name in ['warehouse.snowpark', 'warehouse.pipeline', 'warehouse']:
                sys.modules.pop(name, None)
            from warehouse.snowpark import run_demo
            report = run_demo(session)
            import snowflake.snowpark
            report['snowpark_version'] = snowflake.snowpark.__version__
            report['python_version'] = sys.version.split()[0]
            session.sql('CREATE TABLE IF NOT EXISTS marts.run_evidence (verified_at TIMESTAMP_NTZ, report VARIANT)').collect()
            session.sql('INSERT INTO marts.run_evidence SELECT CURRENT_TIMESTAMP(), PARSE_JSON(?)', params=[__import__('json').dumps(report)]).collect()
            return report
        finally:
            for name in ['warehouse.snowpark', 'warehouse.pipeline', 'warehouse']:
                sys.modules.pop(name, None)
            sys.path.remove(directory)
$$;
CALL {database}.PUBLIC.RUN_RETAIL_DEMO();
"""


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/snowpark_demo.sql")
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(build(args.database))
    print(args.output)
