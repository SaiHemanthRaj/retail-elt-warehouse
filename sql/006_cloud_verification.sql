SELECT 'fact_rows' AS check_name, COUNT(*) AS actual_value, 1220 AS expected_value, COUNT(*)=1220 AS passed FROM marts.fact_sales
UNION ALL SELECT 'revenue_cents',SUM(revenue_cents),7821134,SUM(revenue_cents)=7821134 FROM marts.fact_sales
UNION ALL SELECT 'customer_versions',COUNT(*),66,COUNT(*)=66 FROM marts.dim_customer
UNION ALL SELECT 'raw_sales_rows',COUNT(*),1255,COUNT(*)=1255 FROM raw.sales
UNION ALL SELECT 'committed_batches',COUNT(*),2,COUNT(*)=2 FROM raw.batches
UNION ALL SELECT check_name,failures,0,failures=0 FROM (SELECT 'missing_customer' AS check_name, COUNT(*) AS failures FROM staging.sales s
LEFT JOIN marts.dim_customer c ON s.customer_id=c.customer_id
 AND s.order_date>=c.valid_from AND s.order_date<c.valid_to WHERE c.customer_key IS NULL
UNION ALL
SELECT 'missing_product', COUNT(*) FROM staging.sales s LEFT JOIN marts.dim_product p
 ON s.product_id=p.product_id WHERE p.product_id IS NULL
UNION ALL
SELECT 'missing_store', COUNT(*) FROM staging.sales s LEFT JOIN marts.dim_store d
 ON s.store_id=d.store_id WHERE d.store_id IS NULL
UNION ALL
SELECT 'fact_count', ABS((SELECT COUNT(*) FROM staging.sales)-(SELECT COUNT(*) FROM marts.fact_sales))
UNION ALL
SELECT 'revenue_reconciliation', ABS(
 COALESCE((SELECT SUM(CAST(quantity AS BIGINT)*unit_price_cents) FROM staging.sales),0)
 - COALESCE((SELECT SUM(revenue_cents) FROM marts.fact_sales),0))
UNION ALL
SELECT 'duplicate_fact', COUNT(*) FROM (SELECT order_id FROM marts.fact_sales GROUP BY order_id HAVING COUNT(*)>1) d) ORDER BY check_name;
