# b2v2_qwen_qwen2.5_7b_instruct_smoke25 Error Cases

|idx|question|db_id|generated_sql|executable|execution_match|error_type|path|
|---|---|---|---|---|---|---|---|
|16|What is the maximum capacity and the average of all stadiums ?|concert_singer|SELECT MAX(Capacity) AS Max_Capacity, AVG(Capacity) AS Avg_Capacity FROM stadium;|True|False|result_mismatch|b1_fallback_invalid_plan|
|19|What is the name and capacity for the stadium with the highest average attendance?|concert_singer|SELECT Name, Capacity <br>FROM stadium <br>WHERE Stadium_ID = (SELECT Stadium_ID FROM concert WHERE Year IN (SELECT Year FROM concert GROUP BY Year ORDER BY AVG(Average) DESC LIMIT 1));|False|False|OperationalError|b1_fallback_invalid_plan|
|23|For each stadium, how many concerts play there?|concert_singer|SELECT stadium.Name, COUNT(concert.concert_ID) AS Concert_Count <br>FROM stadium <br>JOIN concert ON stadium.Stadium_ID = concert.Stadium_ID <br>JOIN singer_in_concert ON concert.concert_ID = singer_in_concert.concert_ID <br>GROUP BY stadium.Stadium_ID;|True|False|result_mismatch|plan_then_sql|
