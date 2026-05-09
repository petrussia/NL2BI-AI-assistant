# b1_llama_3p1_8b_instruct_smoke25 Examples

|idx|question|db_id|generated_sql|executable|execution_match|error_type|path|
|---|---|---|---|---|---|---|---|
|0|How many singers do we have?|concert_singer|SELECT COUNT(Singer_ID) FROM singer;|True|True||lex_linker|
|1|What is the total number of singers?|concert_singer|SELECT COUNT(Singer_ID) FROM singer;|True|True||lex_linker|
|2|Show name, country, age for all singers ordered by age from the oldest to the youngest.|concert_singer|SELECT Name, Country, Age FROM singer ORDER BY Age DESC;|True|True||lex_linker|
|3|What are the names, countries, and ages for every singer in descending order of age?|concert_singer|SELECT Name, Country, Age FROM singer ORDER BY Age DESC;|True|True||lex_linker|
|4|What is the average, minimum, and maximum age of all singers from France?|concert_singer|SELECT AVG(Age), MIN(Age), MAX(Age) FROM singer WHERE Country = 'France';|True|True||lex_linker|
