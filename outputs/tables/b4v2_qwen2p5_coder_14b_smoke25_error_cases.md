# b4v2_qwen2p5_coder_14b_smoke25 Error Cases

|idx|question|db_id|generated_sql|executable|execution_match|error_type|path|
|---|---|---|---|---|---|---|---|
|11|How many singers are from each country?|concert_singer|SELECT COUNT(*) ,  Country FROM singer GROUP BY Country;|True|False|result_mismatch|multicand:consistency_winner|
|16|What is the maximum capacity and the average of all stadiums ?|concert_singer|SELECT MAX(Capacity) AS Max_Capacity, AVG(Average) AS Avg_Average FROM stadium;|True|False|result_mismatch|b1_fallback_invalid_plan|
|17|What is the average and maximum capacities for all stadiums ?|concert_singer|SELECT Average, Highest FROM stadium;|True|False|result_mismatch|b1_fallback_invalid_plan|
