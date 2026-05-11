from contracts.extraction import DataExtractionResponse, DataSourceInfo, FieldMetadata, FieldProvenance, ResultTable
from contracts.visualization import VisualizationRequest
from services.adapter.extraction_to_visualization import adapt_extraction_to_visualization
from services.visualization.cpu_visualization_service import CpuVisualizationService
from services.visualization.render import chart_spec


def test_time_series_becomes_line():
    request = VisualizationRequest(
        request_id="r1",
        user_query="Покажи динамику продаж по месяцам",
        data_source=DataSourceInfo(id="demo_concert_singer"),
        result_table=ResultTable(
            columns=["month", "revenue"],
            rows=[
                {"month": "2026-01", "revenue": 10},
                {"month": "2026-02", "revenue": 20},
                {"month": "2026-03", "revenue": 30},
            ],
            row_count=3,
        ),
        field_metadata=[
            FieldMetadata(name="month", data_type="date", semantic_role="time", allowed_aggregations=["none"], default_aggregation="none"),
            FieldMetadata(name="revenue", data_type="number", semantic_role="measure", allowed_aggregations=["sum"], default_aggregation="sum"),
        ],
    )
    response = CpuVisualizationService().visualize(request)
    assert response.status == "success"
    assert response.selected_view.chart_type == "line"


def test_year_month_result_uses_combined_month_axis():
    request = VisualizationRequest(
        request_id="r1",
        user_query="Number of completed tasks by month",
        data_source=DataSourceInfo(id="spider2_asana_dbt"),
        result_table=ResultTable(
            columns=["year", "month", "completed_tasks_count"],
            rows=[
                {"year": 2023, "month": 8, "completed_tasks_count": 4},
                {"year": 2023, "month": 9, "completed_tasks_count": 2},
                {"year": 2024, "month": 1, "completed_tasks_count": 1},
            ],
            row_count=3,
        ),
        field_metadata=[
            FieldMetadata(name="year", data_type="number", semantic_role="time", allowed_aggregations=["none"], default_aggregation="none"),
            FieldMetadata(name="month", data_type="number", semantic_role="time", allowed_aggregations=["none"], default_aggregation="none"),
            FieldMetadata(name="completed_tasks_count", data_type="number", semantic_role="measure", allowed_aggregations=["none"], default_aggregation="none"),
        ],
    )

    response = CpuVisualizationService().visualize(request)

    assert response.status == "success"
    spec = response.selected_view.spec
    assert spec["encoding"]["x"]["field"] == "__period_month"
    assert spec["encoding"]["x"]["type"] == "temporal"
    assert spec["encoding"]["x"]["axis"]["format"] == "%Y-%m"
    assert spec["data"]["values"][0]["__period_month"] == "2023-08-01"
    assert spec["data"]["values"][2]["__period_month"] == "2024-01-01"


def test_empty_rows_failed_safely():
    request = VisualizationRequest(
        request_id="r1",
        user_query="Покажи пустой результат",
        data_source=DataSourceInfo(id="demo_concert_singer"),
        result_table=ResultTable(columns=["category", "revenue"], rows=[], row_count=0),
        field_metadata=[
            FieldMetadata(name="category", data_type="string", semantic_role="dimension"),
            FieldMetadata(name="revenue", data_type="number", semantic_role="measure"),
        ],
    )
    response = CpuVisualizationService().visualize(request)
    assert response.status == "failed"
    assert response.errors[0].code == "empty_result"


def test_derived_count_alias_does_not_add_vega_aggregate():
    table = ResultTable(
        columns=["Country", "NumberOfSingers"],
        rows=[{"Country": "France", "NumberOfSingers": 2}],
        row_count=1,
    )
    spec = chart_spec(
        chart_type="bar",
        title="Сравнение по категориям",
        x_field=FieldMetadata(name="Country", data_type="string", semantic_role="dimension"),
        y_field=FieldMetadata(
            name="NumberOfSingers",
            data_type="number",
            semantic_role="measure",
            default_aggregation="count",
            provenance=FieldProvenance(expression="*", aggregation="count", derived=True),
        ),
        table=table,
    )
    assert spec["encoding"]["y"]["field"] == "NumberOfSingers"
    assert "aggregate" not in spec["encoding"]["y"]


def test_raw_measure_can_still_use_vega_aggregate():
    table = ResultTable(
        columns=["Country", "Capacity"],
        rows=[{"Country": "France", "Capacity": 10}],
        row_count=1,
    )
    spec = chart_spec(
        chart_type="bar",
        title="Сравнение по категориям",
        x_field=FieldMetadata(name="Country", data_type="string", semantic_role="dimension"),
        y_field=FieldMetadata(
            name="Capacity",
            data_type="number",
            semantic_role="measure",
            default_aggregation="sum",
            provenance=FieldProvenance(expression="stadium.Capacity", aggregation=None, derived=False),
        ),
        table=table,
    )
    assert spec["encoding"]["y"]["aggregate"] == "sum"


def test_real_colab_like_category_count_alias_has_no_vega_aggregate():
    extraction = DataExtractionResponse(
        request_id="r1",
        status="success",
        user_query="Сравни количество певцов по странам",
        data_source=DataSourceInfo(id="demo_concert_singer", dialect="sqlite"),
        result_table=ResultTable(
            columns=["Country", "NumberOfSingers"],
            rows=[
                {"Country": "France", "NumberOfSingers": 2},
                {"Country": "United States", "NumberOfSingers": 1},
            ],
            row_count=2,
            truncated=False,
        ),
        field_metadata=[
            FieldMetadata(
                name="Country",
                data_type="string",
                semantic_role="dimension",
                allowed_aggregations=["count"],
                default_aggregation="count",
                provenance=FieldProvenance(expression=None, aggregation=None, derived=False),
            ),
            FieldMetadata(
                name="NumberOfSingers",
                data_type="number",
                semantic_role="measure",
                allowed_aggregations=["none"],
                default_aggregation="none",
                provenance=FieldProvenance(expression="*", aggregation="count", derived=True),
            ),
        ],
    )

    request = adapt_extraction_to_visualization(extraction).request
    response = CpuVisualizationService().visualize(request)

    assert response.selected_view.chart_type == "bar"
    y_encoding = response.selected_view.spec["encoding"]["y"]
    assert y_encoding["field"] == "NumberOfSingers"
    assert "aggregate" not in y_encoding
    assert response.explanation.used_aggregations == ["count"]
