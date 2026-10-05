# Optional Snowflake execution: not cloud-verified

Prerequisites: your own account, an existing **dedicated empty sandbox database**, a small existing
warehouse, and a role with USAGE on the database/warehouse and CREATE SCHEMA on the database.
The loader creates fixed `RAW`, `STAGING`, and `MARTS` objects and replaces views in those schemas.
Never point it at an employer database. It does not create an account, database, role, or warehouse.

Install the optional connector in the same environment:

```bash
python -m pip install -r requirements-snowflake.txt
```

Export the six `SNOWFLAKE_*` variables in `.env.example` securely. Do not paste secrets into a commit,
README, issue, or terminal screenshot. Password authentication may not work for accounts whose policy
requires stronger authentication; key-pair/OAuth support is a future improvement.

```bash
python -m warehouse.pipeline --backend snowflake --demo
```

The same SQL scripts and quality checks are used. Successful execution must produce 1,220 facts,
7,821,134 revenue cents, and six zero quality failures. Capture a sanitized run report before labeling
this path verified. Snowflake primary-key constraints are informational, so the explicit duplicate quality
check remains necessary. Keep date formatting as YYYY-MM-DD if changing session settings, because
customer surrogate keys use a formatted date.

Raw loads, dimension changes, fact MERGE, and batch registration run in one DML transaction. DDL initialization
runs before loading. No stream offsets are involved. A future stream consumer should consume changes and
commit downstream writes transactionally; see [Snowflake streams](https://docs.snowflake.com/en/user-guide/streams-intro).

Costs: a real warehouse can incur compute charges. Use your own auto-suspend setting and inspect activity.
This project has no automatic resource teardown and has not measured cloud cost or runtime.
