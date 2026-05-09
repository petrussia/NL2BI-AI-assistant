from contracts.extraction import DataSourceInfo, FieldMetadata, ResultTable
from contracts.visualization import VisualizationRequest
from services.visualization.cpu_visualization_service import CpuVisualizationService


def test_all_text_fields_falls_back_to_table():
    request = VisualizationRequest(
        request_id="r1",
        user_query="Покажи список комментариев",
        data_source=DataSourceInfo(id="demo_sales"),
        result_table=ResultTable(
            columns=["comment"],
            rows=[{"comment": "ok"}],
            row_count=1,
        ),
        field_metadata=[FieldMetadata(name="comment", data_type="string", semantic_role="text")],
    )
    response = CpuVisualizationService().visualize(request)
    assert response.selected_view.type == "table"


def test_invalid_metadata_field_failed():
    request = VisualizationRequest(
        request_id="r1",
        user_query="Покажи продажи",
        data_source=DataSourceInfo(id="demo_sales"),
        result_table=ResultTable(
            columns=["revenue"],
            rows=[{"revenue": 10}],
            row_count=1,
        ),
        field_metadata=[FieldMetadata(name="missing", data_type="number", semantic_role="measure")],
    )
    response = CpuVisualizationService().visualize(request)
    assert response.status == "failed"
    assert response.errors[0].code == "invalid_field_metadata"

