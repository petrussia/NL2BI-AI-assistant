# b0_qwen_qwen2.5_7b_instruct_smoke10 Error Cases

|idx|question|db_id|generated_sql|executable|execution_match|error_type|
|---|---|---|---|---|---|---|
|6|Show the name and the release year of the song by the youngest singer.|concert_singer|SELECT s.Name AS Song_Name, s.Song_release_year <br>FROM singer s <br>JOIN singer_in_concert sc ON s.Singer_ID = sc.Singer_ID <br>WHERE s.Age = (SELECT MIN(Age) FROM singer);|True|False|result_mismatch|
|7|What are the names and release years for all the songs of the youngest singer?|concert_singer|SELECT Song_Name, Song_release_year <br>FROM singer <br>JOIN song_in_concert ON singer.Singer_ID = singer_in_concert.Singer_ID <br>WHERE Singer_ID = (<br>    SELECT Singer_ID <br>    FROM singer <br>    ORDER BY Age ASC <br>    LIMIT 1<br>);|False|False|OperationalError|
|8|What are all distinct countries where singers above age 20 are from?|concert_singer|SELECT DISTINCT T2.Country <br>FROM singer_in_concert AS T1 <br>JOIN singer AS T2 ON T1.Singer_ID = T2.Singer_ID <br>WHERE T2.Age > 20;|True|False|result_mismatch|
|9|What are  the different countries with singers above age 20?|concert_singer|SELECT DISTINCT T2.Country <br>FROM singer_in_concert AS T1 <br>JOIN singer AS T2 ON T1.Singer_ID = T2.Singer_ID <br>WHERE T2.Age > 20;|True|False|result_mismatch|
