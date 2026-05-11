from colab.db_engine import DatabaseSchema
from colab.metadata import infer_field_metadata


def test_infers_russian_year_month_as_time_and_cyrillic_aggregate_alias() -> None:
    fields, warnings = infer_field_metadata(
        columns=["год", "месяц", "выручка"],
        column_sql_types={},
        sample_rows=[
            {"год": 2024, "месяц": 1, "выручка": 100.0},
            {"год": 2024, "месяц": 2, "выручка": 200.0},
        ],
        sql=(
            "SELECT EXTRACT(YEAR FROM o.дата_заказа) AS год, "
            "EXTRACT(MONTH FROM o.дата_заказа) AS месяц, "
            "SUM(p.цена_за_единицу * p.количество) AS выручка "
            "FROM заказы o JOIN позиции_заказа p ON o.заказ_id = p.заказ_id "
            "GROUP BY год, месяц"
        ),
        schema=DatabaseSchema(data_source_id="northwind_ru", engine="postgres", tables=[]),
    )

    by_name = {field.name: field for field in fields}
    assert warnings == []
    assert by_name["год"].semantic_role == "time"
    assert by_name["год"].periodicity == "year"
    assert by_name["месяц"].semantic_role == "time"
    assert by_name["месяц"].periodicity == "month"
    assert by_name["выручка"].semantic_role == "measure"
    assert by_name["выручка"].provenance.aggregation == "sum"
    assert by_name["выручка"].default_aggregation == "none"
