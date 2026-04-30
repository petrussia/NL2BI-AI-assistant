# b0_multidb30_v2 Error Cases

|idx|question|db_id|generated_sql|executable|execution_match|error_type|
|---|---|---|---|---|---|---|
|2|List the name, date and result of each battle.|battle_death|SELECT name, date, result FROM battle;|True|False|result_mismatch|
|29|What is the number of employees from each city?|employee_hire_evaluation|SELECT employee.City, COUNT(employee.Employee_ID) AS Number_of_Employees<br>FROM employee<br>GROUP BY employee.City;|True|False|result_mismatch|
