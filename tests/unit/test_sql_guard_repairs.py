from colab.db_engine import ColumnSchema, DatabaseSchema, TableSchema
from colab.sql_guard import (
    repair_sql_for_empty_result,
    repair_sql_for_execution,
    repair_sql_for_semantic_mismatch,
    validate_select_only,
)


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
            "SELECT c.segment, MIN(SUM(oi.quantity * oi.unit_price * (1 - oi.discount_pct))) AS min_order_revenue "
            "FROM customers c JOIN orders o ON c.customer_id = o.customer_id "
            "JOIN order_items oi ON o.order_id = oi.order_id "
            "GROUP BY c.segment"
        ),
        engine="duckdb",
        data_source_id="spider2_retail_dbt",
        user_query="Min, avg, max order revenue by customer segment",
        error="Binder Error: aggregate function calls cannot be nested",
    )

    assert repaired is not None
    assert "WITH order_revenue AS" in repaired
    assert "MIN(order_revenue) AS min_order_revenue" in repaired
    assert "AVG(order_revenue) AS avg_order_revenue" in repaired


def test_repairs_spider2_grouped_boxplot_order_value_to_raw_values() -> None:
    repaired = repair_sql_for_semantic_mismatch(
        (
            "WITH order_values AS ("
            "SELECT o.order_id, c.segment, SUM(oi.quantity * oi.unit_price * (1 - oi.discount_pct)) AS order_value "
            "FROM orders o JOIN customers c ON o.customer_id = c.customer_id "
            "JOIN order_items oi ON o.order_id = oi.order_id GROUP BY o.order_id, c.segment) "
            "SELECT segment, MIN(order_value) AS min_order_value, AVG(order_value) AS avg_order_value, "
            "quantile_cont(order_value, 0.25) AS q1_order_value, quantile_cont(order_value, 0.75) AS q3_order_value "
            "FROM order_values GROUP BY segment"
        ),
        engine="duckdb",
        data_source_id="spider2_retail_dbt",
        user_query="Покажи ящик с усами стоимости заказов по сегментам клиентов",
    )

    assert repaired is not None
    assert validate_select_only(repaired).ok
    assert "c.segment" in repaired
    assert "order_value" in repaired
    assert "quantity * oi.unit_price" in repaired
    assert "quantile" not in repaired.lower()
    assert "AVG(" not in repaired.upper()


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


def test_repairs_moscow_area_okrugs_total_to_entity_grain() -> None:
    repaired = repair_sql_for_semantic_mismatch(
        "SELECT SUM(area_km2) AS total_area FROM okrugs LIMIT 1000",
        engine="sqlite",
        data_source_id="moscow_open",
        user_query="Площадь округов Москвы",
    )

    assert repaired is not None
    assert validate_select_only(repaired).ok
    assert "name AS okrug" in repaired
    assert "area_km2" in repaired
    assert "SUM(" not in repaired.upper()


def test_keeps_moscow_total_area_when_user_asks_total() -> None:
    repaired = repair_sql_for_semantic_mismatch(
        "SELECT SUM(area_km2) AS total_area FROM okrugs LIMIT 1000",
        engine="sqlite",
        data_source_id="moscow_open",
        user_query="Общая площадь округов Москвы",
    )

    assert repaired is None


def test_repairs_spider_stadium_point_capacity_to_entity_grain() -> None:
    repaired = repair_sql_for_semantic_mismatch(
        "SELECT AVG(Capacity) AS average_capacity, Name FROM stadium LIMIT 1000",
        engine="sqlite",
        data_source_id="demo_concert_singer",
        user_query="Покажи точками среднюю вместимость стадиона и названия",
    )

    assert repaired is not None
    assert validate_select_only(repaired).ok
    assert "Name" in repaired
    assert "Capacity" in repaired
    assert "AVG(" not in repaired.upper()


def test_repairs_spider_stadium_xy_scatter_to_two_measures() -> None:
    repaired = repair_sql_for_semantic_mismatch(
        "SELECT Name, Capacity FROM stadium LIMIT 1000",
        engine="sqlite",
        data_source_id="demo_concert_singer",
        user_query="Построй scatter plot: вместимость стадиона по X и средняя посещаемость по Y; подпиши точки названием",
    )

    assert repaired is not None
    assert validate_select_only(repaired).ok
    assert "Capacity AS X" in repaired
    assert "Average AS Y" in repaired
    assert "Name AS Label" in repaired


def test_repairs_northwind_boxplot_delivery_cost_to_raw_values() -> None:
    repaired = repair_sql_for_semantic_mismatch(
        (
            "SELECT MIN(стоимость_доставки) AS min_delivery_cost, "
            "MAX(стоимость_доставки) AS max_delivery_cost FROM заказы LIMIT 1000"
        ),
        engine="postgres",
        data_source_id="northwind_ru",
        user_query="Построй boxplot стоимости доставки",
    )

    assert repaired is not None
    assert validate_select_only(repaired).ok
    assert "стоимость_доставки" in repaired
    assert "MIN(" not in repaired.upper()
    assert "MAX(" not in repaired.upper()


def test_repairs_northwind_grouped_boxplot_delivery_cost_to_raw_values() -> None:
    repaired = repair_sql_for_semantic_mismatch(
        "SELECT k.сегмент, percentile_cont(0.5) WITHIN GROUP (ORDER BY o.стоимость_доставки) FROM заказы o JOIN клиенты k ON o.клиент_id = k.клиент_id GROUP BY k.сегмент",
        engine="postgres",
        data_source_id="northwind_ru",
        user_query="Покажи boxplot стоимости доставки по сегментам клиентов",
    )

    assert repaired is not None
    assert validate_select_only(repaired).ok
    assert "k.сегмент" in repaired
    assert "o.стоимость_доставки" in repaired
    assert "percentile" not in repaired.lower()


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
