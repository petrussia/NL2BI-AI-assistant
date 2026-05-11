// Static description of the bundled demo data sources.
// v0.11 — 5 sources, one per benchmark + 1 open-data + 1 production DBMS.
// Engine attribute drives the badge shown in the source picker.
// Authoritative source: colab/demo_data/data_sources.json on the server.

export type DemoEngine = "sqlite" | "duckdb" | "postgres";

export type DemoColumn = {
  name: string;
  type: "INTEGER" | "TEXT" | "REAL" | "NUMERIC" | "DATE" | "TIMESTAMP" | "BOOLEAN";
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
  engine: DemoEngine;
  tables: DemoTable[];
  suggestions: string[];
};

// ---------- 1. Spider 1.0 · concert_singer (SQLite) ----------
const concertSinger: DemoDataSource = {
  id: "demo_concert_singer",
  label: "Spider 1.0 · concert_singer",
  blurb: "Шотландские стадионы, певцы и концерты — каноничный Spider бенчмарк.",
  engine: "sqlite",
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

// ---------- 2. BIRD · student_club (SQLite) ----------
const birdStudentClub: DemoDataSource = {
  id: "bird_student_club",
  label: "BIRD · student_club",
  blurb: "Студенческий клуб: события, посещаемость, бюджет, специализации.",
  engine: "sqlite",
  tables: [
    {
      name: "member",
      description: "Члены клуба: имя, фамилия, специальность, телефон, email.",
      columns: [
        { name: "member_id", type: "TEXT" },
        { name: "first_name", type: "TEXT" },
        { name: "last_name", type: "TEXT" },
        { name: "email", type: "TEXT" },
        { name: "position", type: "TEXT" },
        { name: "t_shirt_size", type: "TEXT" },
        { name: "phone", type: "TEXT" },
        { name: "zip", type: "INTEGER" },
        { name: "link_to_major", type: "TEXT" },
      ],
    },
    {
      name: "event",
      description: "События клуба: название, дата, тип (Meeting/Social/Workshop).",
      columns: [
        { name: "event_id", type: "TEXT" },
        { name: "event_name", type: "TEXT" },
        { name: "event_date", type: "TEXT" },
        { name: "type", type: "TEXT" },
        { name: "notes", type: "TEXT" },
        { name: "location", type: "TEXT" },
        { name: "status", type: "TEXT" },
      ],
    },
    {
      name: "attendance",
      description: "Посещаемость: какой член клуба был на каком событии.",
      columns: [
        { name: "link_to_event", type: "TEXT" },
        { name: "link_to_member", type: "TEXT" },
      ],
    },
    {
      name: "budget",
      description: "Бюджет: на какое событие, какая категория, сумма.",
      columns: [
        { name: "budget_id", type: "TEXT" },
        { name: "category", type: "TEXT" },
        { name: "spent", type: "REAL" },
        { name: "remaining", type: "REAL" },
        { name: "amount", type: "INTEGER" },
        { name: "event_status", type: "TEXT" },
        { name: "link_to_event", type: "TEXT" },
      ],
    },
    {
      name: "expense",
      description: "Расходы: дата, категория, сумма, описание.",
      columns: [
        { name: "expense_id", type: "TEXT" },
        { name: "expense_description", type: "TEXT" },
        { name: "expense_date", type: "TEXT" },
        { name: "cost", type: "REAL" },
        { name: "approved", type: "TEXT" },
        { name: "link_to_budget", type: "TEXT" },
        { name: "link_to_member", type: "TEXT" },
      ],
    },
    {
      name: "income",
      description: "Поступления денег: дата, источник, сумма.",
      columns: [
        { name: "income_id", type: "TEXT" },
        { name: "date_received", type: "TEXT" },
        { name: "amount", type: "INTEGER" },
        { name: "source", type: "TEXT" },
        { name: "notes", type: "TEXT" },
        { name: "link_to_member", type: "TEXT" },
      ],
    },
    {
      name: "major",
      description: "Справочник специальностей и факультетов.",
      columns: [
        { name: "major_id", type: "TEXT" },
        { name: "major_name", type: "TEXT" },
        { name: "department", type: "TEXT" },
        { name: "college", type: "TEXT" },
      ],
    },
  ],
  suggestions: [
    "Сколько событий клуб провёл за каждый месяц",
    "Топ-5 членов клуба по посещаемости",
    "Расходы по категориям бюджета",
    "Сколько участников на каждом типе событий",
  ],
};

// ---------- 3. Spider 2 · asana (DuckDB) ----------
const spider2Asana: DemoDataSource = {
  id: "spider2_asana_dbt",
  label: "Spider 2 · asana (dbt)",
  blurb: "Asana project management: задачи, проекты, команды, пользователи. Аналитический стек DuckDB + dbt.",
  engine: "duckdb",
  tables: [
    {
      name: "project_data",
      description: "Проекты: владелец, статус, дата создания, привязка к команде.",
      columns: [
        { name: "id", type: "TEXT" },
        { name: "name", type: "TEXT" },
        { name: "owner_id", type: "TEXT" },
        { name: "team_id", type: "TEXT" },
        { name: "current_status", type: "TEXT" },
        { name: "created_at", type: "TIMESTAMP" },
        { name: "modified_at", type: "TIMESTAMP" },
        { name: "archived", type: "BOOLEAN" },
      ],
    },
    {
      name: "task_data",
      description: "Задачи: исполнитель, родительская задача, completed, due_on.",
      columns: [
        { name: "id", type: "TEXT" },
        { name: "name", type: "TEXT" },
        { name: "assignee_id", type: "TEXT" },
        { name: "completed", type: "BOOLEAN" },
        { name: "completed_at", type: "TIMESTAMP" },
        { name: "created_at", type: "TIMESTAMP" },
        { name: "due_on", type: "TIMESTAMP" },
        { name: "parent_id", type: "INTEGER" },
      ],
    },
    {
      name: "user_data",
      description: "Пользователи Asana: ФИО, email, команда.",
      columns: [
        { name: "id", type: "TEXT" },
        { name: "name", type: "TEXT" },
        { name: "email", type: "TEXT" },
      ],
    },
    {
      name: "team_data",
      description: "Команды.",
      columns: [
        { name: "id", type: "TEXT" },
        { name: "name", type: "TEXT" },
      ],
    },
    {
      name: "project_task_data",
      description: "Связь project ↔ task.",
      columns: [
        { name: "project_id", type: "TEXT" },
        { name: "task_id", type: "TEXT" },
      ],
    },
    {
      name: "story_data",
      description: "История изменений задач (story = action log).",
      columns: [
        { name: "id", type: "TEXT" },
        { name: "target_id", type: "TEXT" },
        { name: "type", type: "TEXT" },
        { name: "created_at", type: "TIMESTAMP" },
        { name: "created_by_id", type: "TEXT" },
        { name: "text", type: "TEXT" },
      ],
    },
  ],
  suggestions: [
    "How many tasks are there in total",
    "Top 5 users by tasks assigned",
    "How many tasks per project",
    "Number of completed tasks by month",
  ],
};

// ---------- 4. Moscow · open data (SQLite) ----------
const moscowOpen: DemoDataSource = {
  id: "moscow_open",
  label: "Москва · метро и районы",
  blurb: "Открытые данные Москвы: административные округа, районы, линии и станции метро.",
  engine: "sqlite",
  tables: [
    {
      name: "okrugs",
      description: "Административные округа Москвы (12 штук).",
      columns: [
        { name: "okrug_id", type: "INTEGER" },
        { name: "name", type: "TEXT" },
        { name: "code", type: "TEXT" },
        { name: "area_km2", type: "REAL" },
        { name: "population", type: "INTEGER" },
        { name: "established_year", type: "INTEGER" },
      ],
    },
    {
      name: "districts",
      description: "Районы Москвы с привязкой к округам.",
      columns: [
        { name: "district_id", type: "INTEGER" },
        { name: "name", type: "TEXT" },
        { name: "okrug_id", type: "INTEGER" },
        { name: "area_km2", type: "REAL" },
        { name: "population", type: "INTEGER" },
      ],
    },
    {
      name: "metro_lines",
      description: "Линии метро: номер, название, цвет, год открытия, длина.",
      columns: [
        { name: "line_id", type: "INTEGER" },
        { name: "number", type: "TEXT" },
        { name: "name", type: "TEXT" },
        { name: "color_hex", type: "TEXT" },
        { name: "year_opened", type: "INTEGER" },
        { name: "length_km", type: "REAL" },
      ],
    },
    {
      name: "metro_stations",
      description: "Станции метро: линия, район, год открытия, пассажиропоток, пересадка.",
      columns: [
        { name: "station_id", type: "INTEGER" },
        { name: "name", type: "TEXT" },
        { name: "line_id", type: "INTEGER" },
        { name: "district_id", type: "INTEGER" },
        { name: "opened_year", type: "INTEGER" },
        { name: "daily_passengers", type: "INTEGER" },
        { name: "is_transfer", type: "INTEGER" },
      ],
    },
  ],
  suggestions: [
    "Топ-5 районов Москвы по населению",
    "Сколько станций метро на каждой линии",
    "Самые загруженные станции метро",
    "Площадь округов Москвы",
  ],
};

// ---------- 5. Northwind RU · PostgreSQL ----------
const northwindRu: DemoDataSource = {
  id: "northwind_ru",
  label: "Northwind RU",
  blurb: "Классическая BI-схема (продажи) полностью на русских названиях. Живой PostgreSQL.",
  engine: "postgres",
  tables: [
    {
      name: "клиенты",
      description: "Покупатели: компания, контактное лицо, город, регион, сегмент (B2B/Розница/HoReCa).",
      columns: [
        { name: "клиент_id", type: "INTEGER" },
        { name: "название_компании", type: "TEXT" },
        { name: "контактное_лицо", type: "TEXT" },
        { name: "город", type: "TEXT" },
        { name: "регион_id", type: "INTEGER" },
        { name: "сегмент", type: "TEXT" },
      ],
    },
    {
      name: "заказы",
      description: "Заказы клиентов: дата, доставка, привязка к сотруднику.",
      columns: [
        { name: "заказ_id", type: "INTEGER" },
        { name: "клиент_id", type: "INTEGER" },
        { name: "сотрудник_id", type: "INTEGER" },
        { name: "дата_заказа", type: "DATE" },
        { name: "дата_доставки", type: "DATE" },
        { name: "стоимость_доставки", type: "NUMERIC" },
      ],
    },
    {
      name: "позиции_заказа",
      description: "Позиции в заказах: товар, количество, цена, скидка.",
      columns: [
        { name: "позиция_id", type: "INTEGER" },
        { name: "заказ_id", type: "INTEGER" },
        { name: "товар_id", type: "INTEGER" },
        { name: "цена_за_единицу", type: "NUMERIC" },
        { name: "количество", type: "INTEGER" },
        { name: "скидка", type: "NUMERIC" },
      ],
    },
    {
      name: "товары",
      description: "Каталог товаров: цена, единица, категория.",
      columns: [
        { name: "товар_id", type: "INTEGER" },
        { name: "название", type: "TEXT" },
        { name: "категория_id", type: "INTEGER" },
        { name: "цена_за_единицу", type: "NUMERIC" },
        { name: "единица_измерения", type: "TEXT" },
        { name: "снят_с_продажи", type: "BOOLEAN" },
      ],
    },
    {
      name: "категории",
      description: "Категории товаров.",
      columns: [
        { name: "категория_id", type: "INTEGER" },
        { name: "название", type: "TEXT" },
        { name: "описание", type: "TEXT" },
      ],
    },
    {
      name: "сотрудники",
      description: "Менеджеры: ФИО, должность, дата найма, регион.",
      columns: [
        { name: "сотрудник_id", type: "INTEGER" },
        { name: "фио", type: "TEXT" },
        { name: "должность", type: "TEXT" },
        { name: "дата_найма", type: "DATE" },
        { name: "регион_id", type: "INTEGER" },
      ],
    },
    {
      name: "регионы",
      description: "Регионы РФ: федеральный округ, население.",
      columns: [
        { name: "регион_id", type: "INTEGER" },
        { name: "название", type: "TEXT" },
        { name: "федеральный_округ", type: "TEXT" },
        { name: "население_млн", type: "REAL" },
      ],
    },
  ],
  suggestions: [
    "Топ-10 клиентов по выручке за 2024 год",
    "Динамика продаж по месяцам в 2024",
    "Средний чек по сегментам клиентов",
    "Выручка менеджеров по продажам",
    "Сколько товаров продано в каждой категории",
  ],
};

export const DEMO_DATA_SOURCES: DemoDataSource[] = [
  concertSinger,
  birdStudentClub,
  spider2Asana,
  moscowOpen,
  northwindRu,
];

// Human labels used by chart axis/tooltip rendering. Add entries as new
// demo queries surface them.
export const COLUMN_LABELS_RU: Record<string, string> = {
  // Spider concert_singer
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
  Capacity: "Вместимость",
  Highest: "Максимум посещаемости",
  Lowest: "Минимум посещаемости",
  Average: "Средняя посещаемость",
  Location: "Город",
  // BIRD student_club
  first_name: "Имя",
  last_name: "Фамилия",
  event_name: "Событие",
  event_date: "Дата события",
  major_name: "Специальность",
  department: "Факультет",
  college: "Колледж",
  cost: "Стоимость",
  amount: "Сумма",
  category: "Категория",
  spent: "Потрачено",
  remaining: "Остаток",
  // Asana
  total_tasks: "Всего задач",
  total: "Всего",
  completed: "Выполнено",
  // Moscow
  okrug: "Округ",
  okrug_id: "Округ",
  district_id: "Район",
  population: "Население",
  area_km2: "Площадь, км²",
  line_id: "Линия",
  station_id: "Станция",
  opened_year: "Год открытия",
  daily_passengers: "Пассажиропоток (день)",
  is_transfer: "Пересадочная",
  // Northwind RU
  название_компании: "Компания",
  выручка: "Выручка",
  название: "Название",
  сегмент: "Сегмент",
  город: "Город",
  фио: "ФИО",
  должность: "Должность",
  количество: "Количество",
  количество_проданных_товаров: "Кол-во проданных",
  цена_за_единицу: "Цена",
  скидка: "Скидка",
  дата_заказа: "Дата заказа",
  // common
  count: "Кол-во",
  total_count: "Всего",
};

export function labelFor(field: string | undefined | null): string {
  if (!field) return "";
  return COLUMN_LABELS_RU[field] ?? field;
}

export const DEFAULT_DATA_SOURCE_ID = concertSinger.id;

export function findDataSource(id: string): DemoDataSource {
  return DEMO_DATA_SOURCES.find((d) => d.id === id) ?? concertSinger;
}

// Engine display labels for the source picker badge.
export const ENGINE_LABELS: Record<DemoEngine, string> = {
  sqlite: "SQLite",
  duckdb: "DuckDB",
  postgres: "PostgreSQL",
};

// Legacy named exports kept for backward compat with the previous single-source layout.
export const DEMO_DATA_SOURCE_ID = concertSinger.id;
export const DEMO_DATA_SOURCE_LABEL = concertSinger.label;
export const DEMO_TABLES = concertSinger.tables;
export const SUGGESTED_QUERIES = concertSinger.suggestions;
