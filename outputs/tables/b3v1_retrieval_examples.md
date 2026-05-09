# B3_v1 Retrieval Examples (smoke10, first 5)

## idx 0 db=concert_singer
- Question: How many singers do we have?
- knowledge_enabled: False
```
Database: concert_singer
Schema:
- stadium(Stadium_ID, Location, Name, Capacity, Highest, Lowest, Average)
- singer(Singer_ID, Name, Country, Song_Name, Song_release_year, Age, Is_male)
- concert(concert_ID, concert_Name, Theme, Stadium_ID, Year)
- singer_in_concert(concert_ID, Singer_ID)
```

## idx 1 db=concert_singer
- Question: What is the total number of singers?
- knowledge_enabled: False
```
Database: concert_singer
Schema:
- stadium(Stadium_ID, Location, Name, Capacity, Highest, Lowest, Average)
- singer(Singer_ID, Name, Country, Song_Name, Song_release_year, Age, Is_male)
- concert(concert_ID, concert_Name, Theme, Stadium_ID, Year)
- singer_in_concert(concert_ID, Singer_ID)
```

## idx 2 db=concert_singer
- Question: Show name, country, age for all singers ordered by age from the oldest to the youngest.
- knowledge_enabled: False
```
Database: concert_singer
Schema:
- singer(Singer_ID, Name, Country, Song_Name, Song_release_year, Age, Is_male)
```

## idx 3 db=concert_singer
- Question: What are the names, countries, and ages for every singer in descending order of age?
- knowledge_enabled: False
```
Database: concert_singer
Schema:
- singer(Singer_ID, Name, Country, Song_Name, Song_release_year, Age, Is_male)
- singer_in_concert(concert_ID, Singer_ID)
```

## idx 4 db=concert_singer
- Question: What is the average, minimum, and maximum age of all singers from France?
- knowledge_enabled: False
```
Database: concert_singer
Schema:
- singer(Singer_ID, Name, Country, Song_Name, Song_release_year, Age, Is_male)
```
