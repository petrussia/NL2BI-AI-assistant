# b3_spider_smoke10 Error Cases

|idx|question|db_id|plan_valid|generated_sql|executable|execution_match|error_type|
|---|---|---|---|---|---|---|---|
|2|Show name, country, age for all singers ordered by age from the oldest to the youngest.|concert_singer|False||False|False|plan_invalid|
|3|What are the names, countries, and ages for every singer in descending order of age?|concert_singer|False||False|False|plan_invalid|
|4|What is the average, minimum, and maximum age of all singers from France?|concert_singer|False||False|False|plan_invalid|
|5|What is the average, minimum, and maximum age for all French singers?|concert_singer|False||False|False|plan_invalid|
|6|Show the name and the release year of the song by the youngest singer.|concert_singer|False||False|False|plan_invalid|
|7|What are the names and release years for all the songs of the youngest singer?|concert_singer|False||False|False|plan_invalid|
|8|What are all distinct countries where singers above age 20 are from?|concert_singer|False||False|False|plan_invalid|
|9|What are  the different countries with singers above age 20?|concert_singer|False||False|False|plan_invalid|
