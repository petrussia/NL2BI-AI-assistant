# b1_multidb30_v2 Error Cases

|idx|question|db_id|generated_sql|executable|execution_match|error_type|
|---|---|---|---|---|---|---|
|2|List the name, date and result of each battle.|battle_death|SELECT name, date, result FROM battle;|True|False|result_mismatch|
|8|For each continent, list its id, name, and how many countries it has?|car_1|SELECT Continent, COUNT(*) AS NumberOfCountries<br>FROM countries<br>GROUP BY Continent;|True|False|result_mismatch|
|16|Count the number of documents.|cre_Doc_Template_Mgt|SELECT COUNT(*) FROM Templates;|True|False|result_mismatch|
|22|What is the average age of the dogs who have gone through any treatments?|dog_kennels|SELECT AVG(age) FROM Dogs WHERE abandoned_yn = 'N';|True|False|result_mismatch|
|23|Find the average age of the dogs who went through treatments.|dog_kennels|SELECT AVG(age) FROM Dogs WHERE date_treatment IS NOT NULL;|False|False|OperationalError|
|26|Count the number of employees|employee_hire_evaluation|SELECT COUNT(*) FROM shop;|True|False|result_mismatch|
|29|What is the number of employees from each city?|employee_hire_evaluation|SELECT District, COUNT(*) AS Number_of_Employees FROM shop GROUP BY District;|True|False|result_mismatch|
