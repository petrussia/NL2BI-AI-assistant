import os

from contracts.nl2chart import Nl2ChartRequest
from services.gateway.config import Settings
from services.orchestrator.nl2chart_orchestrator import Nl2ChartOrchestrator


def test_mock_mode_unaffected(tmp_path):
    settings = Settings(
        app_env="test",
        extraction_mode="mock",
        text_to_sql_service_url="",
        text_to_sql_auth_token="",
        text_to_sql_timeout_seconds=1,
        visualization_mode="local_cpu",
        artifact_storage="local",
        artifact_dir=tmp_path / "artifacts",
        demo_data_dir=os.getcwd() + "/demo_data",
        auth_db_path=tmp_path / "auth.db",
        auth_jwt_secret="test",
        debug_sql_visible=False,
    )
    response = Nl2ChartOrchestrator(settings).run(
        Nl2ChartRequest(user_query="Покажи динамику продаж по месяцам")
    )
    assert response.status == "success"
    assert response.selected_view["chart_type"] == "line"
