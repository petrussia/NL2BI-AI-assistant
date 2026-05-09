# B1 Schema Linking Examples (smoke25)

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
| 10 | concert_singer | 4 | 4 | 1.00 | True | stadium, singer, concert, singer_in_concert | -- |
| 11 | concert_singer | 4 | 4 | 1.00 | True | stadium, singer, concert, singer_in_concert | -- |
| 12 | concert_singer | 4 | 2 | 0.50 | False | stadium, singer | stadium: Average; singer: Song_Name,Song_release_year |
| 13 | concert_singer | 4 | 1 | 0.25 | False | singer | singer: Song_Name,Song_release_year |
| 14 | concert_singer | 4 | 3 | 0.75 | False | stadium, singer, concert | stadium: Location,Name,Capacity; singer: Name,Song_Name; concert: concert_Name |
| 15 | concert_singer | 4 | 1 | 0.25 | False | stadium | stadium: Capacity |
| 16 | concert_singer | 4 | 1 | 0.25 | False | stadium | stadium: Capacity,Average |
| 17 | concert_singer | 4 | 1 | 0.25 | False | stadium | stadium: Average |
| 18 | concert_singer | 4 | 3 | 0.75 | False | stadium, singer, concert | stadium: Stadium_ID,Name,Capacity,Highest,Average; singer: Name,Song_Name; concert: concert_Name,Stadium_ID |
| 19 | concert_singer | 4 | 3 | 0.75 | False | stadium, singer, concert | stadium: Stadium_ID,Name,Capacity,Highest,Average; singer: Name,Song_Name; concert: concert_Name,Stadium_ID |
| 20 | concert_singer | 4 | 2 | 0.50 | False | singer, concert | singer: Song_release_year; concert: Year |
| 21 | concert_singer | 4 | 4 | 1.00 | True | stadium, singer, concert, singer_in_concert | -- |
| 22 | concert_singer | 4 | 3 | 0.75 | False | stadium, singer, concert | stadium: Stadium_ID,Name; singer: Name,Song_Name; concert: concert_Name,Stadium_ID |
| 23 | concert_singer | 4 | 4 | 1.00 | True | stadium, singer, concert, singer_in_concert | -- |
| 24 | concert_singer | 4 | 3 | 0.75 | False | stadium, singer, concert | stadium: Stadium_ID,Name,Capacity; singer: Name,Song_Name,Song_release_year; concert: concert_Name,Stadium_ID,Year |
