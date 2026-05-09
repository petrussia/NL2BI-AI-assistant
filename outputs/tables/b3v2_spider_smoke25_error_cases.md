# b3v2_spider_smoke25 Error Cases

|idx|question|db_id|generated_sql|executable|execution_match|error_type|path|
|---|---|---|---|---|---|---|---|
|16|What is the maximum capacity and the average of all stadiums ?|concert_singer|SELECT MAX(Capacity), AVG(Capacity) FROM stadium;|True|False|result_mismatch|b1_fallback_invalid_plan|
