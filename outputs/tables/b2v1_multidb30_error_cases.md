# b2v1_multidb30 Error Cases

|idx|question|db_id|plan_valid|generated_sql|executable|execution_match|error_type|
|---|---|---|---|---|---|---|---|
|2|List the name, date and result of each battle.|battle_death|True|SELECT name, date, result FROM battle;|True|False|result_mismatch|
|7|How many countries does each continent have? List the continent id, continent name and the number of countries.|car_1|True|SELECT ContId, Continent, COUNT(CountryId) <br>FROM continents <br>JOIN countries ON Continents.ContId = Countries.Continent <br>GROUP BY ContId, Continent;|False|False|OperationalError|
|8|For each continent, list its id, name, and how many countries it has?|car_1|True|SELECT Continent, COUNT(*) <br>FROM countries <br>GROUP BY Continent;|True|False|result_mismatch|
|16|Count the number of documents.|cre_Doc_Template_Mgt|True|SELECT COUNT(Template_ID) FROM Templates;|True|False|result_mismatch|
|20|Which states have both owners and professionals living there?|dog_kennels|False||False|False|plan_invalid|
|21|Find the states where both owners and professionals live.|dog_kennels|False||False|False|plan_invalid|
|22|What is the average age of the dogs who have gone through any treatments?|dog_kennels|True|SELECT AVG(age) FROM Dogs;|True|False|result_mismatch|
|23|Find the average age of the dogs who went through treatments.|dog_kennels|True|SELECT AVG(age) FROM Dogs;|True|False|result_mismatch|
|24|Which professionals live in the state of Indiana or have done treatment on more than 2 treatments? List his or her id, last name and cell phone.|dog_kennels|True|SELECT Professional_id, last_name, cell_number <br>FROM Professionals <br>JOIN Treatments ON Professionals.professional_id = Treatments.professional_id <br>WHERE state = 'Indiana' <br>AND professional_id >= (SELECT COUNT(*) FROM Treatments GROUP BY professional_id HAVING COUNT(*) > 2);|False|False|OperationalError|
|26|Count the number of employees|employee_hire_evaluation|True|SELECT COUNT(*) FROM shop;|True|False|result_mismatch|
|29|What is the number of employees from each city?|employee_hire_evaluation|True|SELECT Location, SUM(Number_products) AS Total_Number_of_Employees<br>FROM shop<br>GROUP BY Location;|True|False|result_mismatch|
