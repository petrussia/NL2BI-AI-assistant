```diff
--- a/models/marketing/final/hubspot_email_summary.sql
+++ b/models/marketing/final/hubspot_email_summary.sql
@@ -1,6 +1,7 @@
 {{ config(materialized='table') }}
 
-with email_events as (
+with email_events as (
     select *
     from {{ ref('int_hubspot__email_event_aggregates') }}
 ),
@@ -14,6 +15,7 @@
     select *
     from {{ ref('int_hubspot__email_metrics__by_contact_list') }}
 ),
+contact_data as (
     select *
     from {{ ref('hubspot.duckdb.main.contact_data') }}
 ),
@@ -22,6 +24,7 @@
     select *
     from {{ ref('int_hubspot__engagement_metrics__by_contact') }}
 ),
+email_campaign_data as (
     select *
     from {{ ref('hubspot.duckdb.main.email_campaign_data') }}
 ),
@@ -30,6 +33,7 @@
     select *
     from {{ ref('int_hubspot__deals_enhanced') }}
 ),
+contact_list_member_data as (
     select *
     from {{ ref('hubspot.duckdb.main.contact_list_member_data') }}
 ),
@@ -38,6 +42,7 @@
     select *
     from {{ ref('hubspot.duckdb.main.company_data') }}
 ),
+contact_property_history_data as (
     select *
     from {{ ref('hubspot.duckdb.main.contact_property_history_data') }}
 ),
@@ -46,6 +51,7 @@
     select *
     from {{ ref('hubspot.duckdb.main.email_event_data') }}
 ),
+contact_merge_audit_data as (
     select *
     from {{ ref('hubspot.duckdb.main.contact_merge_audit_data') }}
 ),
@@ -54,6 +60,7 @@
     select *
     from {{ ref('hubspot.duckdb.main.deal_data') }}
 ),
+deal_contact_data as (
     select *
     from {{ ref('hubspot.duckdb.main.deal_contact_data') }}
 ),
@@ -62,6 +69,7 @@
     select *
     from {{ ref('hubspot.duckdb.main.deal_pipeline_data') }}
 ),
+deal_pipeline_stage_data as (
     select *
     from {{ ref('hubspot.duckdb.main.deal_pipeline_stage_data') }}
 ),
@@ -70,6 +78,7 @@
     select *
     from {{ ref('hubspot.duckdb.main.deal_property_history_data') }}
 ),
+deal_stage_data as (
     select *
     from {{ ref('hubspot.duckdb.main.deal_stage_data') }}
 ),
@@ -78,6 +87,7 @@
     select *
     from {{ ref('hubspot.duckdb.main.email_event_bounce_data') }}
 ),
+email_event_click_data as (
     select *
     from {{ ref('hubspot.duckdb.main.email_event_click_data') }}
 ),
@@ -86,6 +96,7 @@
     select *
     from {{ ref('hubspot.duckdb.main.email_event_deferred_data') }}
 ),
+email_event_delivered_data as (
     select *
     from {{ ref('hubspot.duckdb.main.email_event_delivered_data') }}
 ),
@@ -94,6 +105,7 @@
     select *
     from {{ ref('hubspot.duckdb.main.email_event_dropped_data') }}
 ),
+email_event_forward_data as (
     select *
     from {{ ref('hubspot.duckdb.main.email_event_forward_data') }}
 ),
@@ -102,6 +114,7 @@
     select *
     from {{ ref('hubspot.duckdb.main.email_event_open_data') }}
 ),
+email_event_print_data as (
     select *
     from {{ ref('hubspot.duckdb.main.email_event_print_data') }}
 ),
@@ -110,6 +123,7 @@
     select *
     from {{ ref('hubspot.duckdb.main.email_event_status_change_data') }}
 ),
+email_event_unsubscribe_data as (
     select *
     from {{ ref('hubspot.duckdb.main.email_event_unsubscribe_data') }}
 ),
@@ -118,6 +132,7 @@
     select *
     from {{ ref('hubspot.duckdb.main.email_template_data') }}
 ),
+email_template_version_data as (
     select *
     from {{ ref('hubspot.duckdb.main.email_template_version_data') }}
 ),
@@ -126,6 +141,7 @@
     select *
     from {{ ref('hubspot.duckdb.main.email_template_version_history_data') }}
 ),
+email_template_version_usage_data as (
     select *
     from {{ ref('hubspot.duckdb.main.email_template_version_usage_data') }}
 ),
@@ -134,6 +150,7 @@
     select *
     from {{ ref('hubspot.duckdb.main.email_template_version_usage_history_data') }}
 ),
+email_template_version_usage_stats_data as (
     select *
     from {{ ref('hubspot.duckdb.main.email_template_version_usage_stats_data') }}
 ),
@@ -142,6 +159,7 @@
     select *
     from {{ ref('hubspot.duckdb.main.email_template_version_usage_stats_history_data') }}
 ),
+email_template_version_usage_stats_summary_data as (
     select *
     from {{ ref('hubspot.duckdb.main.email_template_version_usage_stats_summary_data') }}
 ),
@@ -150,6 +168,7 @@
     select *
     from {{ ref('hubspot.duckdb.main.email_template_version_usage_stats_summary_history_data') }}
 ),
+email_template_version_usage_stats_summary_stats_data as (
     select *
     from {{ ref('hubspot.duckdb.main.email_template_version_usage_stats_summary_stats_data') }}
 ),
@@ -158,6 +177,7 @@
     select *
     from {{ ref('hubspot.duckdb.main.email_template_version_usage_stats_summary_stats_history_data') }}
 ),
+email_template_version_usage_stats_summary_stats_summary_data as (
     select *
     from {{ ref('hubspot.duckdb.main.email_template_version_usage_stats_summary_stats_summary_data') }}
 ),
@@ -166,6 +186,7 @@
     select *
     from {{ ref('hubspot.duckdb.main.email_template_version_usage_stats_summary_stats_summary_history_data') }}
 ),
+email_template_version_usage_stats_summary_stats_summary_stats_data as (
     select *
     from {{ ref('hubspot.duckdb.main.email_template_version_usage_stats_summary_stats_summary_stats_data') }}
 ),
@@ -174,6 +195,7 @@
     select *
     from {{ ref('hubspot.duckdb.main.email_template_version_usage_stats_summary_stats_summary_stats_history_data') }}
 ),
+email_template_version_usage_stats_summary_stats_summary_stats_summary_data as (
     select *
     from {{ ref('hubspot.duckdb.main.email_template_version_usage_stats_summary_stats_summary_stats_summary_data') }}
 ),
@@ -182,6 +204,7 @@
     select *
     from {{ ref('hubspot.duckdb.main.email_template_version_usage_stats_summary_stats_summary