_metrics.device_installs,
         install_metrics.device_uninstalls,
         install_metrics.device_upgrades,
         install_metrics.user_installs,
         install_metrics.user_uninstalls,
+        ratings_metrics.average_total_rating,
         store_performance.store_listing_acquisitions,
         store_performance.store_listing_visitors,
         store_performance.store_listing_conversion_rate,
         store_performance.total_store_acquisitions,
         store_performance.total_store_visitors,
         crashes.daily_crashes,
         crashes.daily_anrs
     from install_metrics
     left join ratings_metrics on install_metrics.source_relation = ratings_metrics.source_relation and install_metrics.date_day = ratings_metrics.date_day and install_metrics.package_name = ratings_metrics.package_name
     left join crashes on install_metrics.source_relation = crashes.source_relation and install_metrics.date_day = crashes.date_day and install_metrics.package_name = crashes.package_name
     left join store_performance on install_metrics.source_relation = store_performance.source_relation and install_metrics.date_day = store_performance.date_day and install_metrics.package_name = store_performance.package_name
 )
 select * from overview_join
```