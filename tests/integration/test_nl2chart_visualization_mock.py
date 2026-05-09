from fastapi.testclient import TestClient

from services.gateway.api.main import app


def test_runtime_mock_mode():
    payload = TestClient(app).get("/api/runtime").json()
    assert payload["server_runtime"] is True
    assert payload["gpu_in_backend"] is False
    assert payload["extraction_mode"] == "mock"
    assert payload["server_allows_llm_imports"] is False

