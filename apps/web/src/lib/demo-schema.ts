// Static description of the bundled demo data source.
// Source of truth: Spider `concert_singer` SQLite. Kept here so the UI can
// surface schema hints + working sample queries without an extra round-trip.

export type DemoColumn = {
  name: string;
  type: "INTEGER" | "TEXT" | "REAL" | "NUMERIC";
};

export type DemoTable = {
  name: string;
  description: string;
  columns: DemoColumn[];
};

export const DEMO_DATA_SOURCE_ID = "demo_concert_singer";
export const DEMO_DATA_SOURCE_LABEL = "Spider concert_singer";

export const DEMO_TABLES: DemoTable[] = [
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
      { name: "Song_release_year", type: "TEXT" },
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
      { name: "Stadium_ID", type: "TEXT" },
      { name: "Year", type: "TEXT" },
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
];

export const SUGGESTED_QUERIES: string[] = [
  "Сравни количество певцов по странам",
  "Покажи топ-5 стадионов по вместимости",
  "Количество концертов по годам",
  "Средний возраст певцов по странам",
];
