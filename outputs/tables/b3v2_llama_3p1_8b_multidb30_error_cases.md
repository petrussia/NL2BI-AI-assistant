# b3v2_llama_3p1_8b_multidb30 Error Cases

|idx|question|db_id|generated_sql|executable|execution_match|error_type|path|
|---|---|---|---|---|---|---|---|
|2|List the name, date and result of each battle.|battle_death|SELECT name, date, result FROM battle;|True|False|result_mismatch|b1_fallback_invalid_plan|
|7|How many countries does each continent have? List the continent id, continent name and the number of countries.|car_1|SELECT T1.Continent, COUNT(T2.CountryId) as CountryCount <br>FROM continents T1 <br>JOIN countries T2 ON T1.ContId = T2.ContinentId <br>GROUP BY T1.Continent;|False|False|OperationalError|b1_fallback_invalid_plan|
|8|For each continent, list its id, name, and how many countries it has?|car_1|SELECT Continent, COUNT(CountryId) as CountryCount, CountryName FROM countries GROUP BY Continent;|True|False|result_mismatch|b1_fallback_invalid_plan|
|9|How many countries are listed?|car_1|SELECT DISTINCT CountryId FROM countries;|True|False|result_mismatch|plan_then_sql|
|16|Count the number of documents.|cre_Doc_Template_Mgt|SELECT DISTINCT Template_ID FROM Templates;|True|False|result_mismatch|plan_then_sql|
|22|What is the average age of the dogs who have gone through any treatments?|dog_kennels|SELECT AVG(T1.age) FROM Dogs AS T1 INNER JOIN Treatments AS T2 ON T1.dog_id = T2.dog_id;|True|False|result_mismatch|b1_fallback_invalid_plan|
|23|Find the average age of the dogs who went through treatments.|dog_kennels|SELECT AVG(T1.age) FROM Dogs AS T1 INNER JOIN Treatments AS T2 ON T1.dog_id = T2.dog_id;|True|False|result_mismatch|b1_fallback_invalid_plan|
|24|Which professionals live in the state of Indiana or have done treatment on more than 2 treatments? List his or her id, last name and cell phone.|dog_kennels|SELECT T1.professional_id, T1.last_name, T1.cell_number <br>FROM Professionals AS T1 <br>INNER JOIN Treatments AS T2 ON T1.professional_id = T2.professional_id <br>WHERE T1.state = 'Indiana' <br>OR T2.treatment_id IN (SELECT treatment_id <br>                       FROM Treatments <br>                       GROUP BY treatment_id <br>                       HAVING COUNT(treatment_id) > 2);|True|False|result_mismatch|b1_fallback_invalid_plan|
|26|Count the number of employees|employee_hire_evaluation|SELECT DISTINCT COUNT(*) FROM shop;|True|False|result_mismatch|plan_then_sql|
|29|What is the number of employees from each city?|employee_hire_evaluation|SELECT DISTINCT Location FROM shop;|True|False|result_mismatch|plan_then_sql|
