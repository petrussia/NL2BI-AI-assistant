# b2v1_multidb30 Examples

|idx|question|db_id|plan_valid|generated_sql|executable|execution_match|error_type|
|---|---|---|---|---|---|---|---|
|0|How many ships ended up being 'Captured'?|battle_death|True|SELECT COUNT(id) FROM ship WHERE disposition_of_ship = 'Captured';|True|True||
|1|List the name and tonnage ordered by in descending alphaetical order for the names.|battle_death|True|SELECT name, tonnage FROM ship ORDER BY name DESC;|True|True||
|2|List the name, date and result of each battle.|battle_death|True|SELECT name, date, result FROM battle;|True|False|result_mismatch|
|3|What is maximum and minimum death toll caused each time?|battle_death|True|SELECT MAX(killed), MIN(killed) FROM death;|True|True||
|4|What is the average number of injuries caused each time?|battle_death|True|SELECT AVG(injured) FROM death;|True|True||
