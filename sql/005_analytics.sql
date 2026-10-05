WITH regional_sales AS (
 SELECT c.region, SUM(f.revenue_cents) AS revenue_cents, COUNT(*) AS orders
 FROM marts.fact_sales f JOIN marts.dim_customer c ON f.customer_key=c.customer_key
 GROUP BY c.region
)
SELECT region, orders, revenue_cents,
 DENSE_RANK() OVER (ORDER BY revenue_cents DESC) AS revenue_rank
FROM regional_sales ORDER BY revenue_rank, region;
