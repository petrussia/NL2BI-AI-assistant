# Query Analysis Examples (smoke10)


Generated at: 2026-04-29T14:59:37.653420+00:00

| idx | question | predicted_intent | confidence | aggregations | distinct | ordering | limit | comparisons | time | join_hint |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 | How many singers do we have? | select_count | 0.9 | ['count'] | False | [] | None | [] | 0 | False |
| 1 | What is the total number of singers? | select_count | 0.9 | ['count', 'sum'] | False | [] | None | [] | 0 | False |
| 2 | Show name, country, age for all singers ordered by age from the oldest to the yo | select_orderby | 0.8 | ['min'] | False | ['order_asc', 'sort'] | 1 | [] | 0 | False |
| 3 | What are the names, countries, and ages for every singer in descending order of  | select_orderby | 0.8 | [] | False | ['order_desc'] | None | [] | 0 | False |
| 4 | What is the average, minimum, and maximum age of all singers from France? | select_aggregate | 0.85 | ['avg', 'max', 'min'] | False | [] | None | [] | 0 | False |
| 5 | What is the average, minimum, and maximum age for all French singers? | select_aggregate | 0.85 | ['avg', 'max', 'min'] | False | [] | None | [] | 0 | False |
| 6 | Show the name and the release year of the song by the youngest singer. | select_orderby | 0.8 | ['min'] | False | ['order_asc'] | 1 | [] | 1 | False |
| 7 | What are the names and release years for all the songs of the youngest singer? | select_orderby | 0.8 | ['min'] | False | ['order_asc'] | 1 | [] | 1 | False |
| 8 | What are all distinct countries where singers above age 20 are from? | select_distinct | 0.85 | [] | True | [] | None | ['>'] | 0 | False |
| 9 | What are  the different countries with singers above age 20? | select_distinct | 0.85 | [] | True | [] | None | ['>'] | 0 | False |
