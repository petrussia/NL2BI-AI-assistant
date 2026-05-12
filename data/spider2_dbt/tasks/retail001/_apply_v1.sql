WITH revenue_by_country AS (
  SELECT
    c.country,
    COUNT(DISTINCT i.invoice_id) AS total_invoices,
    SUM(i.total) AS total_revenue
  FROM {{ ref('fct_invoices') }} i
  JOIN {{ ref('dim_customer') }} c ON i.customer_id = c.customer_id
  GROUP BY c.country
)
SELECT
  country,
  total_invoices,
  total_revenue
FROM revenue_by_country
ORDER BY total_revenue DESC
LIMIT 10;
