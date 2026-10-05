CREATE OR REPLACE VIEW staging.sales AS
SELECT order_id, order_date, customer_id, product_id, store_id, quantity, unit_price_cents, updated_at
FROM raw.sales
QUALIFY ROW_NUMBER() OVER (PARTITION BY order_id ORDER BY updated_at DESC, batch_hash DESC)=1;

CREATE OR REPLACE VIEW marts.dim_customer AS
SELECT MD5(customer_id || '|' || CAST(valid_from AS VARCHAR)) AS customer_key,
 customer_id, region, valid_from,
 LEAD(valid_from, 1, CAST('9999-12-31' AS DATE)) OVER (PARTITION BY customer_id ORDER BY valid_from) AS valid_to
FROM raw.customer_history;

CREATE OR REPLACE VIEW marts.dim_date AS
SELECT DISTINCT order_date AS date_key,
 EXTRACT(YEAR FROM order_date) AS calendar_year,
 EXTRACT(MONTH FROM order_date) AS calendar_month,
 EXTRACT(DAY FROM order_date) AS day_of_month
FROM staging.sales;

CREATE TABLE IF NOT EXISTS marts.fact_sales (
 order_id VARCHAR PRIMARY KEY, date_key DATE, customer_key VARCHAR,
 product_id VARCHAR, store_id VARCHAR, quantity INTEGER,
 unit_price_cents INTEGER, revenue_cents BIGINT, updated_at TIMESTAMP
);
