# b0_qwen_qwen2.5_7b_instruct_smoke25 Error Cases

|idx|question|db_id|generated_sql|executable|execution_match|error_type|path|
|---|---|---|---|---|---|---|---|
|6|Show the name and the release year of the song by the youngest singer.|concert_singer|SELECT Song_Name, Song_release_year <br>FROM singer <br>JOIN song ON singer.Singer_ID = song.Singer_ID <br>WHERE Age = (SELECT MIN(Age) FROM singer);|False|False|OperationalError|direct_full_schema|
|7|What are the names and release years for all the songs of the youngest singer?|concert_singer|SELECT Song_Name, Song_release_year <br>FROM singer <br>JOIN song ON singer.Singer_ID = song.Singer_ID <br>WHERE Age = (SELECT MIN(Age) FROM singer);|False|False|OperationalError|direct_full_schema|
|12|List all song names by singers above the average age.|concert_singer|SELECT s.Song_Name <br>FROM singer s <br>JOIN singer_in_concert sc ON s.Singer_ID = sc.Singer_ID <br>WHERE s.Age > (SELECT AVG(Age) FROM singer);|True|False|result_mismatch|direct_full_schema|
|13|What are all the song names by singers who are older than average?|concert_singer|SELECT s.Song_Name <br>FROM singer s <br>JOIN singer_in_concert sc ON s.Singer_ID = sc.Singer_ID <br>WHERE s.Age > (SELECT AVG(Age) FROM singer);|True|False|result_mismatch|direct_full_schema|
|16|What is the maximum capacity and the average of all stadiums ?|concert_singer|SELECT MAX(Capacity) AS Max_Capacity, AVG(Capacity) AS Avg_Capacity FROM stadium;|True|False|result_mismatch|direct_full_schema|
|22|Show the stadium name and the number of concerts in each stadium.|concert_singer|SELECT s.Name, COUNT(c.concert_ID) AS Number_of_Concerts<br>FROM stadium s<br>LEFT JOIN concert c ON s.Stadium_ID = c.Stadium_ID<br>GROUP BY s.Stadium_ID;|True|False|result_mismatch|direct_full_schema|
|23|For each stadium, how many concerts play there?|concert_singer|SELECT Stadium_ID, COUNT(concert_ID) AS Number_of_Concerts<br>FROM concert<br>GROUP BY Stadium_ID;|True|False|result_mismatch|direct_full_schema|
