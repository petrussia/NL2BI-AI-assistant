# b1_qwen_qwen2.5_7b_instruct_multidb30 Error Cases

|idx|question|db_id|generated_sql|executable|execution_match|error_type|path|
|---|---|---|---|---|---|---|---|
|2|List the name, date and result of each battle.|battle_death|SELECT name, date, result FROM battle;|True|False|result_mismatch|lex_linker|
|3|What is maximum and minimum death toll caused each time?|battle_death|SELECT MIN(killed) AS min_death_toll, MAX(killed) AS max_death_toll<br>FROM death;|True|False|result_mismatch|lex_linker|
|8|For each continent, list its id, name, and how many countries it has?|car_1|SELECT Continent, COUNT(CountryId) AS NumberOfCountries<br>FROM countries<br>GROUP BY Continent;|True|False|result_mismatch|lex_linker|
|16|Count the number of documents.|cre_Doc_Template_Mgt|SELECT COUNT(*) AS Document_Count FROM Templates;|True|False|result_mismatch|lex_linker|
|22|What is the average age of the dogs who have gone through any treatments?|dog_kennels|SELECT AVG(age) AS average_age<br>FROM Dogs<br>WHERE date_departed IS NOT NULL;|True|False|result_mismatch|lex_linker|
|23|Find the average age of the dogs who went through treatments.|dog_kennels|SELECT AVG(age) AS average_age<br>FROM Dogs<br>WHERE date_departed IS NOT NULL;|True|False|result_mismatch|lex_linker|
|24|Which professionals live in the state of Indiana or have done treatment on more than 2 treatments? List his or her id, last name and cell phone.|dog_kennels|SELECT professional_id, last_name, cell_number <br>FROM Professionals <br>WHERE state = 'Indiana' <br>UNION <br>SELECT professional_id, last_name, cell_number <br>FROM Treatments <br>GROUP BY professional_id <br>HAVING COUNT(treatment_id) > 2;|False|False|OperationalError|lex_linker|
|26|Count the number of employees|employee_hire_evaluation|SELECT COUNT(*) AS Employee_Count FROM shop;|True|False|result_mismatch|lex_linker|
|29|What is the number of employees from each city?|employee_hire_evaluation|SELECT COUNT(*), Location <br>FROM shop <br>GROUP BY Location;|True|False|result_mismatch|lex_linker|
