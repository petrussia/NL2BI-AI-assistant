# b2v2_qwen2p5_coder_14b_smoke10 Error Cases

|idx|question|db_id|generated_sql|executable|execution_match|error_type|path|
|---|---|---|---|---|---|---|---|
|6|Show the name and the release year of the song by the youngest singer.|concert_singer|SELECT Name, Song_release_year FROM singer WHERE Age = (SELECT MIN(Age) FROM singer);|True|False|result_mismatch|plan_then_sql|
|7|What are the names and release years for all the songs of the youngest singer?|concert_singer|SELECT Name, Song_release_year FROM singer WHERE Age = (SELECT MIN(Age) FROM singer);|True|False|result_mismatch|plan_then_sql|
