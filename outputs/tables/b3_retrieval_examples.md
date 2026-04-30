# B3 Retrieval Examples (smoke10, first 5)

## Item idx=? db=concert_singer

- **Question:** How many singers do we have?

- **Schema-selected tables:** ['stadium', 'singer', 'concert', 'singer_in_concert']

- **Knowledge top-3 (table_idx, score):** [(0, 0), (1, 0), (2, 0)]

- **Full B3 context (proxy + schema):**

```
Database: concert_singer
Schema (relevant tables):
- stadium(Stadium_ID, Location, Name, Capacity, Highest, Lowest, Average)
- singer(Singer_ID, Name, Country, Song_Name, Song_release_year, Age, Is_male)
- concert(concert_ID, concert_Name, Theme, Stadium_ID, Year)
- singer_in_concert(concert_ID, Singer_ID)

Knowledge (synthetic proxy docs derived from schema metadata):
Table singer_in_concert: domain entity 'singer in concert'.
Columns:
  - concert_ID [PK, FK->col#15, number]
  - Singer_ID [FK->col#8, text]
Table singer: domain entity 'singer'.
Columns:
  - Singer_ID [PK, referenced by col#21, number]
  - Name [text]
  - Country [text]
  - Song_Name [text]
  - Song_release_year [text]
  - Age [number]
  - Is_male [others]
Table concert: domain entity 'concert'.
Columns:
  - concert_ID [PK, referenced by col#20, number]
  - concert_Name [text]
  - Theme [text]
  - Stadium_ID [FK->col#1, text]
  - Year [text]
```

## Item idx=? db=concert_singer

- **Question:** What is the total number of singers?

- **Schema-selected tables:** ['stadium', 'singer', 'concert', 'singer_in_concert']

- **Knowledge top-3 (table_idx, score):** [(0, 0), (1, 0), (2, 0)]

- **Full B3 context (proxy + schema):**

```
Database: concert_singer
Schema (relevant tables):
- stadium(Stadium_ID, Location, Name, Capacity, Highest, Lowest, Average)
- singer(Singer_ID, Name, Country, Song_Name, Song_release_year, Age, Is_male)
- concert(concert_ID, concert_Name, Theme, Stadium_ID, Year)
- singer_in_concert(concert_ID, Singer_ID)

Knowledge (synthetic proxy docs derived from schema metadata):
Table singer_in_concert: domain entity 'singer in concert'.
Columns:
  - concert_ID [PK, FK->col#15, number]
  - Singer_ID [FK->col#8, text]
Table singer: domain entity 'singer'.
Columns:
  - Singer_ID [PK, referenced by col#21, number]
  - Name [text]
  - Country [text]
  - Song_Name [text]
  - Song_release_year [text]
  - Age [number]
  - Is_male [others]
Table concert: domain entity 'concert'.
Columns:
  - concert_ID [PK, referenced by col#20, number]
  - concert_Name [text]
  - Theme [text]
  - Stadium_ID [FK->col#1, text]
  - Year [text]
```

## Item idx=? db=concert_singer

- **Question:** Show name, country, age for all singers ordered by age from the oldest to the youngest.

- **Schema-selected tables:** ['singer']

- **Knowledge top-3 (table_idx, score):** [(1, 1), (0, 0), (2, 0)]

- **Full B3 context (proxy + schema):**

```
Database: concert_singer
Schema (relevant tables):
- singer(Singer_ID, Name, Country, Song_Name, Song_release_year, Age, Is_male)

Knowledge (synthetic proxy docs derived from schema metadata):
Table singer: domain entity 'singer'.
Columns:
  - Singer_ID [PK, referenced by col#21, number]
  - Name [text]
  - Country [text]
  - Song_Name [text]
  - Song_release_year [text]
  - Age [number]
  - Is_male [others]
Table singer_in_concert: domain entity 'singer in concert'.
Columns:
  - concert_ID [PK, FK->col#15, number]
  - Singer_ID [FK->col#8, text]
Table concert: domain entity 'concert'.
Columns:
  - concert_ID [PK, referenced by col#20, number]
  - concert_Name [text]
  - Theme [text]
  - Stadium_ID [FK->col#1, text]
  - Year [text]
```

## Item idx=? db=concert_singer

- **Question:** What are the names, countries, and ages for every singer in descending order of age?

- **Schema-selected tables:** ['singer', 'singer_in_concert']

- **Knowledge top-3 (table_idx, score):** [(1, 1), (3, 1), (0, 0)]

- **Full B3 context (proxy + schema):**

```
Database: concert_singer
Schema (relevant tables):
- singer(Singer_ID, Name, Country, Song_Name, Song_release_year, Age, Is_male)
- singer_in_concert(concert_ID, Singer_ID)

Knowledge (synthetic proxy docs derived from schema metadata):
Table singer_in_concert: domain entity 'singer in concert'.
Columns:
  - concert_ID [PK, FK->col#15, number]
  - Singer_ID [FK->col#8, text]
Table singer: domain entity 'singer'.
Columns:
  - Singer_ID [PK, referenced by col#21, number]
  - Name [text]
  - Country [text]
  - Song_Name [text]
  - Song_release_year [text]
  - Age [number]
  - Is_male [others]
Table concert: domain entity 'concert'.
Columns:
  - concert_ID [PK, referenced by col#20, number]
  - concert_Name [text]
  - Theme [text]
  - Stadium_ID [FK->col#1, text]
  - Year [text]
```

## Item idx=? db=concert_singer

- **Question:** What is the average, minimum, and maximum age of all singers from France?

- **Schema-selected tables:** ['singer']

- **Knowledge top-3 (table_idx, score):** [(1, 1), (0, 0), (2, 0)]

- **Full B3 context (proxy + schema):**

```
Database: concert_singer
Schema (relevant tables):
- singer(Singer_ID, Name, Country, Song_Name, Song_release_year, Age, Is_male)

Knowledge (synthetic proxy docs derived from schema metadata):
Table singer: domain entity 'singer'.
Columns:
  - Singer_ID [PK, referenced by col#21, number]
  - Name [text]
  - Country [text]
  - Song_Name [text]
  - Song_release_year [text]
  - Age [number]
  - Is_male [others]
Table singer_in_concert: domain entity 'singer in concert'.
Columns:
  - concert_ID [PK, FK->col#15, number]
  - Singer_ID [FK->col#8, text]
Table concert: domain entity 'concert'.
Columns:
  - concert_ID [PK, referenced by col#20, number]
  - concert_Name [text]
  - Theme [text]
  - Stadium_ID [FK->col#1, text]
  - Year [text]
```
