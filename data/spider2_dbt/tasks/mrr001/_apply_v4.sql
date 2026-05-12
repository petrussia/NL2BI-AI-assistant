00 chars):
    with contacts as (

        select *
        from {{ ref('int_qualtrics__contacts') }}
    ),

    directory as (

        select *
        from {{ var('directory') }}
    ),

    distribution_contact as (

        select *
        from {{ var('distribution_contact') }}
    ),

    distribution as (
    -- just to grab survey id 
        select *
        from {{ var('distribution') }}
    ),

    survey_response as (

        select *
        from {{ var('survey_response') }}
    ),

    distribution_response as (

        select
            distribution_contact.*,
            distribution.survey_id,
            survey_response.distribution_channel,
            survey_response.progress,
            survey_response.duration_in_seconds,
            survey_response.is_finished,
            survey_response.recorded_date

        from distribution_contact 
        left join distribution
            on distribution_contact.distribution_id = distribution.distribution_id
            and distribution_contact.source_relation =
  - models/qualtrics__daily_breakdown.sql
    cols: min_date, date, date_day, count_distinct_surveys_responded_to, total_count_survey_responses, total_count_completed_survey_responses, count_, count_uncategorized_survey_responses, count_uncategorized_completed_survey_responses, count_contacts_sent_surveys, count_contacts_opened_sent_surveys, count_contacts_started_sent_surveys, count_contacts_completed_sent_surveys, count_contacts_created, count_contacts_unsubscribed_from_directory, count_contacts_unsubscribed_from_mailing_list, source_relation, count_anonymous_survey_responses, ...(29 total)
    --- body (first 900 chars):
    with response as (

        select *
        from {{ ref('qualtrics__response') }}
    ),

    contact as (

        select *
        from {{ ref('qualtrics__contact') }}
    ),

    contact_mailing_list_membership as (

        select *
        from {{ var('contact_mailing_list_membership') }}
    ),

    distribution_contact as (

        select *
        from {{ var('distribution_contact') }}
    ),

    spine as (

        {% if execute %}
        {% set first_date_query %}
            select  coalesce( min( sent_at ), '2016-01-01') as min_date from {{ var('distribution_contact') }}
        {% endset %}
        {% set first_date = run_query(first_date_query).columns[0][0]|string %}

        {% else %} {% set first_date = "2016-01-01" %}
        {% endif %}

        {{ dbt_utils.date_spine(
            datepart = "day", 
            start_date =  "cast('" ~ first_date[0:10] ~ "' as date)", 
            end_date = dbt.dateadd("week", 1, dbt.date_trunc('day', dbt.current_timestamp_backcom
  - models/qualtrics__distribution.sql
    cols: time_to_open_in_seconds, time_to_start_in_seconds, time_to_complete_in_seconds, current_count_surveys_, total_count_contacts, count_contacts_sent_surveys, count_contacts_opened_surveys, count_contacts_started_surveys, count_contacts_completed_surveys, first_survey_sent_at, last_survey_sent_at, first_survey_opened_at, last_survey_opened_at, first_response_completed_at, last_response_completed_at, avg_time_to_open_in_seconds, avg_time_to_start_in_seconds, avg_time_to_complete_in_seconds, ...(28 total)
    --- body (first 900 chars):
    with distribution as (

        select *
        from {{ var('distribution') }}
    ),

    qualtrics_user as (

        select *
        from {{ var('user') }}
    ),

    directory_mailing_list as (

        select *
        from {{ var('directory_mailing_list') }}
    ),

    {% if var('qualtrics__using_core_mailing_lists', false) %}
    core_mailing_list as (

        select *
        from {{ var('core_mailing_list') }}
    ),
    {% endif %}

    distribution_contact as (

        select 
            *,
            -- all relative to sent_at (should response be relative to opened_at?)
            {{ fivetran_utils.timestamp_diff(first_date="sent_at", second_date="opened_at", datepart="second") }} as time_to_open_in_seconds,
            {{ fivetran_utils.timestamp_diff(first_date="sent_at", second_date="response_started_at", datepart="second") }} as time_to_start_in_seconds,
            {{ fivetran_utils.timestamp_diff(first_date
... (truncated)
assistant
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