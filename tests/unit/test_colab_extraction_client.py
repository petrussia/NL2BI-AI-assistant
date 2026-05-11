import httpx

from contracts.extraction import DataExtractionRequest, DataSourceRequest
from services.extraction_client.colab_client import ColabExtractionClient


def _request() -> DataExtractionRequest:
    return DataExtractionRequest(
        request_id="r1",
        user_query="Покажи динамику",
        data_source=DataSourceRequest(id="demo_concert_singer"),
    )


def test_colab_success_with_mock_transport():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "request_id": "r1",
                "status": "success",
                "user_query": "Покажи динамику",
                "data_source": {"id": "demo_concert_singer", "dialect": "unknown"},
                "result_table": {"format": "records", "columns": ["x"], "rows": [{"x": 1}], "row_count": 1, "truncated": False},
                "field_metadata": [{"name": "x", "data_type": "number", "semantic_role": "measure"}],
                "errors": [],
                "warnings": [],
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    response = ColabExtractionClient("https://colab.test", http_client=client).extract(_request())
    assert response.status == "success"


def test_colab_auth_token_sends_bearer_header():
    seen: list[tuple[str, str | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.url.path, request.headers.get("authorization")))
        if request.url.path == "/health":
            return httpx.Response(200, json={"status": "ok", "model_loaded": True})
        return httpx.Response(
            200,
            json={
                "request_id": "r1",
                "status": "success",
                "user_query": "Покажи динамику",
                "data_source": {"id": "demo_concert_singer", "dialect": "unknown"},
                "result_table": {"format": "records", "columns": ["x"], "rows": [{"x": 1}], "row_count": 1, "truncated": False},
                "field_metadata": [{"name": "x", "data_type": "number", "semantic_role": "measure"}],
                "errors": [],
                "warnings": [],
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    colab = ColabExtractionClient("https://colab.test", auth_token="secret-token", http_client=client)
    colab.extract(_request())
    colab.health()

    assert seen == [
        ("/extract", "Bearer secret-token"),
        ("/health", "Bearer secret-token"),
    ]


def test_colab_without_auth_token_sends_no_authorization_header():
    seen: list[tuple[str, str | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.url.path, request.headers.get("authorization")))
        if request.url.path == "/health":
            return httpx.Response(200, json={"status": "ok"})
        return httpx.Response(
            200,
            json={
                "request_id": "r1",
                "status": "success",
                "user_query": "Покажи динамику",
                "data_source": {"id": "demo_concert_singer", "dialect": "unknown"},
                "result_table": {"format": "records", "columns": ["x"], "rows": [{"x": 1}], "row_count": 1, "truncated": False},
                "field_metadata": [{"name": "x", "data_type": "number", "semantic_role": "measure"}],
                "errors": [],
                "warnings": [],
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    colab = ColabExtractionClient("https://colab.test", http_client=client)
    colab.extract(_request())
    colab.health()

    assert seen == [
        ("/extract", None),
        ("/health", None),
    ]


def test_colab_load_model_can_target_planner():
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["body"] = request.content.decode("utf-8")
        seen["authorization"] = request.headers.get("authorization")
        return httpx.Response(
            200,
            json={
                "status": "loading",
                "target": "planner",
                "planner_loaded": False,
                "planner_id": "Qwen/Qwen3-Coder-30B-A3B-Instruct",
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    colab = ColabExtractionClient("https://colab.test", auth_token="secret-token", http_client=client)
    ok, payload = colab.load_model("Qwen/Qwen3-Coder-30B-A3B-Instruct", target="planner")

    assert ok is True
    assert payload["status"] == "loading"
    assert seen["path"] == "/reload_model"
    assert seen["authorization"] == "Bearer secret-token"
    assert '"target":"planner"' in seen["body"]
    assert '"model_id":"Qwen/Qwen3-Coder-30B-A3B-Instruct"' in seen["body"]


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
