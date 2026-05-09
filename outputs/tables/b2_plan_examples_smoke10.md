# B2 Plan Examples (smoke10)

## Item 0 (db: concert_singer)

- **Question:** How many singers do we have?

- **Plan valid:** `True` error=''

- **Plan parsed:**

```json
{
  "intent": "select_count",
  "tables": [
    "singer"
  ],
  "operations": [
    "count"
  ]
}
```

- **Generated SQL:** `SELECT COUNT(*) FROM singer;`

- **Gold SQL:** `SELECT count(*) FROM singer`

- **execution_match:** True

## Item 1 (db: concert_singer)

- **Question:** What is the total number of singers?

- **Plan valid:** `True` error=''

- **Plan parsed:**

```json
{
  "intent": "select_count",
  "tables": [
    "singer"
  ],
  "operations": [
    "count"
  ]
}
```

- **Generated SQL:** `SELECT COUNT(*) FROM singer;`

- **Gold SQL:** `SELECT count(*) FROM singer`

- **execution_match:** True

## Item 2 (db: concert_singer)

- **Question:** Show name, country, age for all singers ordered by age from the oldest to the youngest.

- **Plan valid:** `True` error=''

- **Plan parsed:**

```json
{
  "intent": "select_other",
  "tables": [
    "singer"
  ],
  "operations": [
    "select",
    "orderby"
  ],
  "columns": [
    "Name",
    "Country",
    "Age"
  ],
  "order_by": [
    {
      "column": "Age",
      "dir": "DESC"
    }
  ]
}
```

- **Generated SQL:** `SELECT Name, Country, Age FROM singer ORDER BY Age DESC;`

- **Gold SQL:** `SELECT name ,  country ,  age FROM singer ORDER BY age DESC`

- **execution_match:** True

## Item 3 (db: concert_singer)

- **Question:** What are the names, countries, and ages for every singer in descending order of age?

- **Plan valid:** `True` error=''

- **Plan parsed:**

```json
{
  "intent": "select_other",
  "tables": [
    "singer"
  ],
  "operations": [
    "select",
    "orderby"
  ],
  "columns": [
    "Name",
    "Country",
    "Age"
  ],
  "order_by": [
    {
      "column": "Age",
      "dir": "DESC"
    }
  ]
}
```

- **Generated SQL:** `SELECT Name, Country, Age FROM singer ORDER BY Age DESC;`

- **Gold SQL:** `SELECT name ,  country ,  age FROM singer ORDER BY age DESC`

- **execution_match:** True

## Item 4 (db: concert_singer)

- **Question:** What is the average, minimum, and maximum age of all singers from France?

- **Plan valid:** `True` error=''

- **Plan parsed:**

```json
{
  "intent": "select_aggregate",
  "tables": [
    "singer"
  ],
  "operations": [
    "select",
    "aggregate"
  ],
  "columns": [
    "Age"
  ],
  "aggregations": [
    {
      "function": "AVG",
      "column": "Age"
    },
    {
      "function": "MIN",
      "column": "Age"
    },
    {
      "function": "MAX",
      "column": "Age"
    }
  ],
  "filters": [
    {
      "column": "Country",
      "op": "=",
      "value": "France"
    }
  ]
}
```

- **Generated SQL:** `SELECT AVG(Age), MIN(Age), MAX(Age) FROM singer WHERE Country = 'France';`

- **Gold SQL:** `SELECT avg(age) ,  min(age) ,  max(age) FROM singer WHERE country  =  'France'`

- **execution_match:** True

