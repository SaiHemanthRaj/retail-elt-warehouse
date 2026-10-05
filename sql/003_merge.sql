MERGE INTO marts.fact_sales AS target
USING (
 SELECT s.order_id, s.order_date AS date_key, c.customer_key, s.product_id, s.store_id,
 s.quantity, s.unit_price_cents, CAST(s.quantity AS BIGINT)*s.unit_price_cents AS revenue_cents, s.updated_at
 FROM staging.sales s
 JOIN marts.dim_customer c ON s.customer_id=c.customer_id
   AND s.order_date>=c.valid_from AND s.order_date<c.valid_to
) AS source ON target.order_id=source.order_id
WHEN MATCHED THEN UPDATE SET date_key=source.date_key, customer_key=source.customer_key,
 product_id=source.product_id, store_id=source.store_id, quantity=source.quantity,
 unit_price_cents=source.unit_price_cents, revenue_cents=source.revenue_cents, updated_at=source.updated_at
WHEN NOT MATCHED THEN INSERT (order_id,date_key,customer_key,product_id,store_id,quantity,unit_price_cents,revenue_cents,updated_at)
VALUES(source.order_id,source.date_key,source.customer_key,source.product_id,source.store_id,
source.quantity,source.unit_price_cents,source.revenue_cents,source.updated_at);
