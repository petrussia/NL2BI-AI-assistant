# b1_qwen2p5_coder_14b_instruct_smoke25 Error Cases

|idx|question|db_id|generated_sql|executable|execution_match|error_type|path|
|---|---|---|---|---|---|---|---|
|16|What is the maximum capacity and the average of all stadiums ?|concert_singer|SELECT MAX(Capacity) AS Max_Capacity, AVG(Average) AS Avg_Average FROM stadium;|True|False|result_mismatch|lex_linker|
|17|What is the average and maximum capacities for all stadiums ?|concert_singer|SELECT Average, Highest FROM stadium;|True|False|result_mismatch|lex_linker|
