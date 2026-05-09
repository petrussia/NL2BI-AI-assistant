# B0 vs B1 Case Diff (smoke25)

## Case 0 (db: concert_singer) -- unchanged

- **Question:** How many singers do we have?

- **B0:** executable=True, match=True, error=''

  - SQL: `SELECT COUNT(*) FROM singer;`

- **B1:** executable=True, match=True, error=''

  - SQL: `SELECT COUNT(*) FROM singer;`

  - selected tables: stadium, singer, concert, singer_in_concert (reduction=1.0)

- **Comment:** reduction did not change the outcome.

## Case 1 (db: concert_singer) -- unchanged

- **Question:** What is the total number of singers?

- **B0:** executable=True, match=True, error=''

  - SQL: `SELECT COUNT(*) FROM singer;`

- **B1:** executable=True, match=True, error=''

  - SQL: `SELECT COUNT(*) FROM singer;`

  - selected tables: stadium, singer, concert, singer_in_concert (reduction=1.0)

- **Comment:** reduction did not change the outcome.

## Case 2 (db: concert_singer) -- unchanged

- **Question:** Show name, country, age for all singers ordered by age from the oldest to the youngest.

- **B0:** executable=True, match=True, error=''

  - SQL: `SELECT Name, Country, Age FROM singer ORDER BY Age DESC;`

- **B1:** executable=True, match=True, error=''

  - SQL: `SELECT Name, Country, Age FROM singer ORDER BY Age DESC;`

  - selected tables: singer (reduction=0.25)

- **Comment:** reduction did not change the outcome.

## Case 3 (db: concert_singer) -- unchanged

- **Question:** What are the names, countries, and ages for every singer in descending order of age?

- **B0:** executable=True, match=True, error=''

  - SQL: `SELECT Name, Country, Age FROM singer ORDER BY Age DESC;`

- **B1:** executable=True, match=True, error=''

  - SQL: `SELECT Name, Country, Age FROM singer ORDER BY Age DESC;`

  - selected tables: singer, singer_in_concert (reduction=0.5)

- **Comment:** reduction did not change the outcome.

## Case 4 (db: concert_singer) -- unchanged

- **Question:** What is the average, minimum, and maximum age of all singers from France?

- **B0:** executable=True, match=True, error=''

  - SQL: `SELECT AVG(Age), MIN(Age), MAX(Age) FROM singer WHERE Country = 'France';`

- **B1:** executable=True, match=True, error=''

  - SQL: `SELECT AVG(Age) AS Average_Age, MIN(Age) AS Minimum_Age, MAX(Age) AS Maximum_Age FROM singer WHERE Country = 'France';`

  - selected tables: singer (reduction=0.25)

- **Comment:** reduction did not change the outcome.
