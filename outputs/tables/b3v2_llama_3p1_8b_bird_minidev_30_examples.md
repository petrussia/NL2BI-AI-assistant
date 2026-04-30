# b3v2_llama_3p1_8b_bird_minidev_30 Examples

|idx|question|db_id|generated_sql|executable|execution_match|error_type|path|
|---|---|---|---|---|---|---|---|
|0|How many schools with an average score in Math greater than 400 in the SAT test are exclusively virtual?|california_schools|SELECT COUNT(*) FROM schools WHERE Virtual = 'Y' AND SOC LIKE '%Math%' AND GSserved > 400;|True|False|result_mismatch|b1_fallback_invalid_plan|
|1|Which are the cards that have incredibly powerful foils.|card_games|SELECT * FROM card_games WHERE hasFoil = 1 AND edhrecRank > 100;|False|False|OperationalError|b1_fallback_invalid_plan|
|2|Which user has a higher reputation, Harlan or Jarrod Dixon?|codebase_community|SELECT Id, DisplayName, Reputation FROM users WHERE Reputation > ( SELECT Reputation FROM users WHERE DisplayName = 'Jarrod Dixon' ) AND DisplayName = 'Harlan';|True|False|result_mismatch|b1_fallback_invalid_plan|
|3|What is the ratio of customers who pay in EUR against customers who pay in CZK?|debit_card_specializing|SELECT CAST(SUM(CASE WHEN Currency = 'EUR' THEN 1 ELSE 0 END) AS REAL) / SUM(CASE WHEN Currency = 'CZK' THEN 1 ELSE 0 END) FROM customers;|True|True||b1_fallback_invalid_plan|
|4|Give the name of the league had the most goals in the 2016 season?|european_football_2|SELECT T1.name FROM League AS T1 INNER JOIN Match AS T2 ON T1.id = T2.league_id WHERE T2.season = '2016' GROUP BY T1.id ORDER BY SUM(T2.home_team_goal + T2.away_team_goal) DESC LIMIT 1;|True|False|result_mismatch|b1_fallback_invalid_plan|
