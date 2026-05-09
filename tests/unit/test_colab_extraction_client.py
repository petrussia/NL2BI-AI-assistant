import httpx

from contracts.extraction import DataExtractionRequest, DataSourceRequest
from services.extraction_client.colab_client import ColabExtractionClient


def _request() -> DataExtractionRequest:
    return DataExtractionRequest(
        request_id="r1",
        user_query="Покажи динамику",
        data_source=DataSourceRequest(id="demo_sales"),
    )


def test_colab_success_with_mock_transport():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "request_id": "r1",
                "status": "success",
                "user_query": "Покажи динамику",
                "data_source": {"id": "demo_sales", "dialect": "unknown"},
                "result_table": {"format": "records", "columns": ["x"], "rows": [{"x": 1}], "row_count": 1, "truncated": False},
                "field_metadata": [{"name": "x", "data_type": "number", "semantic_role": "measure"}],
                "errors": [],
                "warnings": [],
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    response = ColabExtractionClient("https://colab.test", http_client=client).extract(_request())
    assert response.status == "success"


def test_colab_invalid_json_maps_safe_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"not json")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    response = ColabExtractionClient("https://colab.test", http_client=client).extract(_request())
    assert response.status == "failed"
    assert response.errors[0].code == "invalid_extraction_response"


def test_colab_unavailable_without_url():
    response = ColabExtractionClient("").extract(_request())
    assert response.status == "failed"
    assert response.errors[0].code == "colab_unavailable"

