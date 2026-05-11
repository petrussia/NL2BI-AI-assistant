import pytest

from contracts.extraction import DataExtractionResponse, DataSourceInfo, FieldMetadata, ResultTable
from services.adapter.extraction_to_visualization import AdapterError, adapt_extraction_to_visualization


def test_adapter_infers_missing_metadata():
    response = DataExtractionResponse(
        request_id="r1",
        status="success",
        user_query="Сравни продажи по категориям",
        data_source=DataSourceInfo(id="demo_concert_singer"),
        result_table=ResultTable(
            columns=["category", "revenue"],
            rows=[{"category": "A", "revenue": 10}],
            row_count=1,
        ),
        field_metadata=[],
    )
    result = adapt_extraction_to_visualization(response)
    roles = {item.name: item.semantic_role for item in result.request.field_metadata}
    assert roles == {"category": "dimension", "revenue": "measure"}
    assert result.warnings


def test_adapter_infers_russian_year_month_as_time():
    response = DataExtractionResponse(
        request_id="r1",
        status="success",
        user_query="Динамика продаж по месяцам в 2024",
        data_source=DataSourceInfo(id="northwind_ru"),
        result_table=ResultTable(
            columns=["год", "месяц", "выручка"],
            rows=[{"год": 2024, "месяц": 1, "выручка": 10}],
            row_count=1,
        ),
        field_metadata=[],
    )

    result = adapt_extraction_to_visualization(response)

    roles = {item.name: item.semantic_role for item in result.request.field_metadata}
    assert roles == {"год": "time", "месяц": "time", "выручка": "measure"}


def test_adapter_infers_decade_as_time():
    response = DataExtractionResponse(
        request_id="r1",
        status="success",
        user_query="Сколько станций открыто по десятилетиям",
        data_source=DataSourceInfo(id="moscow_open"),
        result_table=ResultTable(
            columns=["decade", "station_count"],
            rows=[{"decade": 1980, "station_count": 3}],
            row_count=1,
        ),
        field_metadata=[],
    )

    result = adapt_extraction_to_visualization(response)

    roles = {item.name: item.semantic_role for item in result.request.field_metadata}
    assert roles == {"decade": "time", "station_count": "measure"}


def test_adapter_corrects_russian_time_metadata_misclassified_as_measure():
    response = DataExtractionResponse(
        request_id="r1",
        status="success",
        user_query="Динамика продаж по месяцам в 2024",
        data_source=DataSourceInfo(id="northwind_ru"),
        result_table=ResultTable(
            columns=["год", "месяц", "выручка"],
            rows=[{"год": 2024, "месяц": 1, "выручка": 10}],
            row_count=1,
        ),
        field_metadata=[
            FieldMetadata(name="год", data_type="number", semantic_role="measure"),
            FieldMetadata(name="месяц", data_type="number", semantic_role="measure"),
            FieldMetadata(name="выручка", data_type="number", semantic_role="measure"),
        ],
    )

    result = adapt_extraction_to_visualization(response)

    roles = {item.name: item.semantic_role for item in result.request.field_metadata}
    assert roles == {"год": "time", "месяц": "time", "выручка": "measure"}


def test_adapter_rejects_invalid_columns():
    response = DataExtractionResponse(
        request_id="r1",
        status="success",
        user_query="bad",
        data_source=DataSourceInfo(id="demo_concert_singer"),
        result_table=ResultTable(
            columns=["category", "revenue"],
            rows=[{"category": "A"}],
            row_count=1,
        ),
    )
    with pytest.raises(AdapterError):
        adapt_extraction_to_visualization(response)
