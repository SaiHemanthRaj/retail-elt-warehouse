# Live Snowflake verification — October 6, 2026

Executed in a personal trial account on a dedicated X-Small warehouse, using Python 3.12.13 and Snowpark 1.55.0. Existing course databases and warehouses were left untouched.

| Check | Initial run | Repeated call |
|---|---:|---:|
| Sales facts | 1,220 | 1,220 |
| Revenue cents | 7,821,134 | 7,821,134 |
| Customer versions | 66 | 66 |
| Raw sales versions | 1,255 | 1,255 |
| Committed batches | 2 | 2 |
| SQL quality gates | Six zero failures | Six zero failures |
| Cloud assertions | 10/10 true | 10/10 true |
| Input statuses | loaded, loaded, replayed | replayed, replayed, replayed |

Evidence: [initial report](../examples/snowflake_run_report.json), [repeated-call report](../examples/snowflake_replay_report.json), and [independent persisted-table checks](../examples/snowflake_table_checks.csv). All eleven independent checks passed.

Reports include UTC timestamps and SHA-256 fingerprints for the executed source and fixtures; those fingerprints were compared with the local files. The first query ID can be looked up by the account owner; it does not grant public access. Snowsight displayed 36 seconds for the initial call and 20 seconds for the repeated call. These observations are not a controlled performance benchmark.

## What the assertions demonstrate

Replay leaves results unchanged; a corrected order has quantity seven; late-arriving orders resolve to North and West customer history respectively. An unknown-product probe rolls back raw changes, facts, customer history, and batch registration. Equal-timestamp conflicting payloads are rejected. Duplicate customer-history versions are explicitly rejected and rolled back even though Snowflake primary keys are informational. Expected totals, customer-version counts, and all six SQL quality gates are checked.

The separate SQL query verifies stored tables after both calls, rather than relying only on the procedure's returned report.

## Scope and limits

This verifies the shared Python loader, SQL MERGE, dimensional history, and transaction behavior through Snowpark in a real Snowflake account. It does not verify the standalone password connector CLI, a continuous scheduler, Streams/Tasks, production RBAC, AWS integration, a production SLA, or a benchmark.

The dedicated warehouse uses 60-second auto-suspend and was confirmed SUSPENDED after verification. An explicit SUSPEND returned an invalid-state response because auto-suspend had already stopped it. The database, procedure, and two evidence reports remain available for the account owner to review.

The local pytest suite contains fifteen tests. Local adapter tests use DuckDB to check the session contract; they are not cloud tests. The live ten-assertion run was captured manually, not by an automated cloud CI suite.
