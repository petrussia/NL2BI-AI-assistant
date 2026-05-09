# b2v2_qwen2p5_coder_14b_smoke25 Error Cases

|idx|question|db_id|generated_sql|executable|execution_match|error_type|path|
|---|---|---|---|---|---|---|---|
|6|Show the name and the release year of the song by the youngest singer.|concert_singer|SELECT Name, Song_release_year FROM singer WHERE Age = (SELECT MIN(Age) FROM singer);|True|False|result_mismatch|plan_then_sql|
|7|What are the names and release years for all the songs of the youngest singer?|concert_singer|SELECT Name, Song_release_year FROM singer WHERE Age = (SELECT MIN(Age) FROM singer);|True|False|result_mismatch|plan_then_sql|
|16|What is the maximum capacity and the average of all stadiums ?|concert_singer|SELECT MAX(Capacity) AS Max_Capacity, AVG(Average) AS Avg_Average FROM stadium;|True|False|result_mismatch|b1_fallback_invalid_plan|
