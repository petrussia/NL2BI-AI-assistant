from fastapi.testclient import TestClient

from services.gateway.api.main import app


client = TestClient(app)


def test_nl2chart_time_series_mock():
    response = client.post(
        "/api/nl2chart",
        json={"user_query": "Покажи динамику продаж по месяцам", "data_source_id": "demo_concert_singer"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["selected_view"]["chart_type"] == "line"
    assert any(item["artifact_type"] == "chart_spec" for item in payload["artifacts"])


def test_nl2chart_category_mock():
    response = client.post(
        "/api/nl2chart",
        json={"user_query": "Сравни продажи по категориям", "data_source_id": "demo_concert_singer"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["selected_view"]["chart_type"] == "bar"


def test_nl2chart_top_n_mock():
    response = client.post(
        "/api/nl2chart",
        json={"user_query": "Покажи топ клиентов по выручке", "data_source_id": "demo_concert_singer"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["selected_view"]["chart_type"] in {"bar", "table"}


def test_nl2chart_empty_result_safe():
    response = client.post(
        "/api/nl2chart",
        json={"user_query": "Покажи пустой результат", "data_source_id": "demo_concert_singer"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "failed"
    assert payload["errors"][0]["code"] == "empty_result"
