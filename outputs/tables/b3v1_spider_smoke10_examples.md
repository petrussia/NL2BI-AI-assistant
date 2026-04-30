# b3v1_spider_smoke10 Examples

|idx|question|db_id|plan_valid|generated_sql|executable|execution_match|error_type|
|---|---|---|---|---|---|---|---|
|0|How many singers do we have?|concert_singer|True|SELECT COUNT(*) FROM singer;|True|True||
|1|What is the total number of singers?|concert_singer|True|SELECT COUNT(*) FROM singer;|True|True||
|2|Show name, country, age for all singers ordered by age from the oldest to the youngest.|concert_singer|False||False|False|plan_invalid|
|3|What are the names, countries, and ages for every singer in descending order of age?|concert_singer|False||False|False|plan_invalid|
|4|What is the average, minimum, and maximum age of all singers from France?|concert_singer|True|SELECT avg(Age), min(Age), max(Age) FROM singer WHERE Country = 'France';|True|True||
