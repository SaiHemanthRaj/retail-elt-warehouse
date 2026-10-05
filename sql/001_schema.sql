CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS marts;
CREATE TABLE IF NOT EXISTS raw.batches (batch_hash VARCHAR PRIMARY KEY, source_name VARCHAR, row_count INTEGER);
CREATE TABLE IF NOT EXISTS raw.sales (
 order_id VARCHAR, order_date DATE, customer_id VARCHAR, product_id VARCHAR,
 store_id VARCHAR, quantity INTEGER, unit_price_cents INTEGER, updated_at TIMESTAMP,
 batch_hash VARCHAR
);
CREATE TABLE IF NOT EXISTS raw.customer_history (
 customer_id VARCHAR, region VARCHAR, valid_from DATE, PRIMARY KEY(customer_id, valid_from)
);
CREATE TABLE IF NOT EXISTS marts.dim_product (product_id VARCHAR PRIMARY KEY, category VARCHAR);
CREATE TABLE IF NOT EXISTS marts.dim_store (store_id VARCHAR PRIMARY KEY, store_name VARCHAR);
