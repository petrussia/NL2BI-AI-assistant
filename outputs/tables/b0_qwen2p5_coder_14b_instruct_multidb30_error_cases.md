# b0_qwen2p5_coder_14b_instruct_multidb30 Error Cases

|idx|question|db_id|generated_sql|executable|execution_match|error_type|
|---|---|---|---|---|---|---|
|2|List the name, date and result of each battle.|battle_death|SELECT name, date, result FROM battle;|True|False|result_mismatch|
|22|What is the average age of the dogs who have gone through any treatments?|dog_kennels|SELECT AVG(D.age) <br>FROM Dogs D <br>JOIN Treatments T ON D.dog_id = T.dog_id;|True|False|result_mismatch|
|23|Find the average age of the dogs who went through treatments.|dog_kennels|SELECT AVG(D.age) <br>FROM Dogs D <br>JOIN Treatments T ON D.dog_id = T.dog_id;|True|False|result_mismatch|
|29|What is the number of employees from each city?|employee_hire_evaluation|SELECT City, COUNT(*) AS Number_of_Employees<br>FROM employee<br>GROUP BY City;|True|False|result_mismatch|
