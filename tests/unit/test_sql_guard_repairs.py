from colab.db_engine import ColumnSchema, DatabaseSchema, TableSchema
from colab.sql_guard import repair_sql_for_empty_result, repair_sql_for_execution, validate_select_only


def _repair(query: str, sql: str, error: str) -> str:
    repaired = repair_sql_for_execution(
        sql,
        engine="postgres",
        data_source_id="northwind_ru",
        user_query=query,
        error=error,
    )
    assert repaired is not None
    assert validate_select_only(repaired).ok
    return repaired


def _schema(*tables: TableSchema) -> DatabaseSchema:
    return DatabaseSchema(data_source_id="test", engine="postgres", tables=list(tables))


def _table(name: str, *columns: str) -> TableSchema:
    return TableSchema(
        name=name,
        columns=[
            ColumnSchema(
                name=column,
                sql_type="TEXT",
                nullable=True,
                primary_key=False,
            )
            for column in columns
        ],
    )


def test_repairs_northwind_cyrillic_identifier_case() -> None:
    repaired = _repair(
        "Динамика заказов по месяцам 2024",
        "SELECT EXTRACT(MONTH FROM заказы.Дата_заказа) AS месяц FROM заказы",
        "column заказы.Дата_заказа does not exist",
    )

    assert "заказы.дата_заказа" in repaired
    assert "Дата_заказа" not in repaired


def test_repairs_northwind_having_alias() -> None:
    repaired = _repair(
        "Категории с выручкой больше миллиона",
        (
            "SELECT SUM(p.цена_за_единицу * p.количество * (1 - p.скидка)) AS выручка "
            "FROM позиции_заказа p HAVING выручка > 1000000"
        ),
        'column "выручка" does not exist',
    )

    assert "HAVING SUM(p.цена_за_единицу * p.количество * (1 - p.скидка)) > 1000000" in repaired


def test_repairs_northwind_federal_district_path() -> None:
    repaired = _repair(
        "Выручка по федеральным округам России",
        (
            "SELECT r.федеральный_округ, SUM(o.стоимость_доставки) AS выручка "
            "FROM заказы o JOIN регионы r ON o.регион_id = r.регион_id "
            "GROUP BY r.федеральный_округ"
        ),
        "column o.регион_id does not exist",
    )

    assert "JOIN клиенты k ON o.клиент_id = k.клиент_id" in repaired
    assert "JOIN позиции_заказа p ON o.заказ_id = p.заказ_id" in repaired


def test_repairs_northwind_above_average_order_value() -> None:
    repaired = _repair(
        "Клиенты с заказами выше среднего чека",
        "SELECT клиенты.регионы.название FROM клиенты",
        "invalid reference to FROM-clause entry",
    )

    assert "WITH order_totals AS" in repaired
    assert "WHERE ot.сумма_заказа > (SELECT AVG(сумма_заказа) FROM order_totals)" in repaired


def test_repairs_schema_qualified_cyrillic_typo() -> None:
    repaired = repair_sql_for_execution(
        sql=(
            "SELECT s.фои AS менеджер "
            "FROM сотрудники s "
            "JOIN заказы o ON s.сотрудник_id = o.сотрудник_id"
        ),
        engine="postgres",
        data_source_id="northwind_ru",
        user_query="Выручка менеджеров по продажам",
        error='column s.фои does not exist',
        schema=_schema(
            _table("сотрудники", "сотрудник_id", "фио"),
            _table("заказы", "сотрудник_id"),
        ),
    )

    assert repaired is not None
    assert "s.фио AS менеджер" in repaired


def test_does_not_fuzzy_repair_different_link_columns() -> None:
    repaired = repair_sql_for_execution(
        sql="SELECT expense.link_to_event FROM expense",
        engine="sqlite",
        data_source_id="other_source",
        user_query="Total expense amount per event",
        error="no such column: expense.link_to_event",
        schema=_schema(_table("expense", "expense_id", "link_to_budget", "link_to_member")),
    )

    assert repaired is None


def test_repairs_student_club_expense_event_hop() -> None:
    repaired = repair_sql_for_execution(
        sql="SELECT e.event_name, SUM(expense.cost) FROM expense JOIN event e ON expense.link_to_event = e.event_id",
        engine="sqlite",
        data_source_id="bird_student_club",
        user_query="Total expense amount per event",
        error="no such column: expense.link_to_event",
    )

    assert repaired is not None
    assert "JOIN budget b ON ex.link_to_budget = b.budget_id" in repaired
    assert "JOIN event e ON b.link_to_event = e.event_id" in repaired


def test_repairs_duckdb_nested_aggregate_with_cte() -> None:
    repaired = repair_sql_for_execution(
        sql=(
            "SELECT MIN(COUNT(task_data.id)) AS min_tasks "
            "FROM project_data JOIN project_task_data ON project_data.id = project_task_data.project_id "
            "JOIN task_data ON project_task_data.task_id = task_data.id "
            "GROUP BY project_data.id"
        ),
        engine="duckdb",
        data_source_id="spider2_asana_dbt",
        user_query="Min, avg, max number of tasks per project",
        error="Binder Error: aggregate function calls cannot be nested",
    )

    assert repaired is not None
    assert "WITH task_counts AS" in repaired
    assert "MIN(task_count) AS min_tasks" in repaired


def test_repairs_asana_empty_assignee_query_away_from_followers() -> None:
    repaired = repair_sql_for_empty_result(
        "SELECT u.name, COUNT(t.id) FROM user_data u JOIN task_follower_data tf ON u.id = tf.user_id "
        "JOIN task_data t ON tf.task_id = t.id GROUP BY u.name",
        engine="duckdb",
        data_source_id="spider2_asana_dbt",
        user_query="Number of tasks per user",
    )

    assert repaired is not None
    assert "JOIN task_data t ON u.id = t.assignee_id" in repaired
    assert "task_follower_data" not in repaired


def test_repairs_moscow_empty_central_okrug_value() -> None:
    repaired = repair_sql_for_empty_result(
        "SELECT ms.name FROM metro_stations ms JOIN districts d ON ms.district_id = d.district_id "
        "JOIN okrugs o ON d.okrug_id = o.okrug_id WHERE o.name = 'Центральный округ'",
        engine="sqlite",
        data_source_id="moscow_open",
        user_query="Самые загруженные станции в Центральном округе",
    )

    assert repaired is not None
    assert "o.name = 'Центральный'" in repaired


def test_repairs_northwind_empty_manager_filter() -> None:
    repaired = repair_sql_for_empty_result(
        "SELECT s.фио FROM сотрудники s WHERE s.должность = 'менеджер'",
        engine="postgres",
        data_source_id="northwind_ru",
        user_query="Выручка менеджеров по продажам",
    )

    assert repaired is not None
    assert "ILIKE '%менедж%'" in repaired
    assert "JOIN позиции_заказа p" in repaired
