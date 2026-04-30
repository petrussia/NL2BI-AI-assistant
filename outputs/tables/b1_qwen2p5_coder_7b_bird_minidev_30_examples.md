# b1_qwen2p5_coder_7b_bird_minidev_30 Examples

|idx|question|db_id|generated_sql|executable|execution_match|error_type|path|
|---|---|---|---|---|---|---|---|
|0|How many schools with an average score in Math greater than 400 in the SAT test are exclusively virtual?|california_schools|SELECT COUNT(*) <br>FROM schools <br>WHERE Virtual = 'Yes' AND AVG(SAT_Math) > 400;|False|False|OperationalError|lex_linker|
|1|Which are the cards that have incredibly powerful foils.|card_games|SELECT name FROM cards WHERE hasFoil = 1 AND power IS NOT NULL AND toughness IS NOT NULL AND (power + toughness) > 10;|True|False|result_mismatch|lex_linker|
|2|Which user has a higher reputation, Harlan or Jarrod Dixon?|codebase_community|SELECT DisplayName, Reputation <br>FROM users <br>WHERE DisplayName IN ('Harlan', 'Jarrod Dixon') <br>ORDER BY Reputation DESC <br>LIMIT 1;|True|False|result_mismatch|lex_linker|
|3|What is the ratio of customers who pay in EUR against customers who pay in CZK?|debit_card_specializing|SELECT SUM(CASE WHEN Currency = 'EUR' THEN 1 ELSE 0 END) * 1.0 / SUM(CASE WHEN Currency = 'CZK' THEN 1 ELSE 0 END) AS Ratio FROM customers;|True|True||lex_linker|
|4|Give the name of the league had the most goals in the 2016 season?|european_football_2|SELECT l.name <br>FROM League l <br>JOIN Match m ON l.id = m.league_id <br>WHERE m.season = '2016' <br>GROUP BY l.name <br>ORDER BY SUM(m.home_team_goal + m.away_team_goal) DESC <br>LIMIT 1;|True|False|result_mismatch|lex_linker|
