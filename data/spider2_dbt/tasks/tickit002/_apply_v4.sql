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