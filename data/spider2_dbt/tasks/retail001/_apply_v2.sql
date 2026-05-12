SELECT
  country,
  total_invoices,
  total_revenue
FROM
  {{ ref('report_customer_invoices') }}
ORDER BY
  total_revenue DESC
LIMIT 10;
