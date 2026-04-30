# b0_llama_3p1_8b_instruct_multidb30 Error Cases

|idx|question|db_id|generated_sql|executable|execution_match|error_type|path|
|---|---|---|---|---|---|---|---|
|2|List the name, date and result of each battle.|battle_death|SELECT name, date, result FROM battle;|True|False|result_mismatch|direct_full_schema|
|7|How many countries does each continent have? List the continent id, continent name and the number of countries.|car_1|SELECT T1.Continent, COUNT(T2.CountryId) as CountryCount <br>FROM continents T1 <br>JOIN countries T2 ON T1.ContId = T2.ContinentId;|False|False|OperationalError|direct_full_schema|
|8|For each continent, list its id, name, and how many countries it has?|car_1|SELECT T1.ContId, T1.Continent, COUNT(T2.CountryId) FROM continents AS T1 INNER JOIN countries AS T2 ON T1.ContId = T2.ContinentId GROUP BY T1.ContId;|False|False|OperationalError|direct_full_schema|
|22|What is the average age of the dogs who have gone through any treatments?|dog_kennels|SELECT AVG(T1.age) <br>FROM Dogs AS T1 <br>JOIN Treatments AS T2 ON T1.dog_id = T2.dog_id;|True|False|result_mismatch|direct_full_schema|
|23|Find the average age of the dogs who went through treatments.|dog_kennels|SELECT AVG(T1.age) <br>FROM Dogs AS T1 <br>JOIN Treatments AS T2 ON T1.dog_id = T2.dog_id;|True|False|result_mismatch|direct_full_schema|
