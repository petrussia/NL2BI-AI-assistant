from services.extraction_client.mock_client import MockExtractionClient
from services.gateway.config import REPO_ROOT
from contracts.extraction import DataExtractionRequest, DataSourceRequest


def _request(query: str) -> DataExtractionRequest:
    return DataExtractionRequest(
        request_id="r1",
        user_query=query,
        data_source=DataSourceRequest(id="demo_concert_singer"),
    )


def test_mock_time_series_selection():
    response = MockExtractionClient(REPO_ROOT / "demo_data").extract(_request("Покажи динамику по месяцам"))
    assert response.request_id == "r1"
    assert response.plan.intent == "trend"
    assert response.result_table.rows


def test_mock_empty_selection():
    response = MockExtractionClient(REPO_ROOT / "demo_data").extract(_request("empty result"))
    assert response.status == "partial_success"
    assert response.result_table.row_count == 0
