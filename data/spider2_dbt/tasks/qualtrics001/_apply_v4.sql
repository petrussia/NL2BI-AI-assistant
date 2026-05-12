```diff
--- a/models/qualtrics__contact.sql
+++ b/models/qualtrics__contact.sql
@@ -1,6 +1,7 @@
 with contacts as (
     select *
     from {{ ref('int_qualtrics__contacts') }}
+),
+directory_contact as (
     select *
     from {{ var('directory_contact') }}
 ),
@@ -14,6 +15,7 @@
     select *
     from {{ var('distribution_contact') }}
 ),
+distribution as (
     select *
     from {{ var('distribution') }}
 ),
@@ -22,6 +24,7 @@
     select *
     from {{ var('survey_response') }}
 ),
+distribution_response as (
     select
         distribution_contact.*,
         distribution.survey_id,
@@ -31,6 +34,7 @@
         survey_response.response_started_at,
         survey_response.response_completed_at
     from distribution_contact 
+    left join distribution on distribution_contact.distribution_id = distribution.distribution_id
     left join survey_response
         on distribution_contact.response_id = survey_response.response_id
 ),
@@ -40,6 +44,7 @@
     select
         directory.id as directory_id,
         directory.name as directory_name,
+        directory_contact.contact_id,
         directory_contact.email,
         directory_contact.phone,
         directory_contact.first_name,
@@ -48,6 +53,7 @@
         directory_contact.last_name,
         directory_contact.unsubscribed as is_directory_unsubscribed,
         directory_contact.directory_unsubscribed as is_directory_unsubscribed_from_directory,
+        directory_contact.creation_date,
         directory_contact.directory_unsubscribe_date,
         directory_contact.ext_ref,
         directory_contact.language,
@@ -57,6 +63,7 @@
         directory_contact.write_blanks,
         directory_contact.mailing_list_id,
         directory_contact.directory_unsubscribed_at,
+        directory_contact.directory_unsubscribed_by,
         directory_contact.directory_unsubscribed_reason,
         directory_contact.directory_unsubscribed_comment,
         directory_contact.directory_unsubscribed_by_email,
@@ -66,6 +73,7 @@
         directory_contact.directory_unsubscribed_by_phone,
         directory_contact.directory_unsubscribed_by_ip,
         directory_contact.directory_unsubscribed_by_location,
+        directory_contact.directory_unsubscribed_by_device,
         directory_contact.directory_unsubscribed_by_browser,
         directory_contact.directory_unsubscribed_by_os,
         directory_contact.directory_unsubscribed_by_country,
@@ -75,6 +83,7 @@
         directory_contact.directory_unsubscribed_by_region,
         directory_contact.directory_unsubscribed_by_city,
         directory_contact.directory_unsubscribed_by_zip,
+        directory_contact.directory_unsubscribed_by_postal_code,
         directory_contact.directory_unsubscribed_by_timezone,
         directory_contact.directory_unsubscribed_by_currency,
         directory_contact.directory_unsubscribed_by_language,
@@ -84,6 +93,7 @@
         directory_contact.directory_unsubscribed_by_device_type,
         directory_contact.directory_unsubscribed_by_device_model,
         directory_contact.directory_unsubscribed_by_device_os,
+        directory_contact.directory_unsubscribed_by_device_browser,
         directory_contact.directory_unsubscribed_by_device_resolution,
         directory_contact.directory_unsubscribed_by_device_pixel_density,
         directory_contact.directory_unsubscribed_by_device_orientation,
@@ -93,6 +103,7 @@
         directory_contact.directory_unsubscribed_by_device_battery_level,
         directory_contact.directory_unsubscribed_by_device_signal_strength,
         directory_contact.directory_unsubscribed_by_device_network_type,
+        directory_contact.directory_unsubscribed_by_device_connection_speed,
         directory_contact.directory_unsubscribed_by_device_location_accuracy,
         directory_contact.directory_unsubscribed_by_device_location_permission,
         directory_contact.directory_unsubscribed_by_device_location_provider,
@@ -102,6 +113,7 @@
         directory_contact.directory_unsubscribed_by_device_location_update_interval,
         directory_contact.directory_unsubscribed_by_device_location_update_method,
         directory_contact.directory_unsubscribed_by_device_location_update_accuracy,
+        directory_contact.directory_unsubscribed_by_device_location_update_permission,
         directory_contact.directory_unsubscribed_by_device_location_update_provider,
         directory_contact.directory_unsubscribed_by_device_location_update_method,
         directory_contact.directory_unsubscribed_by_device_location_update_accuracy,
@@ -111,6 +123,7 @@
         directory_contact.directory_unsubscribed_by_device_location_update_permission,
         directory_contact.directory_unsubscribed_by_device_location_update_provider,
         directory_contact.directory_unsubscribed_by_device_location_update_method,
+        directory_contact.directory_unsubscribed_by_device_location_update_accuracy,
         directory_contact.directory_unsubscribed_by_device_location_update_permission,
         directory_contact.directory_unsubscribed_by_device_location_update_provider,
         directory_contact.directory_unsubscribed_by_device_location_update_method,
@@ -120,6 +133,7 @@
         directory_contact.directory_unsubscribed_by_device_location_update_permission,
         directory_contact.directory_unsubscribed_by_device_location_update_provider,
         directory_contact.directory_unsubscribed_by_device_location_update_method,
+        directory_contact.directory_unsubscribed_by_device_location_update_accuracy,
         directory_contact.directory_unsubscribed_by_device_location_update_permission,
         directory_contact.directory_unsubscribed_by_device_location_update_provider,
         directory_contact.directory_unsubscribed_by_device_location_update_method,
@@ -129,6 +143,7 @@
         directory_contact.directory_unsubscribed_by_device_location_update_permission,
         directory_contact.directory_unsubscribed_by_device_location_update_provider,
         directory_contact.directory_unsubscribed_by_device_location_update_method,
+        directory_contact.directory_unsubscribed_by_device_location_update_accuracy,
         directory_contact.directory_unsubscribed_by_device_location_update_permission,
         directory_contact.directory_unsubscribed_by_device_location_update_provider,
         directory_contact.directory_unsubscribed_by_device_location_update_method,
@@ -138,6 +153,7 @@
         directory_contact.directory_unsubscribed_by_device_location_update_permission,
         directory_contact.directory_unsubscribed_by_device_location_update_provider,
         directory_contact.directory_unsubscribed_by_device_location_update_method,
+        directory_contact.directory_unsubscribed_by_device_location_update_accuracy,
         directory_contact.directory_unsubscribed_by_device_location_update_permission,
         directory_contact.directory_unsubscribed_by_device_location_update_provider,
         directory_contact.directory_unsubscribed_by_device_location_update_method,
@@ -147,6 +163,7 @@
         directory_contact.directory_unsubscribed_by_device_location_update_permission,
         directory_contact.directory_unsubscribed_by_device_location_update_provider,
         directory_contact.directory_unsubscribed_by_device_location_update_method,
+        directory_contact.directory_unsubscribed_by_device_location_update_accuracy,
         directory_contact.directory_unsubscribed_by_device_location_update_permission,
         directory_contact.directory_unsubscribed_by_device_location_update_provider,
         directory_contact.directory_unsubscribed_by_device_location_update_method,
@@ -156,6 +173,7 @@
         directory_contact.directory_unsubscribed_by_device_location_update_permission,
         directory_contact.directory_unsubscribed_by_device_location_update_provider,
         directory_contact.directory_unsubscribed_by_device_location_update_method,
+        directory_contact.directory_unsubscribed_by_device_location_update_accuracy,
         directory_contact.directory_unsubscribed_by_device_location_update_permission,