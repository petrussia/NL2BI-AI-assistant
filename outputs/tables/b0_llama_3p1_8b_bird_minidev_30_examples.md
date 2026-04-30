# b0_llama_3p1_8b_bird_minidev_30 Examples

|idx|question|db_id|generated_sql|executable|execution_match|error_type|path|
|---|---|---|---|---|---|---|---|
|0|How many schools with an average score in Math greater than 400 in the SAT test are exclusively virtual?|california_schools|SELECT COUNT(*) FROM satscores WHERE AvgScrMath > 400 AND Virtual = 'Y';|False|False|OperationalError|direct_full_schema|
|1|Which are the cards that have incredibly powerful foils.|card_games|SELECT c.* FROM cards c INNER JOIN set_translations st ON c.setCode = st.setCode WHERE st.language = 'en' AND c.hasFoil = 1 AND c.edhrecRank > 1000;|True|False|result_mismatch|direct_full_schema|
|2|Which user has a higher reputation, Harlan or Jarrod Dixon?|codebase_community|SELECT Id, DisplayName, Reputation FROM users WHERE Reputation > ( SELECT Reputation FROM users WHERE DisplayName = 'Jarrod Dixon' ) AND DisplayName = 'Harlan';|True|False|result_mismatch|direct_full_schema|
|3|What is the ratio of customers who pay in EUR against customers who pay in CZK?|debit_card_specializing|SELECT CAST(SUM(CASE WHEN T1.Currency = 'EUR' THEN 1 ELSE 0 END) AS REAL) / SUM(CASE WHEN T1.Currency = 'CZK' THEN 1 ELSE 0 END) FROM customers AS T1;|True|True||direct_full_schema|
|4|Give the name of the league had the most goals in the 2016 season?|european_football_2|SELECT T2.name FROM Match AS T1 INNER JOIN League AS T2 ON T1.league_id = T2.id WHERE T1.season = 2016 ORDER BY T1.home_team_goal + T1.away_team_goal DESC LIMIT 1;|True|False|result_mismatch|direct_full_schema|
