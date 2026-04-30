# b1_qwen_qwen2.5_7b_instruct_smoke25 Error Cases

|idx|question|db_id|generated_sql|executable|execution_match|error_type|path|
|---|---|---|---|---|---|---|---|
|16|What is the maximum capacity and the average of all stadiums ?|concert_singer|SELECT MAX(Capacity) AS Max_Capacity, AVG(Capacity) AS Avg_Capacity FROM stadium;|True|False|result_mismatch|lex_linker|
|19|What is the name and capacity for the stadium with the highest average attendance?|concert_singer|SELECT Name, Capacity <br>FROM stadium <br>WHERE Stadium_ID = (SELECT Stadium_ID FROM concert WHERE Year IN (SELECT Year FROM concert GROUP BY Year ORDER BY AVG(Average) DESC LIMIT 1));|False|False|OperationalError|lex_linker|
|22|Show the stadium name and the number of concerts in each stadium.|concert_singer|SELECT s.Name, COUNT(c.concert_ID) AS Number_of_Concerts<br>FROM stadium s<br>LEFT JOIN concert c ON s.Stadium_ID = c.Stadium_ID<br>GROUP BY s.Stadium_ID;|True|False|result_mismatch|lex_linker|
|23|For each stadium, how many concerts play there?|concert_singer|SELECT Stadium_ID, COUNT(concert_ID) AS Number_of_Concerts<br>FROM concert<br>GROUP BY Stadium_ID;|True|False|result_mismatch|lex_linker|
