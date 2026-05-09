# b0_qwen_qwen2.5_7b_instruct_multidb30 Error Cases

|idx|question|db_id|generated_sql|executable|execution_match|error_type|path|
|---|---|---|---|---|---|---|---|
|2|List the name, date and result of each battle.|battle_death|SELECT name, date, result FROM battle;|True|False|result_mismatch|direct_full_schema|
|3|What is maximum and minimum death toll caused each time?|battle_death|SELECT MIN(killed + injured) AS min_toll, MAX(killed + injured) AS max_toll<br>FROM death;|True|False|result_mismatch|direct_full_schema|
|20|Which states have both owners and professionals living there?|dog_kennels|SELECT O.state, P.state<br>FROM Owners O<br>JOIN Professionals P ON O.state = P.state<br>GROUP BY O.state, P.state<br>HAVING COUNT(DISTINCT O.owner_id) > 0 AND COUNT(DISTINCT P.professional_id) > 0;|True|False|result_mismatch|direct_full_schema|
|22|What is the average age of the dogs who have gone through any treatments?|dog_kennels|SELECT AVG(Dogs.age) AS average_age<br>FROM Dogs<br>JOIN Treatments ON Dogs.dog_id = Treatments.dog_id;|True|False|result_mismatch|direct_full_schema|
|23|Find the average age of the dogs who went through treatments.|dog_kennels|SELECT AVG(dogs.age) AS average_age<br>FROM dogs<br>JOIN treatments ON dogs.dog_id = treatments.dog_id;|True|False|result_mismatch|direct_full_schema|
|29|What is the number of employees from each city?|employee_hire_evaluation|SELECT e.City, COUNT(*) AS Number_of_Employees<br>FROM employee e<br>GROUP BY e.City;|True|False|result_mismatch|direct_full_schema|
