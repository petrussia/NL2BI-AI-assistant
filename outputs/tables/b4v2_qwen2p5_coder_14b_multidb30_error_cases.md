# b4v2_qwen2p5_coder_14b_multidb30 Error Cases

|idx|question|db_id|generated_sql|executable|execution_match|error_type|path|
|---|---|---|---|---|---|---|---|
|2|List the name, date and result of each battle.|battle_death|SELECT name, date, result FROM battle;|True|False|result_mismatch|multicand:consistency_winner|
|8|For each continent, list its id, name, and how many countries it has?|car_1|SELECT Continent, COUNT(*) FROM countries GROUP BY Continent;|True|False|result_mismatch|multicand:consistency_winner|
|26|Count the number of employees|employee_hire_evaluation|SELECT COUNT(*) FROM shop;|True|False|result_mismatch|multicand:consistency_winner|
|29|What is the number of employees from each city?|employee_hire_evaluation|SELECT Location, COUNT(*) FROM shop GROUP BY Location;|True|False|result_mismatch|multicand:consistency_winner|
