,6 +1,7 @@
 {{ config(enabled=var('using_bill', True)) }}
 
 with bills as (
     select *
     from {{ source('main', 'bill_data') }}
+    left join {{ source('main', 'bill_line_data') }} on bills.id = bill_line_data.bill_id
 ),
 bill_payments as (
     select *
@@ -18,6 +19,10 @@
     select *
     from {{ source('main', 'customer_data') }}
 ),
+suppliers as (
+    select *
+    from {{ source('main', 'vendor_data') }}
+),
 address_data as (
     select *
     from {{ source('main', 'address_data') }}
@@ -34,6 +43,10 @@
     select *
     from {{ source('main', 'payment_data') }}
 ),
+payment_statuses as (
+    select *
+    from {{ source('main', 'payment_status_data') }}
+),
 final as (
     select
         bills.id as bill_id,
@@ -42,6 +55,10 @@
         bills.balance as bill_balance,
         bills.due_date as bill_due_date,
         bills.transaction_date as bill_transaction_date,
+        suppliers.name as supplier_name,
+        customers.name as customer_name,
+        payment_statuses.status as payment_status,
+        (bills.balance - coalesce(sum(bill_payments.total_amount), 0)) as balance,
+        datediff(current_date, bills.due_date) as overdue_days
     from bills
     left join bill_payments on bills.id = bill_payments.billed_entity_id
     left join customers on bills.vendor_id = customers.id
+    left join suppliers on bills.vendor_id = suppliers.id
+    left join payment_statuses on bills.payment_status_id = payment_statuses.id
 )
 select * from final
```