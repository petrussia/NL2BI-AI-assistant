# b3v2_qwen2p5_coder_14b_multidb30 Error Cases

|idx|question|db_id|generated_sql|executable|execution_match|error_type|path|
|---|---|---|---|---|---|---|---|
|2|List the name, date and result of each battle.|battle_death|SELECT name, date, result FROM battle;|True|False|result_mismatch|plan_then_sql|
|8|For each continent, list its id, name, and how many countries it has?|car_1|SELECT Continent, COUNT(*) <br>FROM countries <br>GROUP BY Continent;|True|False|result_mismatch|plan_then_sql|
|16|Count the number of documents.|cre_Doc_Template_Mgt|SELECT COUNT(*) FROM Templates;|True|False|result_mismatch|plan_then_sql|
|26|Count the number of employees|employee_hire_evaluation|SELECT COUNT(*) FROM shop;|True|False|result_mismatch|plan_then_sql|
|29|What is the number of employees from each city?|employee_hire_evaluation|SELECT Location, COUNT(*) AS Number_of_Employees <br>FROM shop <br>GROUP BY Location;|True|False|result_mismatch|plan_then_sql|
