# b1_qwen_qwen2.5_7b_instruct_bird_minidev_30 Examples

|idx|question|db_id|generated_sql|executable|execution_match|error_type|path|
|---|---|---|---|---|---|---|---|
|0|How many schools with an average score in Math greater than 400 in the SAT test are exclusively virtual?|california_schools|SELECT COUNT(*) <br>FROM schools <br>WHERE Virtual = 'Yes' AND GSoffered LIKE '%Math%' AND CAST(SUBSTR(GSoffered, INSTR(GSoffered, 'Math') + 5) AS INTEGER) > 400;|True|False|result_mismatch|lex_linker|
|1|Which are the cards that have incredibly powerful foils.|card_games|SELECT name, text, manaCost, power, toughness, rarity <br>FROM cards <br>WHERE hasFoil = 1 AND (power IS NOT NULL AND toughness IS NOT NULL AND (power + toughness) > 10);|True|False|result_mismatch|lex_linker|
|2|Which user has a higher reputation, Harlan or Jarrod Dixon?|codebase_community|SELECT u1.DisplayName, u1.Reputation <br>FROM users u1<br>JOIN users u2 ON u1.Reputation < u2.Reputation<br>WHERE (u1.DisplayName = 'Harlan' AND u2.DisplayName = 'Jarrod Dixon') OR (u1.DisplayName = 'Jarrod Dixon' AND u2.DisplayName = 'Harlan')<br>LIMIT 1;|True|False|result_mismatch|lex_linker|
|3|What is the ratio of customers who pay in EUR against customers who pay in CZK?|debit_card_specializing|SELECT CAST(SUM(CASE WHEN Currency = 'EUR' THEN 1 ELSE 0 END) AS REAL) / SUM(1) AS Euro_Ratio<br>FROM customers;|True|False|result_mismatch|lex_linker|
|4|Give the name of the league had the most goals in the 2016 season?|european_football_2|SELECT L.name<br>FROM League L<br>JOIN Match M ON L.id = M.league_id<br>WHERE M.season = '2016'<br>GROUP BY L.name<br>ORDER BY SUM(M.home_team_goal + M.away_team_goal) DESC<br>LIMIT 1;|True|False|result_mismatch|lex_linker|
