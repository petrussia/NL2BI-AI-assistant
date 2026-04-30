# b0_qwen2p5_coder_14b_bird_minidev_30 Examples

|idx|question|db_id|generated_sql|executable|execution_match|error_type|path|
|---|---|---|---|---|---|---|---|
|0|How many schools with an average score in Math greater than 400 in the SAT test are exclusively virtual?|california_schools|SELECT COUNT(DISTINCT s.CDSCode) <br>FROM schools s <br>JOIN satscores ss ON s.CDSCode = ss.cds <br>WHERE ss.AvgScrMath > 400 AND s.Virtual = 'Yes';|True|False|result_mismatch|direct_full_schema|
|1|Which are the cards that have incredibly powerful foils.|card_games|SELECT name FROM cards WHERE hasFoil = 1 AND rarity = 'Mythic Rare';|True|False|result_mismatch|direct_full_schema|
|2|Which user has a higher reputation, Harlan or Jarrod Dixon?|codebase_community|SELECT DisplayName, Reputation <br>FROM users <br>WHERE DisplayName = 'Harlan' OR DisplayName = 'Jarrod Dixon' <br>ORDER BY Reputation DESC <br>LIMIT 1;|True|False|result_mismatch|direct_full_schema|
|3|What is the ratio of customers who pay in EUR against customers who pay in CZK?|debit_card_specializing|SELECT <br>    SUM(CASE WHEN Currency = 'EUR' THEN 1 ELSE 0 END) * 1.0 / <br>    SUM(CASE WHEN Currency = 'CZK' THEN 1 ELSE 0 END) AS Ratio<br>FROM <br>    customers;|True|True||direct_full_schema|
|4|Give the name of the league had the most goals in the 2016 season?|european_football_2|SELECT L.name <br>FROM League L <br>JOIN Match M ON L.id = M.league_id <br>WHERE M.season = '2016' <br>GROUP BY L.name <br>ORDER BY SUM(M.home_team_goal + M.away_team_goal) DESC <br>LIMIT 1;|True|False|result_mismatch|direct_full_schema|
