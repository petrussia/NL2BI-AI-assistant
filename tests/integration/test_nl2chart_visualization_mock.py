from fastapi.testclient import TestClient

from services.gateway.api.routers import runtime as runtime_router
from services.gateway.api.main import app
from services.gateway.config import Settings


def test_runtime_mock_mode():
    payload = TestClient(app).get("/api/runtime").json()
    assert payload["server_runtime"] is True
    assert payload["gpu_in_backend"] is False
    assert payload["extraction_mode"] == "mock"
    assert payload["colab_available"] is False
    assert payload["colab_health"] == {
        "model_loaded": None,
        "gpu_name": None,
        "mock_model": None,
        "demo_db_ready": None,
    }
    assert payload["server_allows_llm_imports"] is False


def test_runtime_colab_health_is_sanitized(monkeypatch, tmp_path):
    class FakeColabClient:
        def __init__(self, service_url: str, timeout_seconds: float, auth_token: str):
            assert service_url == "https://colab.example"
            assert timeout_seconds == 3
            assert auth_token == "secret"

        def health(self):
            return True, {
                "model_loaded": True,
                "gpu_name": "NVIDIA L4",
                "mock_model": False,
                "model_id": "Qwen/Qwen2.5-Coder-7B-Instruct",
                "auth": {"api_token_set": True},
            }

    monkeypatch.setattr(runtime_router, "ColabExtractionClient", FakeColabClient)
    settings = Settings(
        app_env="test",
        extraction_mode="colab",
        text_to_sql_service_url="https://colab.example",
        text_to_sql_auth_token="secret",
        text_to_sql_timeout_seconds=3,
        visualization_mode="local_cpu",
        artifact_storage="local",
        artifact_dir=tmp_path / "artifacts",
        demo_data_dir=tmp_path / "demo_data",
        auth_db_path=tmp_path / "auth.db",
        auth_jwt_secret="test",
        debug_sql_visible=False,
    )

    payload = runtime_router.runtime(settings)

    assert payload["colab_available"] is True
    assert payload["colab_service_url_configured"] is True
    assert payload["colab_auth_token_configured"] is True
    assert payload["colab_health"] == {
        "model_loaded": True,
        "gpu_name": "NVIDIA L4",
        "mock_model": False,
        "demo_db_ready": None,
    }
    assert "https://colab.example" not in str(payload)
    assert "secret" not in str(payload)
    assert "auth" not in payload["colab_health"]
