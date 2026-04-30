# B4_final Candidate Examples (smoke10, first 5)

## idx=0 db=concert_singer
- Question: How many singers do we have?
- Safety flags:
  - ok=True reason='' sql=`SELECT COUNT(*) FROM singer;`
  - ok=True reason='' sql=`SELECT COUNT(*) FROM singer;`
  - ok=True reason='' sql=`SELECT COUNT(*) FROM singer;`
- Cand exec results:
  - executable=True error_type='' sql=`SELECT COUNT(*) FROM singer;`
  - executable=True error_type='' sql=`SELECT COUNT(*) FROM singer;`
  - executable=True error_type='' sql=`SELECT COUNT(*) FROM singer;`
- Chosen: `SELECT COUNT(*) FROM singer;`
- Selection reason: `consistency_winner`
- Repaired: `False`

## idx=1 db=concert_singer
- Question: What is the total number of singers?
- Safety flags:
  - ok=True reason='' sql=`SELECT COUNT(*) FROM singer;`
  - ok=True reason='' sql=`SELECT COUNT(*) FROM singer;`
  - ok=True reason='' sql=`SELECT COUNT(*) FROM singer;`
- Cand exec results:
  - executable=True error_type='' sql=`SELECT COUNT(*) FROM singer;`
  - executable=True error_type='' sql=`SELECT COUNT(*) FROM singer;`
  - executable=True error_type='' sql=`SELECT COUNT(*) FROM singer;`
- Chosen: `SELECT COUNT(*) FROM singer;`
- Selection reason: `consistency_winner`
- Repaired: `False`

## idx=2 db=concert_singer
- Question: Show name, country, age for all singers ordered by age from the oldest to the youngest.
- Safety flags:
- Cand exec results:
- Chosen: ``
- Selection reason: ``
- Repaired: `False`

## idx=3 db=concert_singer
- Question: What are the names, countries, and ages for every singer in descending order of age?
- Safety flags:
- Cand exec results:
- Chosen: ``
- Selection reason: ``
- Repaired: `False`

## idx=4 db=concert_singer
- Question: What is the average, minimum, and maximum age of all singers from France?
- Safety flags:
  - ok=True reason='' sql=`SELECT avg(Age), min(Age), max(Age) FROM singer WHERE Country = 'France';`
  - ok=True reason='' sql=`SELECT avg(Age), min(Age), max(Age) FROM singer WHERE Country = 'France';`
  - ok=True reason='' sql=`SELECT avg(Age), min(Age), max(Age) FROM singer WHERE Country = 'France';`
- Cand exec results:
  - executable=True error_type='' sql=`SELECT avg(Age), min(Age), max(Age) FROM singer WHERE Country = 'France';`
  - executable=True error_type='' sql=`SELECT avg(Age), min(Age), max(Age) FROM singer WHERE Country = 'France';`
  - executable=True error_type='' sql=`SELECT avg(Age), min(Age), max(Age) FROM singer WHERE Country = 'France';`
- Chosen: `SELECT avg(Age), min(Age), max(Age) FROM singer WHERE Country = 'France';`
- Selection reason: `consistency_winner`
- Repaired: `False`
