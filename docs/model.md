# Model contract

```mermaid
erDiagram
 DIM_CUSTOMER ||--o{ FACT_SALES : customer_key
 DIM_DATE ||--o{ FACT_SALES : date_key
 DIM_PRODUCT ||--o{ FACT_SALES : product_id
 DIM_STORE ||--o{ FACT_SALES : store_id
 DIM_CUSTOMER {
   string customer_key PK
   string customer_id
   string region
   date valid_from
   date valid_to
 }
 FACT_SALES {
   string order_id PK
   date date_key FK
   string customer_key FK
   string product_id FK
   string store_id FK
   int quantity
   bigint revenue_cents
 }
```

Foreign-key consistency is enforced by the data quality gate rather than engine-specific foreign-key DDL.
The customer key is a deterministic hash of the natural key and effective date. MD5 is used as a compact
non-security identifier; it is not used for authentication. Input integrity uses SHA-256.

The dimension uses LEAD to create nonoverlapping intervals. The fact MERGE remaps customer keys when
history changes, so late customer effective dates can revise historical assignments. This is a deliberate
restatement policy, not an immutable financial ledger.

The source timestamp governs correction order, while order_date governs historical customer lookup.
Those are different concepts. Five deliberately stale source versions cannot overwrite newer quantities.

Only exact batch replay is skipped. A differently formatted file can be loaded as a new batch, but latest
version selection and fact MERGE prevent double-counting. Raw ingestion history can retain repeated versions.
