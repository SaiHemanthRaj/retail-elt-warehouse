# Run the warehouse in Snowflake

The Snowpark path was executed in a personal trial account on October 6, 2026. It runs the shared Python loader and SQL through a caller-owned Snowpark session. See [captured evidence](cloud-verification.md). The separate password connector CLI remains unverified.

## Dedicated sandbox

Use a fresh database whose name begins with `PORTFOLIO_`. The adapter checks that prefix before DDL; it is not a substitute for selecting the correct database. The loader creates fixed RAW, STAGING, and MARTS objects and replaces views. Never use an employer database.

Example setup using an existing authorized role:

```sql
USE ROLE SYSADMIN;
CREATE WAREHOUSE PORTFOLIO_RETAIL_WH
  WAREHOUSE_SIZE='XSMALL' AUTO_SUSPEND=60 AUTO_RESUME=TRUE
  INITIALLY_SUSPENDED=TRUE STATEMENT_TIMEOUT_IN_SECONDS=180;
CREATE DATABASE PORTFOLIO_RETAIL_DEMO;
USE WAREHOUSE PORTFOLIO_RETAIL_WH;
USE DATABASE PORTFOLIO_RETAIL_DEMO;
USE SCHEMA PUBLIC;
```

Choose fresh names: CREATE intentionally fails if those objects already exist. No new credentials or security grants are required by the procedure.

## Build and execute

From the repository root:

```bash
python scripts/build_snowpark_demo.py --database PORTFOLIO_RETAIL_DEMO
```

Open `artifacts/snowpark_demo.sql` in a new Snowsight SQL file, select your sandbox warehouse and existing role, then run all statements. The script packages the original synthetic fixtures and loader into a deterministic ZIP inside a caller-rights Python 3.12 procedure, using `snowflake-snowpark-python==1.55.0`. It contains no credentials and requires no external network integration. Account package policies may require an administrator's approval; do not bypass them.

The initial run should return 1,220 facts, 7,821,134 revenue cents, 66 customer versions, six zero quality failures, and ten true assertions. Probes cover replay, corrections, late customer history, conflicting versions, and transaction rollback. The report is persisted in `marts.run_evidence`.

```sql
CALL PUBLIC.RUN_RETAIL_DEMO();
```

A repeated call should report all three fixture inputs as replayed, retain two committed batches, and produce the same totals. Run [006_cloud_verification.sql](../sql/006_cloud_verification.sql) separately to verify persisted tables. Download the CSV and remove account or session metadata before publishing evidence.

Suspend only the warehouse you created when finished:

```sql
ALTER WAREHOUSE PORTFOLIO_RETAIL_WH SUSPEND;
```

Compute and storage can consume trial credits or incur charges. The example uses an X-Small warehouse with 60-second auto-suspend. It does not deploy a continuous scheduler. Database, procedure, and evidence remain for review; the account owner controls retention. No cost or performance benchmark is claimed.

## Separate external connector: unverified

```bash
python -m pip install -r requirements-snowflake.txt
python -m warehouse.pipeline --backend snowflake --demo
```

Securely export the six `SNOWFLAKE_*` variables listed in `.env.example` and select an existing dedicated empty sandbox. Never commit secrets. Password authentication may be incompatible with account policy; key-pair/OAuth support is not implemented. Do not weaken authentication to run this path. It is not exercised in CI.

DDL initialization precedes the DML transaction. Raw loads, dimensions, fact MERGE, and batch registration commit together. Snowflake primary keys are informational, so explicit duplicate customer-history and fact checks enforce those invariants. Date formatting is set to YYYY-MM-DD. Streams, Tasks, and production RBAC deployment are future work.
