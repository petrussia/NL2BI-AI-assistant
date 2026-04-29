# B0 vs B1 vs B2 Case Diff (smoke10)

## Case 6 (db: concert_singer)

- **Question:** Show the name and the release year of the song by the youngest singer.

- **B0:** match=True executable=True error=''

  - SQL: `SELECT Song_Name, Song_release_year FROM singer ORDER BY Age ASC LIMIT 1;`

- **B1:** match=True executable=True error='' selected_tables=['stadium', 'singer', 'concert']

  - SQL: `SELECT Song_Name, Song_release_year FROM singer ORDER BY Age ASC LIMIT 1;`

- **B2:** match=False executable=True plan_valid=True error='result_mismatch'

  - Plan parsed: `{"intent": "select_filter", "tables": ["singer"], "operations": ["select", "filter", "orderby"], "columns": ["Name", "Song_release_year"], "filters": [], "aggregations": [], "group_by": [], "order_by"`

  - SQL: `SELECT Name, Song_release_year FROM singer ORDER BY Age ASC LIMIT 1;`

- **Comment:** B2 regressed vs simpler baseline (planner introduced an error)

## Case 7 (db: concert_singer)

- **Question:** What are the names and release years for all the songs of the youngest singer?

- **B0:** match=True executable=True error=''

  - SQL: `SELECT Song_Name, Song_release_year FROM singer ORDER BY Age ASC LIMIT 1;`

- **B1:** match=True executable=True error='' selected_tables=['singer']

  - SQL: `SELECT Song_Name, Song_release_year FROM singer WHERE Age = (SELECT MIN(Age) FROM singer);`

- **B2:** match=False executable=True plan_valid=True error='result_mismatch'

  - Plan parsed: `{"intent": "select_filter", "tables": ["singer"], "operations": ["select", "filter", "orderby", "limit"], "columns": ["Name", "Song_release_year"], "filters": [], "aggregations": [], "group_by": [], "`

  - SQL: `SELECT Name, Song_release_year FROM singer ORDER BY Age ASC LIMIT 1;`

- **Comment:** B2 regressed vs simpler baseline (planner introduced an error)

## Case 8 (db: concert_singer)

- **Question:** What are all distinct countries where singers above age 20 are from?

- **B0:** match=True executable=True error=''

  - SQL: `SELECT DISTINCT Country FROM singer WHERE Age > 20;`

- **B1:** match=True executable=True error='' selected_tables=['singer']

  - SQL: `SELECT DISTINCT Country FROM singer WHERE Age > 20;`

- **B2:** match=False executable=False plan_valid=False error='plan_invalid'

  - Plan parsed: `{"intent": "select_filter", "tables": ["singer"], "operations": ["select", "filter"], "columns": ["Country"], "filters": [{"column": "Age", "op": ">", "value": 20}], "distinct": true}`

  - SQL: ``

- **Comment:** B2 regressed vs simpler baseline (planner introduced an error)

## Case 0 (db: concert_singer)

- **Question:** How many singers do we have?

- **B0:** match=True executable=True error=''

  - SQL: `SELECT COUNT(*) FROM singer;`

- **B1:** match=True executable=True error='' selected_tables=['stadium', 'singer', 'concert', 'singer_in_concert']

  - SQL: `SELECT COUNT(*) FROM singer;`

- **B2:** match=True executable=True plan_valid=True error=''

  - Plan parsed: `{"intent": "select_count", "tables": ["singer"], "operations": ["count"]}`

  - SQL: `SELECT COUNT(*) FROM singer;`

- **Comment:** all three baselines correct

## Case 1 (db: concert_singer)

- **Question:** What is the total number of singers?

- **B0:** match=True executable=True error=''

  - SQL: `SELECT COUNT(*) FROM singer;`

- **B1:** match=True executable=True error='' selected_tables=['stadium', 'singer', 'concert', 'singer_in_concert']

  - SQL: `SELECT COUNT(*) FROM singer;`

- **B2:** match=True executable=True plan_valid=True error=''

  - Plan parsed: `{"intent": "select_count", "tables": ["singer"], "operations": ["count"]}`

  - SQL: `SELECT COUNT(*) FROM singer;`

- **Comment:** all three baselines correct
