# b2v1_spider_smoke10 Error Cases

|idx|question|db_id|plan_valid|generated_sql|executable|execution_match|error_type|
|---|---|---|---|---|---|---|---|
|6|Show the name and the release year of the song by the youngest singer.|concert_singer|True|SELECT Name, Song_release_year FROM singer WHERE Age = (SELECT MIN(Age) FROM singer);|True|False|result_mismatch|
|7|What are the names and release years for all the songs of the youngest singer?|concert_singer|True|SELECT Name, Song_release_year FROM singer WHERE Singer_ID = (SELECT Singer_ID FROM singer ORDER BY Age ASC LIMIT 1);|True|False|result_mismatch|
|8|What are all distinct countries where singers above age 20 are from?|concert_singer|False||False|False|plan_invalid|
|9|What are  the different countries with singers above age 20?|concert_singer|False||False|False|plan_invalid|
