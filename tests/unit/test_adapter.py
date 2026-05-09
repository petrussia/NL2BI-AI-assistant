import pytest

from contracts.extraction import DataExtractionResponse, DataSourceInfo, ResultTable
from services.adapter.extraction_to_visualization import AdapterError, adapt_extraction_to_visualization


def test_adapter_infers_missing_metadata():
    response = DataExtractionResponse(
        request_id="r1",
        status="success",
        user_query="Сравни продажи по категориям",
        data_source=DataSourceInfo(id="demo_sales"),
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


def test_adapter_rejects_invalid_columns():
    response = DataExtractionResponse(
        request_id="r1",
        status="success",
        user_query="bad",
        data_source=DataSourceInfo(id="demo_sales"),
        result_table=ResultTable(
            columns=["category", "revenue"],
            rows=[{"category": "A"}],
            row_count=1,
        ),
    )
    with pytest.raises(AdapterError):
        adapt_extraction_to_visualization(response)

