from __future__ import annotations

import uuid

from contracts.common import ErrorItem, WarningItem
from contracts.extraction import DataExtractionRequest, DataSourceRequest, ExtractionConstraints, PresentationHint
from contracts.nl2chart import Nl2ChartRequest, Nl2ChartResponse
from services.adapter.extraction_to_visualization import AdapterError, adapt_extraction_to_visualization
from services.artifacts.store import LocalArtifactStore
from services.extraction_client.colab_client import ColabExtractionClient
from services.extraction_client.disabled_client import DisabledExtractionClient
from services.extraction_client.mock_client import MockExtractionClient
from services.gateway.config import Settings
from services.visualization.cpu_visualization_service import CpuVisualizationService


class Nl2ChartOrchestrator:
    def __init__(
        self,
        settings: Settings,
        artifact_store: LocalArtifactStore | None = None,
        visualization_service: CpuVisualizationService | None = None,
    ):
        self.settings = settings
        self.artifact_store = artifact_store or LocalArtifactStore(settings.artifact_dir)
        self.visualization_service = visualization_service or CpuVisualizationService()

    def _extraction_client(self):
        if self.settings.extraction_mode == "mock":
            return MockExtractionClient(self.settings.demo_data_dir)
        if self.settings.extraction_mode == "colab":
            return ColabExtractionClient(
                self.settings.text_to_sql_service_url,
                self.settings.text_to_sql_timeout_seconds,
                self.settings.text_to_sql_auth_token,
            )
        return DisabledExtractionClient()

    def run(self, request: Nl2ChartRequest) -> Nl2ChartResponse:
        request_id = uuid.uuid4().hex
        extraction_request = DataExtractionRequest(
            request_id=request_id,
            user_query=request.user_query,
            locale=request.locale,
            timezone=request.timezone,
            data_source=DataSourceRequest(
                id=request.data_source_id,
                dialect="unknown",
                connection_ref=None,
                schema_version=None,
            ),
            constraints=ExtractionConstraints(),
            presentation_hint=PresentationHint(
                preferred_output=request.presentation_preferences.preferred_output,
            ),
        )

        extraction_response = self._extraction_client().extract(extraction_request)
        if extraction_response.status == "failed":
            response = Nl2ChartResponse(
                request_id=request_id,
                status="failed",
                message="Не удалось получить данные для запроса.",
                selected_view={},
                artifacts=[],
                warnings=extraction_response.warnings,
                errors=extraction_response.errors or [
                    ErrorItem(
                        code="extraction_failed",
                        message="Извлечение данных завершилось ошибкой.",
                        source="extraction",
                        retryable=True,
                    )
                ],
                debug=self._debug_payload(extraction_response.sql.query, request.presentation_preferences.technical_mode),
            )
            self._save_response(response)
            return response

        try:
            adapter_result = adapt_extraction_to_visualization(
                extraction_response,
                request.presentation_preferences,
            )
        except AdapterError as exc:
            response = Nl2ChartResponse(
                request_id=request_id,
                status="failed",
                message="Данные получены, но не прошли адаптацию к визуализации.",
                selected_view={},
                artifacts=[],
                warnings=exc.warnings,
                errors=exc.errors,
                debug=self._debug_payload(extraction_response.sql.query, request.presentation_preferences.technical_mode),
            )
            self._save_response(response)
            return response

        visualization_response = self.visualization_service.visualize(adapter_result.request)
        warnings = [
            *adapter_result.warnings,
            *visualization_response.warnings,
        ]
        errors = visualization_response.errors
        artifacts = []

        table_payload = {
            "columns": adapter_result.request.result_table.columns,
            "rows": adapter_result.request.result_table.rows[:100],
            "row_count": adapter_result.request.result_table.row_count,
            "truncated": adapter_result.request.result_table.truncated
            or adapter_result.request.result_table.row_count > 100,
            "request_id": request_id,
        }
        artifacts.append(
            self.artifact_store.save(
                artifact_type="table",
                title="Таблица результата",
                payload=table_payload,
                request_id=request_id,
            )
        )

        if visualization_response.selected_view.type == "chart":
            artifacts.append(
                self.artifact_store.save(
                    artifact_type="chart_spec",
                    title=visualization_response.selected_view.title,
                    payload={
                        "spec": visualization_response.selected_view.spec,
                        "request_id": request_id,
                    },
                    request_id=request_id,
                )
            )

        if self.settings.debug_sql_visible and request.presentation_preferences.technical_mode and extraction_response.sql.query:
            artifacts.append(
                self.artifact_store.save(
                    artifact_type="debug_sql",
                    title="SQL debug",
                    payload={"sql": extraction_response.sql.query, "request_id": request_id},
                    request_id=request_id,
                )
            )

        response_status = visualization_response.status
        if warnings and response_status == "success":
            response_status = "partial_success"
        message = self._message_for(response_status, visualization_response.selected_view.type, errors)
        response = Nl2ChartResponse(
            request_id=request_id,
            status=response_status,
            message=message,
            selected_view=visualization_response.selected_view.model_dump(mode="json"),
            artifacts=artifacts,
            warnings=warnings,
            errors=errors,
            debug=self._debug_payload(extraction_response.sql.query, request.presentation_preferences.technical_mode),
        )
        self._save_response(response)
        return response

    def _debug_payload(self, sql: str | None, technical_mode: bool) -> dict[str, object]:
        if self.settings.debug_sql_visible and technical_mode and sql:
            return {"sql": sql}
        return {"sql_visible": False}

    @staticmethod
    def _message_for(status: str, view_type: str, errors: list[ErrorItem]) -> str:
        if status == "failed" and any(error.code == "empty_result" for error in errors):
            return "Запрос выполнен, но данные не найдены."
        if status == "failed":
            return "Не удалось построить визуализацию."
        if view_type == "chart":
            return "Построил график по вашему запросу."
        return "Подготовил таблицу по вашему запросу."

    def _save_response(self, response: Nl2ChartResponse) -> None:
        self.artifact_store.save_response(response.request_id, response.model_dump(mode="json"))
