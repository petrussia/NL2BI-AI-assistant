# b2v2_qwen_qwen2.5_7b_instruct_multidb30 Examples

|idx|question|db_id|generated_sql|executable|execution_match|error_type|path|
|---|---|---|---|---|---|---|---|
|0|How many ships ended up being 'Captured'?|battle_death|SELECT COUNT(*) FROM ship WHERE disposition_of_ship = 'Captured';|True|True||b1_fallback_invalid_plan|
|1|List the name and tonnage ordered by in descending alphaetical order for the names.|battle_death|SELECT name, tonnage <br>FROM ship <br>ORDER BY name DESC;|True|True||b1_fallback_invalid_plan|
|2|List the name, date and result of each battle.|battle_death|SELECT name, date, result FROM battle;|True|False|result_mismatch|b1_fallback_invalid_plan|
|3|What is maximum and minimum death toll caused each time?|battle_death|SELECT MIN(killed) AS min_death_toll, MAX(killed) AS max_death_toll<br>FROM death;|True|False|result_mismatch|b1_fallback_invalid_plan|
|4|What is the average number of injuries caused each time?|battle_death|SELECT AVG(injured) AS average_injuries<br>FROM death;|True|True||b1_fallback_invalid_plan|
