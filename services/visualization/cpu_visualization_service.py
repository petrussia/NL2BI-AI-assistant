from __future__ import annotations

from time import perf_counter

from contracts.common import ErrorItem, WarningItem
from contracts.extraction import FieldMetadata
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


def _has_any(text: str, tokens: tuple[str, ...]) -> bool:
    return any(token in text for token in tokens)


def _is_multi_metric_query(user_query: str) -> bool:
    query = user_query.casefold()
    return _has_any(
        query,
        (
            "min",
            "max",
            "avg",
            "average",
            "minimum",
            "maximum",
            "сред",
            "миним",
            "максим",
        ),
    )


def _pick_measure_field(fields: list[FieldMetadata], user_query: str) -> FieldMetadata:
    query = user_query.casefold()

    def score(field: FieldMetadata) -> tuple[int, int]:
        name = field.name.casefold()
        value = 0
        if _has_any(query, ("сколько", "how many", "count", "number of", "количество")) and _has_any(
            name, ("count", "количество", "_n", " n", "total", "всего")
        ):
            value += 8
        hints: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
            (("станц", "station"), ("station", "станц")),
            (("заказ", "order"), ("order", "заказ")),
            (("выруч", "продаж", "revenue", "sales"), ("revenue", "sales", "выруч", "сумм", "amount", "total")),
            (("задач", "task"), ("task", "задач")),
            (("насел", "population"), ("population", "насел")),
            (("площад", "area"), ("area", "площад")),
            (("событ", "event"), ("event", "событ")),
            (("участ", "member"), ("member", "участ")),
            (("певц", "singer"), ("singer", "певц")),
            (("концерт", "concert"), ("concert", "концерт")),
            (("расход", "expense"), ("expense", "cost", "расход")),
            (("возраст", "age"), ("age", "возраст")),
        )
        for query_tokens, field_tokens in hints:
            if _has_any(query, query_tokens) and _has_any(name, field_tokens):
                value += 6
        if field.provenance.derived or field.default_aggregation == "none":
            value += 1
        return value, -len(name)

    return max(fields, key=score)


def _pick_dimension_field(fields: list[FieldMetadata], user_query: str) -> FieldMetadata:
    query = user_query.casefold()

    def score(field: FieldMetadata) -> tuple[int, int]:
        name = field.name.casefold()
        value = 0
        if field.semantic_role == "id" or name.endswith("_id"):
            value -= 8
        if _has_any(name, ("name", "название", "фио", "company", "компания")):
            value += 8
        if _has_any(name, ("category", "категор", "country", "страна", "segment", "сегмент", "okrug", "округ")):
            value += 6
        if _has_any(query, ("линии", "line")) and _has_any(name, ("name", "название", "line")):
            value += 4
        if _has_any(name, ("color", "цвет", "hex", "code", "код")):
            value -= 4
        return value, -len(name)

    return max(fields, key=score)


def _field_by_name(fields: list[FieldMetadata], name: str | None, fallback: FieldMetadata) -> FieldMetadata:
    if name:
        for field in fields:
            if field.name == name:
                return field
    return fallback


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
            inferred_role = infer_semantic_role(item.name, data_type)
            role = inferred_role if inferred_role == "time" else item.semantic_role if item.semantic_role != "unknown" else inferred_role
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
        selected_time_field = time_fields[0] if time_fields else None
        selected_measure_field = _pick_measure_field(measure_fields, request.user_query) if measure_fields else None
        selected_dimension_field = _pick_dimension_field(dimension_fields, request.user_query) if dimension_fields else None
        multi_metric_query = len(measure_fields) >= 2 and _is_multi_metric_query(request.user_query)

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
        if multi_metric_query:
            add_candidate("table", 0.93, "Several measures are requested; table preserves all metrics.")
        if selected_time_field and selected_measure_field:
            add_candidate(
                "line",
                0.9 if intent == "trend" else 0.55,
                "Time field and measure are available.",
                selected_time_field.name,
                selected_measure_field.name,
            )
        if selected_dimension_field and selected_measure_field:
            score = 0.88 if intent in {"comparison", "top_n"} else 0.7
            add_candidate(
                "bar",
                score,
                "Dimension and measure are available.",
                selected_dimension_field.name,
                selected_measure_field.name,
            )
        if len(measure_fields) >= 2 and (intent == "correlation" or preferred_chart_type == "scatter"):
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
            x_field = _field_by_name(time_fields, selected_candidate.fields[0] if selected_candidate.fields else None, time_fields[0])
            y_field = _field_by_name(measure_fields, selected_candidate.fields[1] if len(selected_candidate.fields) > 1 else None, measure_fields[0])
            # A line on 1-2 points reads worse than two bars; downgrade so the
            # reader actually sees the values.
            mark = "bar" if table.row_count < 3 else "line"
            spec = chart_spec(
                chart_type=mark,
                title=title,
                x_field=x_field,
                y_field=y_field,
                table=table,
            )
            selected = SelectedView(type="chart", chart_type=mark, title=title, spec=spec, normalized_spec=spec)
            used_fields = [x_field.name, y_field.name]
        elif chart_type == "bar" and dimension_fields and measure_fields:
            x_field = _field_by_name(dimension_fields, selected_candidate.fields[0] if selected_candidate.fields else None, dimension_fields[0])
            y_field = _field_by_name(measure_fields, selected_candidate.fields[1] if len(selected_candidate.fields) > 1 else None, measure_fields[0])
            spec = chart_spec(
                chart_type="bar",
                title=title,
                x_field=x_field,
                y_field=y_field,
                table=table,
            )
            selected = SelectedView(type="chart", chart_type="bar", title=title, spec=spec, normalized_spec=spec)
            used_fields = [x_field.name, y_field.name]
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
                used_aggregations=self._used_aggregations(metadata, used_fields),
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
    def _used_aggregations(fields: list, used_fields: list[str]) -> list[str]:
        aggregations: list[str] = []
        for field in fields:
            if field.name not in used_fields or field.semantic_role != "measure":
                continue
            aggregation = field.provenance.aggregation or field.default_aggregation
            if aggregation and aggregation != "none":
                aggregations.append(aggregation)
        return aggregations

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
