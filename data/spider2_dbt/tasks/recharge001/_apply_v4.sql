```diff
--- a/models/standardized_models/recharge__line_item_enhanced.sql
+++ b/models/standardized_models/recharge__line_item_enhanced.sql
@@ -14,6 +14,7 @@
     , charge_shipping_lines as (
         select
             charge_id,
+            sum(price) as total_shipping
         from {{ var('charge_shipping_line') }}
         group by 1
     )
@@ -28,6 +29,7 @@
     , charge_tax_lines as (
         select
             charge_id,
+            sum(price) as total_tax
         from {{ var('charge_tax_line') }}
         group by 1
     )
@@ -42,6 +44,7 @@
     , charge_refunds as (
         select
             charge_id,
+            sum(amount) as total_refund
         from {{ var('charge_refund') }}
         group by 1
     )
@@ -56,6 +59,7 @@
     , charge_discounts as (
         select
             charge_id,
+            sum(value) as total_discount
         from {{ var('charge_discount') }}
         group by 1
     )
@@ -70,6 +74,7 @@
     , charge_line_items as (
         select * 
         from {{ var('charge_line_item')}}
+        cross join charge_shipping_lines
+        cross join charge_tax_lines
+        cross join charge_refunds
+        cross join charge_discounts
     )
     , charges as (
         select * 
         from {{ var('charge') }}
     )
     , charge_order_attributes as (
         select
             charge_id,
@@ -84,6 +89,7 @@
     , addresses as (
         select * 
         from {{ var('address') }}
+        cross join charge_shipping_lines
     ), customers as (
         select * 
         from {{ var('customer') }}
+        cross join charge_shipping_lines
     ), subscriptions as (
         select *
         from {{ var('subscription_history') }} 
         where is_most_recent_record
+        cross join charge_shipping_lines
     ), enhanced as (
         select
             cast(charge_line_items.charge_id as {{ dbt.type_string() }}) as header_id,
             cast(charge_line_items.index as {{ dbt.type_int() }}) as line_item_index,
             charge_line_items.variant_title,
             charge_line_items.title,
             charge_line_items.quantity,
             charge_line_items.grams,
             charge_line_items.total_price,
             charge_line_items.sku,
             charge_line_items.external_product_id_ecommerce,
             charge_line_items.vendor,
             charge_line_items.unit_price,
             charge_line_items.tax_due,
             charge_line_items.taxable,
             charge_line_items.taxable_amount,
             charge_line_items.unit_price_includes_tax,
             charge_line_items.purchase_item_id,
             charge_line_items.purchase_item_type,
             charge_line_items.external_variant_id_ecommerce,
             charge_shipping_lines.total_shipping,
+            charge_tax_lines.total_tax,
+            charge_refunds.total_refund,
+            charge_discounts.total_discount,
             charges.created_at as header_created_at,
             charges.updated_at as header_updated_at,
             charges.processed_at as header_processed_at,
             charges.scheduled_at as header_scheduled_at,
             charges.orders_count,
             charges.external_order_id_ecommerce,
             charges.subtotal_price,
             charges.tags,
             charges.tax_lines,
             charges.total_discounts,
             charges.total_line_items_price,
             charges.total_price,
             charges.total_tax,
             charges.total_weight_grams,
             charges.type,
             charges.status,
             charges.total_refunds,
             charges.external_transaction_id_payment_processor,
             charges.email,
             charges.payment_processor,
             charges.has_uncommitted_changes,
             charges.retry_date,
             charges.error_type,
             charges.error,
             charges.charge_attempts,
             charge_order_attributes.order_attribute,
             addresses.id as address_id,
             addresses.first_name,
             addresses.last_name,
             addresses.address_1,
             addresses.address_2,
             addresses.city,
             addresses.province,
             addresses.country_code,
             addresses.zip,
             addresses.company,
             addresses.phone,
             addresses.created_at as address_created_at,
             addresses.updated_at as address_updated_at,
             addresses._fivetrans_deleted as address_fivetrans_deleted,
             addresses._fivetrans_synced as address_fivetrans_synced,
             customers.id as customer_id,
             customers.hash as customer_hash,
             customers.external_customer_id_ecommerce,
             customers.email,
             customers.created_at as customer_created_at,
             customers.updated_at as customer_updated_at,
             customers.first_charge_processed_at,
             customers.first_name as customer_first_name,
             customers.last_name as customer_last_name,
             customers.subscriptions_active_count,
             customers.subscriptions_total_count,
             customers.has_valid_payment_method,
             customers.has_payment_method_in_dunning,
             customers._fivetrans_deleted as customer_fivetrans_deleted,
             customers._fivetrans_synced as customer_fivetrans_synced,
             subscriptions.id as subscription_id,
             subscriptions.subscription_id,
             subscriptions.plan_id,
             subscriptions.interval,
             subscriptions.interval_count,
             subscriptions.trial_end,
             subscriptions.cancelled_at,
             subscriptions.canceled_at,
             subscriptions.current_period_start,
             subscriptions.current_period_end,
             subscriptions.next_bill_date,
             subscriptions.paused_at,
             subscriptions.paused_until,
             subscriptions.status,
             subscriptions.is_trialing,
             subscriptions.is_cancelled,
             subscriptions.is_canceled,
             subscriptions.is_paused,
             subscriptions.is_future,
             subscriptions.is_current,
             subscriptions.is_past_due,
             subscriptions.is_overdue,
             subscriptions.is_expired,
             subscriptions.is_renewal_pending,
             subscriptions.is_renewal_failed,
             subscriptions.is_renewal_successful,
             subscriptions.is_renewal_skipped,
             subscriptions.is_renewal_canceled,
             subscriptions.is_renewal_paused,
             subscriptions.is_renewal_resumed,
             subscriptions.is_renewal_completed,
             subscriptions.is_renewal_failed,
             subscriptions.is_renewal_successful,
             subscriptions.is_renewal_skipped,
             subscriptions.is_renewal_canceled,
             subscriptions.is_renewal_paused,
             subscriptions.is_renewal_resumed,
             subscriptions.is_renewal_completed,
             subscriptions.is_renewal_failed,
             subscriptions.is_renewal_successful,
             subscriptions.is_renewal_skipped,
             subscriptions.is_renewal_canceled,
             subscriptions.is_renewal_paused,
             subscriptions.is_renewal_resumed,
             subscriptions.is_renewal_completed,
             subscriptions.is_renewal_failed,
             subscriptions.is_renewal_successful,
             subscriptions.is_renewal_skipped,
             subscriptions.is_renewal_canceled,
             subscriptions.is_renewal_paused,
             subscriptions.is_renewal_resumed,
             subscriptions.is_renewal_completed,
             subscriptions.is_renewal_failed,
             subscriptions.is_renewal_successful,
             subscriptions.is_renewal_skipped,
             subscriptions.is_renewal_canceled,
             subscriptions.is_renewal_paused,
             subscriptions.is_renewal_resumed,
             subscriptions.is_renewal_completed,
             subscriptions.is_renewal_failed,
             subscriptions.is_renewal