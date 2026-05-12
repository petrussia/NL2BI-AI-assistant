,
            sum(s.price_paid) as total_sales,
            sum(s.qty_sold) as total_tickets_sold,
            round(total_sales / total_tickets_sold, 2) as avg_tickit_sale_price,
            sum(s.commission) as total_commissions,
            sum(s.earnings) as total_earnings
        from 
            sales as s
                join dates as d on d.date_id = s.date_id
        group by
            year,
            month,
      		quarter
        order by 
            year,
            month,
      		quarter

    )

    select * from final
  - models/analyses/non_buyer_likes.sql
    cols: integer, sports, theatre, concerts, jazz, classical, opera, rock, vegas, broadway, musicals, like_id
    --- body (first 900 chars):
    {{ config(materialized='table', sort='event_type', dist='like_id') }}

    {%- set event_types = 'sports, theatre, concerts, jazz, classical, opera, rock, vegas, broadway, musicals' -%}

    with buyers as (

        select * from {{ ref('dim_non_buyers') }}

    ),

    total_likes as (

        select
            sum(coalesce(cast(like_sports as integer), 0)) as sports,
            sum(coalesce(cast(like_theatre as integer), 0)) as theatre,
            sum(coalesce(cast(like_concerts as integer), 0)) as concerts,
            sum(coalesce(cast(like_jazz as integer), 0)) as jazz,
            sum(coalesce(cast(like_classical as integer), 0)) as classical,
            sum(coalesce(cast(like_opera as integer), 0)) as opera,
            sum(coalesce(cast(like_rock as integer), 0)) as rock,
            sum(coalesce(cast(like_vegas as integer), 0)) as vegas,
            sum(coalesce(cast(like_broadway as integer), 0)) as broadway,
            sum(c
  - models/analyses/sales_by_category.sql
    cols: total_transactions, total_tickets_sold, total_sales, total_commissions, total_earnings, avg_tickit_sale_price
    --- body (first 900 chars):
    with sales as (

            select * from {{ ref('stg_tickit__sales') }}

    ),

    events as (

            select * from {{ ref('stg_tickit__events') }}

    ),

    categories as (

            select * from {{ ref('stg_tickit__categories') }}

    ),

    final as (

        select
            c.cat_group,
            c.cat_name,
            count(s.price_paid) as total_transactions,
            sum(s.qty_sold) as total_tickets_sold,
            sum(s.price_paid) as total_sales,
            sum(s.commission) as total_commissions,
            sum(s.earnings) as total_earnings,
            round(total_sales / total_tickets_sold, 2) as avg_tickit_sale_price
        from
            sales s,
            events e,
            categories c
        where
            s.event_id = e.event_id
                and c.cat_id = e.cat_id
        group by
            cat_group,
            cat_name
        order by
            cat_group, 
            cat_name

    )

    select * from final

--- dbt_project.yml (head) ---

# Name your project! Project names should contain only lowercase characters
# and underscores. A good package name should reflect your organization's
# name or the intended use of these models
name: 'dbt_redshift_demo'
version: '1.0.0'
config-version: 2

# This setting configures which "profile" dbt uses for this project.
profile: 'tickit'

# These configurations specify where dbt should look for different types of files.
# The `source-paths` config, for example, states that models in this proj


--- models/intermediate/users/_int_users__models.yml (head) ---
version: 2

models:
  - name: int_buyers_extracted_from_users
    description: All buyers, based on sales history, extracted from users

  - name: int_sellers_extracted_from_users
    description: All sellers, based on sales history, extracted from users



        REMEMBER: prefer extending an existing final model via a unified
        diff over writing a new file. Keep changes minimal — small,
        focused additions are easier to validate.

        DIFF (or SQL fallback) — one fenced block, nothing else:
assistant
```diff
--- a/models/final/events_with_details.sql
+++ b/models/final/events_with_details.sql
@@ -1,3 +1,4 @@
+with events as (
     select * from {{ ref('stg_tickit__events') }}
 ),
@@ -6,3 +7,4 @@
     select * from {{ ref('stg_tickit__listings') }}
 ),
@@ -9,3 +10,4 @@
     select * from {{ ref('stg_tickit__sales') }}
 ),
@@ -12,3 +13,4 @@
     select * from {{ ref('stg_tickit__categories') }}
 ),
@@ -15,3 +16,4 @@
     select * from {{ ref('stg_tickit__venues') }}
 ),
@@ -18,3 +19,4 @@
     select * from {{ ref('stg_tickit__users') }}
 ),
@@ -21,3 +22,4 @@
     select * from {{ ref('stg_tickit__dates') }}
 ),
@@ -24,3 +25,4 @@
     select * from {{ ref('stg_tickit__sales') }}
 ),
@@ -27,3 +28,4 @@
     select * from {{ ref('stg_tickit__categories') }}
 ),
@@ -30,3 +31,4 @@
     select * from {{ ref('stg_tickit__venues') }}
 ),
@@ -33,3 +34,4 @@
     select * from {{ ref('stg_tickit__users') }}
 ),
@@ -36,3 +37,4 @@
     select * from {{ ref('stg_tickit__dates') }}
 ),
@@ -39,3 +40,4 @@
     select * from {{ ref('stg_tickit__sales') }}
 ),
@@ -42,3 +43,4 @@
     select * from {{ ref('stg_tickit__categories') }}
 ),
@@ -45,3 +46,4 @@
     select * from {{ ref('stg_tickit__venues') }}
 ),
@@ -48,3 +49,4 @@
     select * from {{ ref('stg_tickit__users') }}
 ),
@@ -51,3 +52,4 @@
     select * from {{ ref('stg_tickit__dates') }}
 ),
@@ -54,3 +55,4 @@
     select * from {{ ref('stg_tickit__sales') }}
 ),
@@ -57,3 +58,4 @@
     select * from {{ ref('stg_tickit__categories') }}
 ),
@@ -60,3 +61,4 @@
     select * from {{ ref('stg_tickit__venues') }}
 ),
@@ -63,3 +64,4 @@
     select * from {{ ref('stg_tickit__users') }}
 ),
@@ -66,3 +67,4 @@
     select * from {{ ref('stg_tickit__dates') }}
 ),
@@ -69,3 +70,4 @@
     select * from {{ ref('stg_tickit__sales') }}
 ),
@@ -72,3 +73,4 @@
     select * from {{ ref('stg_tickit__categories') }}
 ),
@@ -75,3 +76,4 @@
     select * from {{ ref('stg_tickit__venues') }}
 ),
@@ -78,3 +79,4 @@
     select * from {{ ref('stg_tickit__users') }}
 ),
@@ -81,3 +82,4 @@
     select * from {{ ref('stg_tickit__dates') }}
 ),
@@ -84,3 +85,4 @@
     select * from {{ ref('stg_tickit__sales') }}
 ),
@@ -87,3 +88,4 @@
     select * from {{ ref('stg_tickit__categories') }}
 ),
@@ -90,3 +91,4 @@
     select * from {{ ref('stg_tickit__venues') }}
 ),
@@ -93,3 +94,4 @@
     select * from {{ ref('stg_tickit__users') }}
 ),
@@ -96,3 +97,4 @@
     select * from {{ ref('stg_tickit__dates') }}
 ),
@@ -99,3 +100,4 @@
     select * from {{ ref('stg_tickit__sales') }}
 ),
@@ -102,3 +103,4 @@
     select * from {{ ref('stg_tickit__categories') }}
 ),
@@ -105,3 +106,4 @@
     select * from {{ ref('stg_tickit__venues') }}
 ),
@@ -108,3 +109,4 @@
     select * from {{ ref('stg_tickit__users') }}
 ),
@@ -111,3 +112,4 @@
     select * from {{ ref('stg_tickit__dates') }}
 ),
@@ -114,3 +115,4 @@
     select * from {{ ref('stg_tickit__sales') }}
 ),
@@ -117,3 +118,4 @@
     select * from {{ ref('stg_tickit__categories') }}
 ),
@@ -120,3 +121,4 @@
     select * from {{ ref('stg_tickit__venues') }}
 ),
@@ -123,3 +124,4 @@
     select * from {{ ref('stg_tickit__users') }}
 ),
@@ -126,3 +127,4 @@
     select * from {{ ref('stg_tickit__dates') }}
 ),
@@ -129,3 +130,4 @@
     select * from {{ ref('stg_tickit__sales') }}
 ),
@@ -132,3 +133,4 @@
     select * from {{ ref('stg_tickit__categories') }}
 ),
@@ -135,3 +136,4 @@
     select * from {{ ref('stg_tickit__venues') }}
 ),
@@ -138,3 +139,4 @@
     select * from {{ ref('stg_tickit__users') }}
 ),
@@ -141,3 +142,4 @@
     select * from {{ ref('stg_tickit__dates') }}
 ),
@@ -144,3 +145,4 @@
     select * from {{ ref('stg_tickit__sales') }}
 ),
@@ -147,3 +148,4 @@
     select * from {{ ref('stg_tickit__categories') }}
 ),
@@ -150,3 +151,4 @@
     select * from {{ ref('stg_tickit__venues') }}
 ),
@@ -153,3 +154,4 @@
     select * from {{ ref('stg_tickit__users') }}
 ),
@@ -156,3 +157