# b0_spider_smoke25 Error Cases

|idx|question|db_id|gold_sql|generated_sql|executable|execution_match|error_type|
|---|---|---|---|---|---|---|---|
|16|What is the maximum capacity and the average of all stadiums ?|concert_singer|select max(capacity), average from stadium|SELECT MAX(Capacity), AVG(Average) FROM stadium;|True|False|result_mismatch|
