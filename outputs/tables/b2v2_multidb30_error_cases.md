# b2v2_multidb30 Error Cases

|idx|question|db_id|generated_sql|executable|execution_match|error_type|path|
|---|---|---|---|---|---|---|---|
|2|List the name, date and result of each battle.|battle_death|SELECT name, date, result FROM battle;|True|False|result_mismatch|b1_fallback_invalid_plan|
|7|How many countries does each continent have? List the continent id, continent name and the number of countries.|car_1|SELECT c.Continent, COUNT(co.CountryId) AS NumberOfCountries<br>FROM continents c<br>LEFT JOIN countries co ON c.ContId = co.Continent<br>GROUP BY c.ContId;|True|False|result_mismatch|b1_fallback_invalid_plan|
|8|For each continent, list its id, name, and how many countries it has?|car_1|SELECT Continent, COUNT(*) AS NumberOfCountries<br>FROM countries<br>GROUP BY Continent;|True|False|result_mismatch|b1_fallback_invalid_plan|
|22|What is the average age of the dogs who have gone through any treatments?|dog_kennels|SELECT AVG(age) FROM Dogs WHERE abandoned_yn = 'N';|True|False|result_mismatch|b1_fallback_invalid_plan|
|23|Find the average age of the dogs who went through treatments.|dog_kennels|SELECT AVG(age) FROM Dogs WHERE date_treatment IS NOT NULL;|False|False|OperationalError|b1_fallback_invalid_plan|
|29|What is the number of employees from each city?|employee_hire_evaluation|SELECT District, COUNT(*) AS Number_of_Employees FROM shop GROUP BY District;|True|False|result_mismatch|b1_fallback_invalid_plan|
