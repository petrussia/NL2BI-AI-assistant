# b1_qwen2p5_coder_14b_instruct_multidb30 Error Cases

|idx|question|db_id|generated_sql|executable|execution_match|error_type|
|---|---|---|---|---|---|---|
|2|List the name, date and result of each battle.|battle_death|SELECT name, date, result FROM battle;|True|False|result_mismatch|
|7|How many countries does each continent have? List the continent id, continent name and the number of countries.|car_1|SELECT c.ContId, con.Continent, COUNT(c.CountryId) AS NumberOfCountries<br>FROM countries c<br>JOIN continents con ON c.Continent = con.ContId<br>GROUP BY c.ContId, con.Continent;|False|False|OperationalError|
|8|For each continent, list its id, name, and how many countries it has?|car_1|SELECT Continent, COUNT(*) AS CountryCount <br>FROM countries <br>GROUP BY Continent;|True|False|result_mismatch|
|16|Count the number of documents.|cre_Doc_Template_Mgt|SELECT COUNT(*) FROM Templates;|True|False|result_mismatch|
|24|Which professionals live in the state of Indiana or have done treatment on more than 2 treatments? List his or her id, last name and cell phone.|dog_kennels|SELECT DISTINCT p.professional_id, p.last_name, p.cell_number<br>FROM Professionals p<br>JOIN Treatments t ON p.professional_id = t.professional_id<br>WHERE p.state = 'Indiana'<br>UNION<br>SELECT p.professional_id, p.last_name, p.cell_number<br>FROM Professionals p<br>JOIN Treatments t ON p.professional_id = t.professional_id<br>GROUP BY p.professional_id<br>HAVING COUNT(t.treatment_id) > 2;|True|False|result_mismatch|
|26|Count the number of employees|employee_hire_evaluation|SELECT COUNT(*) FROM employee_hire_evaluation;|False|False|OperationalError|
|29|What is the number of employees from each city?|employee_hire_evaluation|SELECT Location, COUNT(*) AS Number_of_Employees<br>FROM shop<br>GROUP BY Location;|True|False|result_mismatch|
