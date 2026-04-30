# b4_final_multidb30 Error Cases

|idx|question|db_id|plan_valid|generated_sql|executable|execution_match|error_type|
|---|---|---|---|---|---|---|---|
|1|List the name and tonnage ordered by in descending alphaetical order for the names.|battle_death|False||False|False|plan_invalid|
|2|List the name, date and result of each battle.|battle_death|True|SELECT name, date, result FROM battle;|True|False|result_mismatch|
|7|How many countries does each continent have? List the continent id, continent name and the number of countries.|car_1|False||False|False|plan_invalid|
|8|For each continent, list its id, name, and how many countries it has?|car_1|False||False|False|plan_invalid|
|12|List the names of teachers in ascending order of age.|course_teach|False||False|False|plan_invalid|
|13|What are the names of the teachers ordered by ascending age?|course_teach|False||False|False|plan_invalid|
|16|Count the number of documents.|cre_Doc_Template_Mgt|True|SELECT COUNT(*) FROM Templates;|True|False|result_mismatch|
|20|Which states have both owners and professionals living there?|dog_kennels|False||False|False|plan_invalid|
|21|Find the states where both owners and professionals live.|dog_kennels|False||False|False|plan_invalid|
|22|What is the average age of the dogs who have gone through any treatments?|dog_kennels|False||False|False|plan_invalid|
|23|Find the average age of the dogs who went through treatments.|dog_kennels|False||False|False|plan_invalid|
|24|Which professionals live in the state of Indiana or have done treatment on more than 2 treatments? List his or her id, last name and cell phone.|dog_kennels|False||False|False|plan_invalid|
|26|Count the number of employees|employee_hire_evaluation|True|SELECT COUNT(*) FROM shop;|True|False|result_mismatch|
|27|Sort employee names by their age in ascending order.|employee_hire_evaluation|False||False|False|plan_invalid|
|28|List the names of employees and sort in ascending order of age.|employee_hire_evaluation|False||False|False|plan_invalid|
|29|What is the number of employees from each city?|employee_hire_evaluation|True|SELECT Location, COUNT(*) FROM shop GROUP BY Location;|True|False|result_mismatch|
