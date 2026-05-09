# b0_llama_3p1_8b_instruct_smoke10 Error Cases

|idx|question|db_id|generated_sql|executable|execution_match|error_type|
|---|---|---|---|---|---|---|
|6|Show the name and the release year of the song by the youngest singer.|concert_singer|SELECT T2.Name, T2.`Song_release_year` <br>FROM singer AS T1 <br>INNER JOIN singer AS T2 ON T1.Singer_ID = T2.Singer_ID <br>WHERE T1.Age = ( SELECT MIN(T1.Age) FROM singer AS T1 );|True|False|result_mismatch|
|7|What are the names and release years for all the songs of the youngest singer?|concert_singer|SELECT T2.Name, T2.Song_Name, T2.Song_release_year <br>FROM singer AS T1 <br>INNER JOIN singer AS T2 ON T1.Singer_ID = T2.Singer_ID <br>WHERE T1.Age = ( SELECT MIN(T1.Age) FROM singer AS T1 );|True|False|result_mismatch|
