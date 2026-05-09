# B1 Spider Smoke10 Examples

|idx|question|db_id|selected_tables|gold_sql|generated_sql|executable|execution_match|error_type|
|---|---|---|---|---|---|---|---|---|
|0|How many singers do we have?|concert_singer|stadium, singer, concert, singer_in_concert|SELECT count(*) FROM singer|SELECT COUNT(*) FROM singer;|True|True||
|1|What is the total number of singers?|concert_singer|stadium, singer, concert, singer_in_concert|SELECT count(*) FROM singer|SELECT COUNT(*) FROM singer;|True|True||
|2|Show name, country, age for all singers ordered by age from the oldest to the youngest.|concert_singer|singer|SELECT name ,  country ,  age FROM singer ORDER BY age DESC|SELECT Name, Country, Age FROM singer ORDER BY Age DESC;|True|True||
|3|What are the names, countries, and ages for every singer in descending order of age?|concert_singer|singer, singer_in_concert|SELECT name ,  country ,  age FROM singer ORDER BY age DESC|SELECT Name, Country, Age FROM singer ORDER BY Age DESC;|True|True||
|4|What is the average, minimum, and maximum age of all singers from France?|concert_singer|singer|SELECT avg(age) ,  min(age) ,  max(age) FROM singer WHERE country  =  'France'|SELECT AVG(Age) AS Average_Age, MIN(Age) AS Minimum_Age, MAX(Age) AS Maximum_Age FROM singer WHERE Country = 'France';|True|True||
