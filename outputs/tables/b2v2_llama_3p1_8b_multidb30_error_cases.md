# b2v2_llama_3p1_8b_multidb30 Error Cases

|idx|question|db_id|generated_sql|executable|execution_match|error_type|path|
|---|---|---|---|---|---|---|---|
|0|How many ships ended up being 'Captured'?|battle_death|SELECT id FROM ship WHERE disposition_of_ship = 'Captured';|True|False|result_mismatch|plan_then_sql|
|2|List the name, date and result of each battle.|battle_death|SELECT name, date, result FROM battle;|True|False|result_mismatch|b1_fallback_invalid_plan|
|7|How many countries does each continent have? List the continent id, continent name and the number of countries.|car_1|SELECT T1.Continent, COUNT(T2.CountryId) as CountryCount <br>FROM continents T1 <br>JOIN countries T2 ON T1.ContId = T2.ContinentId <br>GROUP BY T1.Continent;|False|False|OperationalError|b1_fallback_invalid_plan|
|8|For each continent, list its id, name, and how many countries it has?|car_1|SELECT Continent, COUNT(CountryId) as CountryCount, CountryName FROM countries GROUP BY Continent;|True|False|result_mismatch|b1_fallback_invalid_plan|
|22|What is the average age of the dogs who have gone through any treatments?|dog_kennels|SELECT DISTINCT AVG(Dogs.age) FROM Dogs INNER JOIN Treatments ON Dogs.dog_id = Treatments.dog_id WHERE Dogs.dog_id = (SELECT treatment_id FROM Treatments);|True|False|result_mismatch|plan_then_sql|
|23|Find the average age of the dogs who went through treatments.|dog_kennels|SELECT AVG(T1.age) FROM Dogs AS T1 INNER JOIN Treatments AS T2 ON T1.dog_id = T2.dog_id;|True|False|result_mismatch|b1_fallback_invalid_plan|
|24|Which professionals live in the state of Indiana or have done treatment on more than 2 treatments? List his or her id, last name and cell phone.|dog_kennels|SELECT DISTINCT p.professional_id, p.last_name, p.cell_number <br>FROM Professionals p <br>INNER JOIN Treatments t ON p.professional_id = t.professional_id <br>WHERE (SELECT COUNT(treatment_id) FROM Treatments WHERE professional_id = p.professional_id) > 2 OR p.state = 'Indiana';|True|False|result_mismatch|plan_then_sql|
|29|What is the number of employees from each city?|employee_hire_evaluation|SELECT Location, COUNT(*) FROM shop GROUP BY Location;|True|False|result_mismatch|b1_fallback_invalid_plan|
