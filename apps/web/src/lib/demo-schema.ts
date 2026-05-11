// Static description of the bundled demo data sources.
// Source of truth: Spider SQLite databases mounted on the Colab L4 from
// /content/drive/MyDrive/diploma_plan_sql/data/spider/database/.
// We keep the schema here so the UI can show table layouts and a curated set
// of suggested queries without paying the extra round-trip.

export type DemoColumn = {
  name: string;
  type: "INTEGER" | "TEXT" | "REAL" | "NUMERIC";
};

export type DemoTable = {
  name: string;
  description: string;
  columns: DemoColumn[];
};

export type DemoDataSource = {
  id: string;
  label: string;
  blurb: string;
  tables: DemoTable[];
  suggestions: string[];
};

const concertSinger: DemoDataSource = {
  id: "demo_concert_singer",
  label: "Spider concert_singer",
  blurb: "Шотландские стадионы, певцы и концерты.",
  tables: [
    {
      name: "stadium",
      description: "Стадионы Шотландии: вместимость, посещаемость.",
      columns: [
        { name: "Stadium_ID", type: "INTEGER" },
        { name: "Location", type: "TEXT" },
        { name: "Name", type: "TEXT" },
        { name: "Capacity", type: "INTEGER" },
        { name: "Highest", type: "INTEGER" },
        { name: "Lowest", type: "INTEGER" },
        { name: "Average", type: "INTEGER" },
      ],
    },
    {
      name: "singer",
      description: "Певцы: страна, возраст, песня и год её выпуска.",
      columns: [
        { name: "Singer_ID", type: "INTEGER" },
        { name: "Name", type: "TEXT" },
        { name: "Country", type: "TEXT" },
        { name: "Song_Name", type: "TEXT" },
        { name: "Song_release_year", type: "INTEGER" },
        { name: "Age", type: "INTEGER" },
        { name: "Is_male", type: "TEXT" },
      ],
    },
    {
      name: "concert",
      description: "Концерты: тема, год, привязка к стадиону.",
      columns: [
        { name: "concert_ID", type: "INTEGER" },
        { name: "concert_Name", type: "TEXT" },
        { name: "Theme", type: "TEXT" },
        { name: "Stadium_ID", type: "INTEGER" },
        { name: "Year", type: "INTEGER" },
      ],
    },
    {
      name: "singer_in_concert",
      description: "Связка певец-концерт (many-to-many).",
      columns: [
        { name: "concert_ID", type: "INTEGER" },
        { name: "Singer_ID", type: "INTEGER" },
      ],
    },
  ],
  suggestions: [
    "Сравни количество певцов по странам",
    "Покажи топ-5 стадионов по вместимости",
    "Количество концертов по годам",
    "Средний возраст певцов по странам",
  ],
};

const wrestler: DemoDataSource = {
  id: "wrestler",
  label: "Spider wrestler",
  blurb: "Рестлеры и их матчи.",
  tables: [
    {
      name: "wrestler",
      description: "Рестлеры: рейтинг, родная страна, дни в качестве чемпиона.",
      columns: [
        { name: "Wrestler_ID", type: "INTEGER" },
        { name: "Name", type: "TEXT" },
        { name: "Reign", type: "TEXT" },
        { name: "Days_held", type: "TEXT" },
        { name: "Location", type: "TEXT" },
        { name: "Event", type: "TEXT" },
      ],
    },
    {
      name: "Elimination",
      description: "События с выбыванием: кого, когда и каким приёмом.",
      columns: [
        { name: "Elimination_ID", type: "INTEGER" },
        { name: "Team", type: "TEXT" },
        { name: "Eliminated_By", type: "TEXT" },
        { name: "Elimination_Move", type: "TEXT" },
        { name: "Wrestler_ID", type: "INTEGER" },
        { name: "Time", type: "TEXT" },
      ],
    },
  ],
  suggestions: [
    "Топ-5 рестлеров по дням удержания титула",
    "Сколько событий было в каждой команде",
    "Какие приёмы чаще всего приводят к выбыванию",
  ],
};

const world1: DemoDataSource = {
  id: "world_1",
  label: "Spider world_1",
  blurb: "Страны, города, языки — классический World DB.",
  tables: [
    {
      name: "city",
      description: "Города мира с населением и кодом страны.",
      columns: [
        { name: "ID", type: "INTEGER" },
        { name: "Name", type: "TEXT" },
        { name: "CountryCode", type: "TEXT" },
        { name: "District", type: "TEXT" },
        { name: "Population", type: "INTEGER" },
      ],
    },
    {
      name: "country",
      description: "Страны: материк, регион, население, площадь.",
      columns: [
        { name: "Code", type: "TEXT" },
        { name: "Name", type: "TEXT" },
        { name: "Continent", type: "TEXT" },
        { name: "Region", type: "TEXT" },
        { name: "SurfaceArea", type: "REAL" },
        { name: "Population", type: "INTEGER" },
        { name: "GNP", type: "REAL" },
      ],
    },
    {
      name: "countrylanguage",
      description: "Языки стран и их доля.",
      columns: [
        { name: "CountryCode", type: "TEXT" },
        { name: "Language", type: "TEXT" },
        { name: "IsOfficial", type: "TEXT" },
        { name: "Percentage", type: "REAL" },
      ],
    },
  ],
  suggestions: [
    "Топ-10 стран по населению",
    "Среднее население городов по континентам",
    "Сколько официальных языков в каждой стране",
  ],
};

export const DEMO_DATA_SOURCES: DemoDataSource[] = [concertSinger, wrestler, world1];

// Human-readable labels for SQL aliases / column names that the model
// generates. Used by the chart renderer to replace title=field on axes,
// legends, tooltips. Add new entries as new demo queries surface them.
export const COLUMN_LABELS_RU: Record<string, string> = {
  // singer / concert_singer
  NumberOfSingers: "Количество певцов",
  number_of_singers: "Количество певцов",
  concerts_count: "Количество концертов",
  Concerts: "Количество концертов",
  average_age: "Средний возраст",
  avg_age: "Средний возраст",
  Age: "Возраст",
  Country: "Страна",
  Year: "Год",
  Name: "Название",
  Song_Name: "Песня",
  Song_release_year: "Год выпуска песни",
  Is_male: "Мужской",
  // stadium
  Capacity: "Вместимость",
  Highest: "Максимум посещаемости",
  Lowest: "Минимум посещаемости",
  Average: "Средняя посещаемость",
  Location: "Город",
  // world_1
  Population: "Население",
  Continent: "Континент",
  Region: "Регион",
  SurfaceArea: "Площадь, км²",
  GNP: "ВВП",
  Language: "Язык",
  IsOfficial: "Официальный",
  Percentage: "Доля, %",
  // wrestler
  Days_held: "Дней удержания титула",
  Reign: "Сроки удержания",
  Event: "Событие",
  Eliminated_By: "Кем выбит",
  Elimination_Move: "Приём",
  Time: "Время",
};

export function labelFor(field: string | undefined | null): string {
  if (!field) return "";
  return COLUMN_LABELS_RU[field] ?? field;
}

export const DEFAULT_DATA_SOURCE_ID = concertSinger.id;

export function findDataSource(id: string): DemoDataSource {
  return DEMO_DATA_SOURCES.find((d) => d.id === id) ?? concertSinger;
}

// Legacy named exports kept for backward compat with the previous single-source layout.
export const DEMO_DATA_SOURCE_ID = concertSinger.id;
export const DEMO_DATA_SOURCE_LABEL = concertSinger.label;
export const DEMO_TABLES = concertSinger.tables;
export const SUGGESTED_QUERIES = concertSinger.suggestions;
