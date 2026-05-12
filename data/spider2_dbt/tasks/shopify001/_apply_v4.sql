first name of the customer."
+  - name: customer_last_name
+    description: "The last name of the customer."
+  - name: customer_company
+    description: "The company associated with the customer."
+  - name: customer_support_rep_id
+    description: "The ID of the support representative handling the customer."
+
 select
     i.invoice_id,
     i.customer_id,
@@ -35,6 +57,17 @@
     i.billing_state,
     i.billing_country,
     i.billing_postal_code,
+    c.first_name AS customer_first_name,
+    c.last_name AS customer_last_name,
+    c.company AS customer_company,
+    c.support_rep_id AS customer_support_rep_id,
+    d.date_key,
+    d.day_of_year,
+    d.week_key,
+    d.week_of_year,
+    d.day_of_week,
+    d.iso_day_of_week,
+    d.day_name,
+    d.first_day_of_week,
+    d.last_day_of_week,
+    d.month_key,
+    d.month_of_year,
+    d.day_of_month,
+    d.month_name_short,
+    d.month_name,
+    d.first_day_of_month,
+    d.last_day_of_month
 from
     {{ ref('fct_invoice') }} i
 join
     {{ ref('dim_customer') }} c on i.customer_id = c.customer_id
 join
     {{ ref('dim_date') }} d on i.invoice_date = d.date_key
```