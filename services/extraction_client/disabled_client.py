from __future__ import annotations

from contracts.common import ErrorItem
from contracts.extraction import DataExtractionRequest, DataExtractionResponse, DataSourceInfo
from services.extraction_client.base import ExtractionClient


class DisabledExtractionClient(ExtractionClient):
    def extract(self, request: DataExtractionRequest) -> DataExtractionResponse:
        return DataExtractionResponse(
            request_id=request.request_id,
            status="failed",
            user_query=request.user_query,
            normalized_query=None,
            data_source=DataSourceInfo(
                id=request.data_source.id,
                dialect=request.data_source.dialect,
                schema_version=request.data_source.schema_version,
            ),
            errors=[
                ErrorItem(
                    code="extraction_disabled",
                    message="Извлечение данных отключено в конфигурации сервера.",
                    source="extraction",
                    retryable=False,
                )
            ],
        )

