# b3v2_spider_smoke10 Error Cases

|idx|question|db_id|generated_sql|executable|execution_match|error_type|path|
|---|---|---|---|---|---|---|---|
|4|What is the average, minimum, and maximum age of all singers from France?|concert_singer|SELECT MIN(Age) AS Min_Age, MAX(Age) AS Max_Age, AVG(Age) AS Avg_Age FROM singer WHERE Country = 'France';|True|False|result_mismatch|b1_fallback_invalid_plan|
|5|What is the average, minimum, and maximum age for all French singers?|concert_singer|SELECT MIN(Age) AS Min_Age, MAX(Age) AS Max_Age, AVG(Age) AS Avg_Age FROM singer WHERE Country = 'France';|True|False|result_mismatch|b1_fallback_invalid_plan|
