# b0_llama_3p1_8b_instruct_multidb30 Examples

|idx|question|db_id|generated_sql|executable|execution_match|error_type|path|
|---|---|---|---|---|---|---|---|
|0|How many ships ended up being 'Captured'?|battle_death|SELECT COUNT(*) FROM ship WHERE disposition_of_ship = 'Captured';|True|True||direct_full_schema|
|1|List the name and tonnage ordered by in descending alphaetical order for the names.|battle_death|SELECT name, tonnage FROM ship ORDER BY name DESC;|True|True||direct_full_schema|
|2|List the name, date and result of each battle.|battle_death|SELECT name, date, result FROM battle;|True|False|result_mismatch|direct_full_schema|
|3|What is maximum and minimum death toll caused each time?|battle_death|SELECT MAX(killed) AS max_death, MIN(killed) AS min_death FROM death;|True|True||direct_full_schema|
|4|What is the average number of injuries caused each time?|battle_death|SELECT AVG(injured) FROM death;|True|True||direct_full_schema|
