# b1_llama_3p1_8b_instruct_smoke25 Error Cases

|idx|question|db_id|generated_sql|executable|execution_match|error_type|path|
|---|---|---|---|---|---|---|---|
|6|Show the name and the release year of the song by the youngest singer.|concert_singer|SELECT T2.Name, T2.`Song_release_year` <br>FROM singer AS T1 <br>INNER JOIN concert AS T2 ON T1.Singer_ID = T2.Singer_ID <br>WHERE T1.Age = ( SELECT MIN(T1.Age) FROM singer AS T1 );|False|False|OperationalError|lex_linker|
|7|What are the names and release years for all the songs of the youngest singer?|concert_singer|SELECT T2.Name, T2.Song_Name, T2.Song_release_year <br>FROM singer AS T1 <br>JOIN singer AS T2 ON T1.Singer_ID = T2.Singer_ID <br>WHERE T1.Age = ( SELECT MIN(T1.Age) FROM singer AS T1 );|True|False|result_mismatch|lex_linker|
|10|Show all countries and the number of singers in each country.|concert_singer|SELECT T2.Country, COUNT(T1.Singer_ID) FROM singer_in_concert AS T1 INNER JOIN singer AS T2 ON T1.Singer_ID = T2.Singer_ID GROUP BY T2.Country;|True|False|result_mismatch|lex_linker|
|11|How many singers are from each country?|concert_singer|SELECT COUNT(Singer_ID), Country FROM singer GROUP BY Country;|True|False|result_mismatch|lex_linker|
|12|List all song names by singers above the average age.|concert_singer|SELECT T2.Song_Name <br>FROM singer AS T1 <br>JOIN concert_singer.stadium AS T2 ON T1.Singer_ID = T2.Singer_ID <br>WHERE T1.Age > ( SELECT AVG(Age) FROM singer );|False|False|OperationalError|lex_linker|
|16|What is the maximum capacity and the average of all stadiums ?|concert_singer|SELECT MAX(Capacity), AVG(Capacity) FROM stadium;|True|False|result_mismatch|lex_linker|
|23|For each stadium, how many concerts play there?|concert_singer|SELECT COUNT(concert_ID), T1.Name FROM stadium AS T1 INNER JOIN concert AS T2 ON T1.Stadium_ID = T2.Stadium_ID GROUP BY T1.Name;|True|False|result_mismatch|lex_linker|
