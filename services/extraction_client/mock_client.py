from __future__ import annotations

import json
import re
from pathlib import Path

from contracts.extraction import DataExtractionRequest, DataExtractionResponse
from services.extraction_client.base import ExtractionClient


class MockExtractionClient(ExtractionClient):
    def __init__(self, demo_data_dir: Path):
        self.fixture_dir = Path(demo_data_dir) / "extraction_fixtures"

    @staticmethod
    def fixture_name_for_query(user_query: str) -> str:
        query = user_query.casefold()
        if re.search(r"month|месяц|динамик|trend|выручк.*месяц", query):
            return "time_series"
        if re.search(r"top|топ|лучшие|клиент", query):
            return "top_n"
        if re.search(r"empty|пуст|нет данных", query):
            return "empty_result"
        if re.search(r"metadata|метадан|непол", query):
            return "metadata_incomplete"
        if re.search(r"category|категор|сравн", query):
            return "category_comparison"
        return "category_comparison"

    def extract(self, request: DataExtractionRequest) -> DataExtractionResponse:
        fixture_name = self.fixture_name_for_query(request.user_query)
        fixture_path = self.fixture_dir / f"{fixture_name}.json"
        payload = json.loads(fixture_path.read_text(encoding="utf-8"))
        payload["request_id"] = request.request_id
        payload["user_query"] = request.user_query
        payload.setdefault("data_source", {})["id"] = request.data_source.id
        return DataExtractionResponse.model_validate(payload)
