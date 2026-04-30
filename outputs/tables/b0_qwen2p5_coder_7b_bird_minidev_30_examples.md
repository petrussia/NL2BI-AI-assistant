# b0_qwen2p5_coder_7b_bird_minidev_30 Examples

|idx|question|db_id|generated_sql|executable|execution_match|error_type|path|
|---|---|---|---|---|---|---|---|
|0|How many schools with an average score in Math greater than 400 in the SAT test are exclusively virtual?|california_schools|SELECT COUNT(*) <br>FROM satscores AS T1 <br>JOIN schools AS T2 ON T1.cds = T2.CDSCode <br>WHERE T1.AvgScrMath > 400 AND T2.Virtual = 'Yes';|True|False|result_mismatch|direct_full_schema|
|1|Which are the cards that have incredibly powerful foils.|card_games|SELECT name FROM cards WHERE hasFoil = 1 AND convertedManaCost > 5;|True|False|result_mismatch|direct_full_schema|
|2|Which user has a higher reputation, Harlan or Jarrod Dixon?|codebase_community|SELECT DisplayName FROM users WHERE DisplayName IN ('Harlan', 'Jarrod Dixon') ORDER BY Reputation DESC LIMIT 1;|True|True||direct_full_schema|
|3|What is the ratio of customers who pay in EUR against customers who pay in CZK?|debit_card_specializing|SELECT <br>    SUM(CASE WHEN c.Currency = 'EUR' THEN 1 ELSE 0 END) * 1.0 / <br>    SUM(CASE WHEN c.Currency = 'CZK' THEN 1 ELSE 0 END) AS Ratio<br>FROM <br>    customers c<br>JOIN <br>    transactions_1k t ON c.CustomerID = t.CustomerID;|True|False|result_mismatch|direct_full_schema|
|4|Give the name of the league had the most goals in the 2016 season?|european_football_2|SELECT l.name <br>FROM League l <br>JOIN Match m ON l.id = m.league_id <br>WHERE m.season = '2016' <br>GROUP BY l.name <br>ORDER BY SUM(m.home_team_goal + m.away_team_goal) DESC <br>LIMIT 1;|True|False|result_mismatch|direct_full_schema|
