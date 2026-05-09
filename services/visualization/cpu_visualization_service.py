from __future__ import annotations

from time import perf_counter

from contracts.common import ErrorItem, WarningItem
from contracts.visualization import (
    SelectedView,
    VisualizationCandidate,
    VisualizationExplanation,
    VisualizationPerformance,
    VisualizationQuality,
    VisualizationRequest,
    VisualizationResponse,
)
from services.adapter.aggregation_inference import infer_allowed_aggregations, infer_default_aggregation
from services.adapter.role_inference import infer_semantic_role
from services.adapter.type_mapping import infer_data_type
from services.visualization.render import chart_spec, table_spec
from services.visualization.rules import detect_intent, fields_by_role
from services.visualization.validation import validate_visualization_request


class CpuVisualizationService:
    def visualize(self, request: VisualizationRequest) -> VisualizationResponse:
        started = perf_counter()
        warnings: list[WarningItem] = []
        errors = validate_visualization_request(request)
        if errors:
            return self._failed(request, errors, warnings, started)

        table = request.result_table
        metadata = []
        for item in request.field_metadata:
            values = [row.get(item.name) for row in table.rows]
            data_type = item.data_type if item.data_type != "unknown" else infer_data_type(item.name, values)
            role = item.semantic_role if item.semantic_role != "unknown" else infer_semantic_role(item.name, data_type)
            allowed = item.allowed_aggregations or infer_allowed_aggregations(role)
            default = item.default_aggregation or infer_default_aggregation(role)
            if item.data_type == "unknown" or item.semantic_role == "unknown" or not item.allowed_aggregations:
                warnings.append(
                    WarningItem(
                        code="metadata_incomplete",
                        message=f"Visualization inferred metadata for '{item.name}'.",
                        source="visualization",
                        details={"field": item.name},
                    )
                )
            metadata.append(
                item.model_copy(
                    update={
                        "data_type": data_type,
                        "semantic_role": role,
                        "allowed_aggregations": allowed,
                        "default_aggregation": default,
                    }
                )
            )

        if table.row_count == 0 or not table.rows:
            selected = SelectedView(
                type="table",
                chart_type="table",
                title="Данные не найдены",
                spec=table_spec("Данные не найдены", table),
                normalized_spec=table_spec("Данные не найдены", table),
            )
            error = ErrorItem(
                code="empty_result",
                message="Запрос выполнен, но данные не найдены.",
                source="visualization",
                retryable=False,
            )
            return VisualizationResponse(
                request_id=request.request_id,
                status="failed",
                selected_view=selected,
                table_view=selected.spec,
                explanation=VisualizationExplanation(
                    intent=detect_intent(request.user_query),
                    reason="No rows available for visualization.",
                ),
                quality=VisualizationQuality(confidence=0.0, validation_passed=True),
                performance=self._performance(started, mode="fallback"),
                errors=[error],
                warnings=warnings,
            )

        if table.row_count > 100:
            warnings.append(
                WarningItem(
                    code="row_limit_exceeded",
                    message="Visualization response includes first 100 rows only.",
                    source="visualization",
                    details={"row_count": table.row_count, "inline_limit": 100},
                )
            )

        intent = detect_intent(request.user_query)
        roles = fields_by_role(metadata)
        time_fields = roles.get("time", [])
        measure_fields = roles.get("measure", [])
        dimension_fields = roles.get("dimension", [])
        text_fields = roles.get("text", [])
        preferred_output = request.presentation_preferences.preferred_output
        preferred_chart_type = request.presentation_preferences.preferred_chart_type

        candidates: list[VisualizationCandidate] = []

        def add_candidate(chart_type: str, score: float, reason: str, x_name: str | None = None, y_name: str | None = None) -> None:
            fields = [value for value in (x_name, y_name) if value]
            candidates.append(
                VisualizationCandidate(
                    chart_type=chart_type, score=score, reason=reason, fields=fields, spec={}
                )
            )

        if preferred_output == "table" or intent == "table":
            add_candidate("table", 1.0, "User requested table output.")
        if preferred_chart_type and preferred_chart_type != "table":
            add_candidate(preferred_chart_type, 0.95, "User preferred chart type.")
        if time_fields and measure_fields:
            add_candidate("line", 0.9 if intent == "trend" else 0.75, "Time field and measure are available.", time_fields[0].name, measure_fields[0].name)
        if dimension_fields and measure_fields:
            score = 0.88 if intent in {"comparison", "top_n"} else 0.7
            add_candidate("bar", score, "Dimension and measure are available.", dimension_fields[0].name, measure_fields[0].name)
        if len(measure_fields) >= 2:
            add_candidate("scatter", 0.65 if intent == "correlation" else 0.45, "Two measures are available.", measure_fields[0].name, measure_fields[1].name)
        if not candidates or (text_fields and not measure_fields and not dimension_fields):
            add_candidate("table", 0.6, "Fallback table view is safest.")

        candidates.sort(key=lambda item: item.score, reverse=True)
        selected_candidate = candidates[0]

        chart_type = selected_candidate.chart_type
        if preferred_output == "chart" and chart_type == "table":
            warnings.append(
                WarningItem(
                    code="visualization_fallback",
                    message="Данные подходят только для табличного отображения.",
                    source="visualization",
                )
            )

        title = self._title_for(chart_type, request.user_query)
        if chart_type == "line" and time_fields and measure_fields:
            spec = chart_spec(
                chart_type="line",
                title=title,
                x_field=time_fields[0],
                y_field=measure_fields[0],
                table=table,
            )
            selected = SelectedView(type="chart", chart_type="line", title=title, spec=spec, normalized_spec=spec)
            used_fields = [time_fields[0].name, measure_fields[0].name]
        elif chart_type == "bar" and dimension_fields and measure_fields:
            spec = chart_spec(
                chart_type="bar",
                title=title,
                x_field=dimension_fields[0],
                y_field=measure_fields[0],
                table=table,
            )
            selected = SelectedView(type="chart", chart_type="bar", title=title, spec=spec, normalized_spec=spec)
            used_fields = [dimension_fields[0].name, measure_fields[0].name]
        elif chart_type == "scatter" and len(measure_fields) >= 2:
            spec = chart_spec(
                chart_type="scatter",
                title=title,
                x_field=measure_fields[0],
                y_field=measure_fields[1],
                table=table,
            )
            selected = SelectedView(type="chart", chart_type="scatter", title=title, spec=spec, normalized_spec=spec)
            used_fields = [measure_fields[0].name, measure_fields[1].name]
        else:
            spec = table_spec(title, table)
            selected = SelectedView(type="table", chart_type="table", title=title, spec=spec, normalized_spec=spec)
            used_fields = list(table.columns)

        status = "partial_success" if warnings else "success"
        return VisualizationResponse(
            request_id=request.request_id,
            status=status,
            selected_view=selected,
            candidates=candidates[: request.presentation_preferences.max_candidates],
            table_view=table_spec("Таблица результата", table),
            explanation=VisualizationExplanation(
                intent=intent,
                used_fields=used_fields,
                used_aggregations=[field.default_aggregation for field in metadata if field.name in used_fields and field.default_aggregation],
                reason=selected_candidate.reason,
            ),
            quality=VisualizationQuality(
                confidence=selected_candidate.score,
                validation_passed=True,
                warnings=[warning.message for warning in warnings],
            ),
            performance=self._performance(started),
            errors=[],
            warnings=warnings,
        )

    @staticmethod
    def _title_for(chart_type: str, user_query: str) -> str:
        if chart_type == "line":
            return "Динамика показателя"
        if chart_type == "bar":
            return "Сравнение по категориям"
        if chart_type == "scatter":
            return "Связь показателей"
        if user_query:
            return "Таблица результата"
        return "Результат"

    @staticmethod
    def _performance(started: float, mode: str = "fast") -> VisualizationPerformance:
        return VisualizationPerformance(latency_ms=int((perf_counter() - started) * 1000), mode=mode)

    def _failed(
        self,
        request: VisualizationRequest,
        errors: list[ErrorItem],
        warnings: list[WarningItem],
        started: float,
    ) -> VisualizationResponse:
        spec = table_spec("Ошибка визуализации", request.result_table)
        selected = SelectedView(
            type="table",
            chart_type="table",
            title="Ошибка визуализации",
            spec=spec,
            normalized_spec=spec,
        )
        return VisualizationResponse(
            request_id=request.request_id,
            status="failed",
            selected_view=selected,
            table_view=spec,
            explanation=VisualizationExplanation(reason="Visualization validation failed."),
            quality=VisualizationQuality(confidence=0.0, validation_passed=False),
            performance=self._performance(started, mode="fallback"),
            errors=errors,
            warnings=warnings,
        )

