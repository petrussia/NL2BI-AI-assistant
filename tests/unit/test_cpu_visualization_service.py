from contracts.extraction import DataSourceInfo, FieldMetadata, ResultTable
from contracts.visualization import VisualizationRequest
from services.visualization.cpu_visualization_service import CpuVisualizationService


def test_time_series_becomes_line():
    request = VisualizationRequest(
        request_id="r1",
        user_query="Покажи динамику продаж по месяцам",
        data_source=DataSourceInfo(id="demo_sales"),
        result_table=ResultTable(
            columns=["month", "revenue"],
            rows=[{"month": "2026-01", "revenue": 10}, {"month": "2026-02", "revenue": 20}],
            row_count=2,
        ),
        field_metadata=[
            FieldMetadata(name="month", data_type="date", semantic_role="time", allowed_aggregations=["none"], default_aggregation="none"),
            FieldMetadata(name="revenue", data_type="number", semantic_role="measure", allowed_aggregations=["sum"], default_aggregation="sum"),
        ],
    )
    response = CpuVisualizationService().visualize(request)
    assert response.status == "success"
    assert response.selected_view.chart_type == "line"


def test_empty_rows_failed_safely():
    request = VisualizationRequest(
        request_id="r1",
        user_query="Покажи пустой результат",
        data_source=DataSourceInfo(id="demo_sales"),
        result_table=ResultTable(columns=["category", "revenue"], rows=[], row_count=0),
        field_metadata=[
            FieldMetadata(name="category", data_type="string", semantic_role="dimension"),
            FieldMetadata(name="revenue", data_type="number", semantic_role="measure"),
        ],
    )
    response = CpuVisualizationService().visualize(request)
    assert response.status == "failed"
    assert response.errors[0].code == "empty_result"

