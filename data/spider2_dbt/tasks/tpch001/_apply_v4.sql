- source_relation
+    columns:
+      - name: date
+        description: Date of the report
+      - name: page_id
+        description: Unique identifier for each Facebook page
+      - name: page_name
+        description: Name of the Facebook page
+      - name: total_likes
+        description: Total number of likes
+      - name: total_comments
+        description: Total number of comments
+
   - name: rollup_report
     description: Each record represents a post from a social media account
     tests:
@@ -28,6 +49,7 @@
         - post_id
         - platform
         - source_relation
+        - date
         - created_timestamp
         - post_message
         - post_url
```