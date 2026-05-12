```diff
--- a/models/mart/fct_match.sql
+++ b/models/mart/fct_match.sql
@@ -1,6 +1,7 @@
 with matches as (
   select *
     from {{ ref('stg_atp_tour__matches') }}
+),
+tournaments as (
   select *
     from {{ ref('stg_atp_tour__matches') }}
 ),
 players as (
   select *
     from {{ ref('stg_atp_tour__players') }}
@@ -14,6 +15,14 @@ with matches as (
     from {{ ref('stg_atp_tour__matches') }}
 ),
 players as (
   select *
     from {{ ref('stg_atp_tour__players') }}
+),
+tournament_details as (
+  select 
+    tournament_id,
+    tournament_name,
+    tournament_date,
+    surface,
+    draw_size
+  from {{ ref('stg_atp_tour__matches') }}
 )
 , ref_unknown_record as (
 	select *
 		from {{ ref('ref_unknown_values') }}
@@ -22,6 +31,14 @@ with matches as (
     from {{ ref('stg_atp_tour__matches') }}
 ),
 players as (
   select *
     from {{ ref('stg_atp_tour__players') }}
+),
+tournament_details as (
+  select 
+    tournament_id,
+    tournament_name,
+    tournament_date,
+    surface,
+    draw_size
+  from {{ ref('stg_atp_tour__matches') }}
 )
 , match as (
 	select 
@@ -30,6 +47,14 @@ with matches as (
     from {{ ref('stg_atp_tour__matches') }}
 ),
 players as (
   select *
     from {{ ref('stg_atp_tour__players') }}
+),
+tournament_details as (
+  select 
+    tournament_id,
+    tournament_name,
+    tournament_date,
+    surface,
+    draw_size
+  from {{ ref('stg_atp_tour__matches') }}
 )
 , match as (
 	select 
@@ -40,6 +65,14 @@ with matches as (
     from {{ ref('stg_atp_tour__matches') }}
 ),
 players as (
   select *
     from {{ ref('stg_atp_tour__players') }}
+),
+tournament_details as (
+  select 
+    tournament_id,
+    tournament_name,
+    tournament_date,
+    surface,
+    draw_size
+  from {{ ref('stg_atp_tour__matches') }}
 )
 , match as (
 	select 
@@ -50,6 +83,14 @@ with matches as (
     from {{ ref('stg_atp_tour__matches') }}
 ),
 players as (
   select *
     from {{ ref('stg_atp_tour__players') }}
+),
+tournament_details as (
+  select 
+    tournament_id,
+    tournament_name,
+    tournament_date,
+    surface,
+    draw_size
+  from {{ ref('stg_atp_tour__matches') }}
 )
 , match as (
 	select 
@@ -60,6 +101,14 @@ with matches as (
     from {{ ref('stg_atp_tour__matches') }}
 ),
 players as (
   select *
     from {{ ref('stg_atp_tour__players') }}
+),
+tournament_details as (
+  select 
+    tournament_id,
+    tournament_name,
+    tournament_date,
+    surface,
+    draw_size
+  from {{ ref('stg_atp_tour__matches') }}
 )
 , match as (
 	select 
@@ -70,6 +121,14 @@ with matches as (
     from {{ ref('stg_atp_tour__matches') }}
 ),
 players as (
   select *
     from {{ ref('stg_atp_tour__players') }}
+),
+tournament_details as (
+  select 
+    tournament_id,
+    tournament_name,
+    tournament_date,
+    surface,
+    draw_size
+  from {{ ref('stg_atp_tour__matches') }}
 )
 , match as (
 	select 
@@ -80,6 +141,14 @@ with matches as (
     from {{ ref('stg_atp_tour__matches') }}
 ),
 players as (
   select *
     from {{ ref('stg_atp_tour__players') }}
+),
+tournament_details as (
+  select 
+    tournament_id,
+    tournament_name,
+    tournament_date,
+    surface,
+    draw_size
+  from {{ ref('stg_atp_tour__matches') }}
 )
 , match as (
 	select 
@@ -90,6 +161,14 @@ with matches as (
     from {{ ref('stg_atp_tour__matches') }}
 ),
 players as (
   select *
     from {{ ref('stg_atp_tour__players') }}
+),
+tournament_details as (
+  select 
+    tournament_id,
+    tournament_name,
+    tournament_date,
+    surface,
+    draw_size
+  from {{ ref('stg_atp_tour__matches') }}
 )
 , match as (
 	select 
@@ -100,6 +181,14 @@ with matches as (
     from {{ ref('stg_atp_tour__matches') }}
 ),
 players as (
   select *
     from {{ ref('stg_atp_tour__players') }}
+),
+tournament_details as (
+  select 
+    tournament_id,
+    tournament_name,
+    tournament_date,
+    surface,
+    draw_size
+  from {{ ref('stg_atp_tour__matches') }}
 )
 , match as (
 	select 
@@ -110,6 +191,14 @@ with matches as (
     from {{ ref('stg_atp_tour__matches') }}
 ),
 players as (
   select *
     from {{ ref('stg_atp_tour__players') }}
+),
+tournament_details as (
+  select 
+    tournament_id,
+    tournament_name,
+    tournament_date,
+    surface,
+    draw_size
+  from {{ ref('stg_atp_tour__matches') }}
 )
 , match as (
 	select 
@@ -120,6 +201,14 @@ with matches as (
     from {{ ref('stg_atp_tour__matches') }}
 ),
 players as (
   select *
     from {{ ref('stg_atp_tour__players') }}
+),
+tournament_details as (
+  select 
+    tournament_id,
+    tournament_name,
+    tournament_date,
+    surface,
+    draw_size
+  from {{ ref('stg_atp_tour__matches') }}
 )
 , match as (
 	select 
@@ -130,6 +211,14 @@ with matches as (
     from