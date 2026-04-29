# B1 Schema Linking Examples (smoke10)

| # | db_id | total_tables | selected | reduction | fallback | selected_tables | matched_cols |
|---|---|---|---|---|---|---|---|
| 0 | concert_singer | 4 | 4 | 1.00 | True | stadium, singer, concert, singer_in_concert | -- |
| 1 | concert_singer | 4 | 4 | 1.00 | True | stadium, singer, concert, singer_in_concert | -- |
| 2 | concert_singer | 4 | 1 | 0.25 | False | singer | singer: Age |
| 3 | concert_singer | 4 | 2 | 0.50 | False | singer, singer_in_concert | singer: Singer_ID; singer_in_concert: Singer_ID |
| 4 | concert_singer | 4 | 1 | 0.25 | False | singer | singer: Age |
| 5 | concert_singer | 4 | 1 | 0.25 | False | singer | singer: Age |
| 6 | concert_singer | 4 | 3 | 0.75 | False | stadium, singer, concert | stadium: Name; singer: Name,Song_Name,Song_release_year; concert: concert_Name,Year |
| 7 | concert_singer | 4 | 1 | 0.25 | False | singer | singer: Song_release_year |
| 8 | concert_singer | 4 | 1 | 0.25 | False | singer | singer: Age |
| 9 | concert_singer | 4 | 1 | 0.25 | False | singer | singer: Age |
