from __future__ import annotations

import re
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
from services.visualization.render import chart_spec, multi_measure_line_spec, precomputed_boxplot_spec, table_spec
from services.visualization.rules import detect_intent, fields_by_role
from services.visualization.validation import validate_visualization_request


AXIS_TOKEN_RE = re.compile(r"\bпо\s+[xy]\b|\b[xy]\s*[- ]?axis\b", re.IGNORECASE)
AXIS_FIELD_WINDOW = 60


def _has_any(text: str, tokens: tuple[str, ...]) -> bool:
    return any(token in text for token in tokens)


def _is_multi_metric_query(user_query: str) -> bool:
    query = user_query.casefold()
    metric_groups = (
        ("min", "minimum", "миним"),
        ("max", "maximum", "максим"),
        ("avg", "average", "средн"),
    )
    return sum(1 for tokens in metric_groups if _has_any(query, tokens)) >= 2


def _is_area_query(user_query: str) -> bool:
    query = user_query.casefold()
    return _has_any(query, ("area chart", "area graph", "област", "площадн"))


def _is_part_to_whole_query(user_query: str) -> bool:
    query = user_query.casefold()
    return _has_any(
        query,
        (
            "доля",
            "доли",
            "процент",
            "структур",
            "share",
            "part-to-whole",
            "pie",
            "donut",
            "кругов",
            "сектор",
        ),
    )


def _is_stacked_query(user_query: str) -> bool:
    query = user_query.casefold()
    return _has_any(query, ("stacked", "накоплен", "разбив", "вклад", "состав"))


def _is_multi_series_query(user_query: str) -> bool:
    query = user_query.casefold()
    return _has_any(
        query,
        (
            "multi-line",
            "multiline",
            "несколько лини",
            "много лини",
            "в разрезе",
            "в разбив",
            "по групп",
            "по регион",
            "по категор",
            "по канал",
            "отдельно для",
            "split by",
            "broken down by",
        ),
    )


def _mentions_axis(user_query: str, axis: str) -> bool:
    axis_pattern = re.escape(axis.casefold())
    return bool(
        re.search(
            rf"\bпо\s+{axis_pattern}\b|\bпо\s+оси\s+{axis_pattern}\b|\bось\s+{axis_pattern}\b|\b{axis_pattern}\s*[- ]?axis\b",
            user_query.casefold(),
            re.IGNORECASE,
        )
    )


def _is_heatmap_shaped_query(user_query: str) -> bool:
    query = user_query.casefold()
    asks_for_color = _has_any(query, ("цвет", "color", "окрас", "закрас"))
    return asks_for_color and _mentions_axis(query, "x") and _mentions_axis(query, "y")


def _is_heatmap_query(user_query: str) -> bool:
    query = user_query.casefold()
    return _has_any(query, ("теплов", "тепров", "heatmap", "heat map", "матриц")) or _is_heatmap_shaped_query(user_query)


def _is_histogram_query(user_query: str) -> bool:
    query = user_query.casefold()
    return _has_any(query, ("гистограмм", "histogram", "распредел"))


def _is_boxplot_query(user_query: str) -> bool:
    query = user_query.casefold()
    return _has_any(query, ("boxplot", "box plot", "ящик", "ус", "выброс"))


def _is_scatter_query(user_query: str) -> bool:
    query = user_query.casefold()
    if _is_heatmap_query(query):
        return False
    asks_for_axis = bool(AXIS_TOKEN_RE.search(query))
    return _has_any(
        query,
        ("scatter", "dot plot", "point chart", "коррел", "точеч", "точк", "рассеян", "рассеив"),
    ) or asks_for_axis


def _unique_count(rows: list[dict], field: FieldMetadata | None) -> int:
    if field is None:
        return 0
    values: set[object] = set()
    for row in rows:
        value = row.get(field.name)
        if value is None:
            continue
        if isinstance(value, list):
            value = tuple(value)
        elif isinstance(value, dict):
            value = tuple(sorted(value.items()))
        values.add(value)
    return len(values)


def _all_non_negative(rows: list[dict], field: FieldMetadata | None) -> bool:
    if field is None:
        return False
    values = [row.get(field.name) for row in rows if row.get(field.name) is not None]
    if not values:
        return False
    return all(isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0 for value in values)


def _is_raw_distribution_field(field: FieldMetadata | None) -> bool:
    if field is None:
        return False
    if field.provenance.aggregation is not None:
        return False
    if field.provenance.derived and field.default_aggregation != "none":
        return False
    return True


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
        if _has_any(query, ("чек", "стоимост", "order value")) and _has_any(
            name, ("стоим", "сумм", "amount", "value", "total")
        ):
            value += 10
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


def _normalized_name(field: FieldMetadata) -> str:
    return re.sub(r"[^0-9a-zа-яё]+", "_", field.name.casefold()).strip("_")


def _axis_token_pattern(token: str) -> str:
    escaped = re.escape(token.casefold()).replace(r"\ ", r"\s+")
    return rf"(?<![0-9a-zа-яё]){escaped}(?![0-9a-zа-яё])"


def _field_axis_tokens(field: FieldMetadata) -> set[str]:
    name = _normalized_name(field)
    tokens = {name, name.replace("_", " ")}
    if "month" in name or "месяц" in name:
        tokens.update({"month", "месяц", "месяцам", "месяцы", "помесячно"})
    if "type" in name or "тип" in name:
        tokens.update({"type", "тип", "типы", "типам", "тип мероприятия", "event type"})
    if "weekday" in name or "день" in name:
        tokens.update({"weekday", "day", "день недели", "день"})
    if "hour" in name or "час" in name:
        tokens.update({"hour", "час", "часы", "часам"})
    if "category" in name or "категор" in name:
        tokens.update({"category", "категория", "категории", "категориям"})
    if "segment" in name or "сегмент" in name:
        tokens.update({"segment", "сегмент", "сегменты", "сегментам"})
    return {token for token in tokens if token}


def _query_assigns_token_to_axis(query: str, token: str, axis: str) -> bool:
    token_pattern = _axis_token_pattern(token)
    axis_pattern = re.escape(axis.casefold())
    axis_phrase = (
        rf"(?:по\s+оси\s+{axis_pattern}|ось\s+{axis_pattern}|"
        rf"{axis_pattern}\s*[-:=]|{axis_pattern}\s+axis|{axis_pattern}-axis)"
    )
    return any(
        re.search(pattern, query, re.IGNORECASE)
        for pattern in (
            rf"{token_pattern}\s+(?:по|на|для|on|along|by)\s+{axis_pattern}(?![0-9a-zа-яё])",
            rf"{axis_phrase}[^,.;\n]{{0,{AXIS_FIELD_WINDOW}}}{token_pattern}",
            rf"{token_pattern}[^,.;\n]{{0,{AXIS_FIELD_WINDOW}}}{axis_phrase}",
        )
    )


def _field_for_requested_axis(fields: list[FieldMetadata], user_query: str, axis: str) -> FieldMetadata | None:
    query = user_query.casefold().replace("ё", "е")
    for field in fields:
        for token in _field_axis_tokens(field):
            if _query_assigns_token_to_axis(query, token.replace("ё", "е"), axis):
                return field
    return None


def _find_stat_field(fields: list[FieldMetadata], stat: str) -> FieldMetadata | None:
    for field in fields:
        name = _normalized_name(field)
        if stat == "q1" and (
            name in {"q1", "p25", "percentile_25", "percentile25"}
            or "q1" in name
            or "25" in name and ("percentile" in name or "кварт" in name)
            or "нижн" in name and "кварт" in name
            or "перв" in name and "кварт" in name
        ):
            return field
        if stat == "median" and (
            name in {"median", "mediana", "q2", "p50", "percentile_50", "percentile50", "медиана"}
            or "median" in name
            or "медиан" in name
            or "q2" in name
            or "50" in name and ("percentile" in name or "кварт" in name)
        ):
            return field
        if stat == "avg" and (
            name in {"avg", "average", "mean", "среднее"}
            or "avg" in name
            or "average" in name
            or "mean" in name
            or "средн" in name
        ):
            return field
        if stat == "q3" and (
            name in {"q3", "p75", "percentile_75", "percentile75"}
            or "q3" in name
            or "75" in name and ("percentile" in name or "кварт" in name)
            or "верхн" in name and "кварт" in name
            or "трет" in name and "кварт" in name
        ):
            return field
        if stat == "min" and (
            name in {"min", "minimum", "минимум"}
            or name.startswith("min_")
            or name.endswith("_min")
            or name.startswith("миним")
        ):
            return field
        if stat == "max" and (
            name in {"max", "maximum", "максимум"}
            or name.startswith("max_")
            or name.endswith("_max")
            or name.startswith("максим")
        ):
            return field
    return None


def _precomputed_boxplot_fields(
    metadata: list[FieldMetadata],
    dimension_fields: list[FieldMetadata],
) -> tuple[FieldMetadata, FieldMetadata, FieldMetadata, FieldMetadata, FieldMetadata | None, FieldMetadata | None] | None:
    category_field = dimension_fields[0] if dimension_fields else None
    numeric_fields = [field for field in metadata if field.data_type == "number" and field.semantic_role == "measure"]
    q1_field = _find_stat_field(numeric_fields, "q1")
    median_field = _find_stat_field(numeric_fields, "median") or _find_stat_field(numeric_fields, "avg")
    q3_field = _find_stat_field(numeric_fields, "q3")
    if category_field is None or q1_field is None or median_field is None or q3_field is None:
        return None
    return (
        category_field,
        q1_field,
        median_field,
        q3_field,
        _find_stat_field(numeric_fields, "min"),
        _find_stat_field(numeric_fields, "max"),
    )


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
        multi_metric_query = (
            len(measure_fields) >= 2
            and intent != "correlation"
            and preferred_chart_type != "scatter"
            and _is_multi_metric_query(request.user_query)
        )
        secondary_dimension_field = next(
            (field for field in dimension_fields if selected_dimension_field is None or field.name != selected_dimension_field.name),
            None,
        )
        discrete_fields = [*dimension_fields, *time_fields]
        selected_discrete_field = selected_dimension_field or selected_time_field
        requested_x_field = _field_for_requested_axis(discrete_fields, request.user_query, "x")
        requested_y_field = _field_for_requested_axis(discrete_fields, request.user_query, "y")
        heatmap_x_field = requested_x_field or selected_discrete_field
        heatmap_y_field = requested_y_field or next(
            (field for field in discrete_fields if heatmap_x_field is None or field.name != heatmap_x_field.name),
            None,
        )
        if heatmap_x_field is not None and heatmap_y_field is not None and heatmap_x_field.name == heatmap_y_field.name:
            heatmap_y_field = next((field for field in discrete_fields if field.name != heatmap_x_field.name), None)
        secondary_discrete_field = next(
            (field for field in discrete_fields if selected_discrete_field is None or field.name != selected_discrete_field.name),
            None,
        )
        category_count = _unique_count(table.rows, selected_dimension_field)
        secondary_category_count = _unique_count(table.rows, secondary_dimension_field)
        series_count = _unique_count(table.rows, selected_dimension_field)
        can_pie = (
            selected_dimension_field is not None
            and selected_measure_field is not None
            and 2 <= category_count <= 8
            and _all_non_negative(table.rows, selected_measure_field)
        )
        can_histogram = selected_measure_field is not None and table.row_count >= 5 and _is_raw_distribution_field(selected_measure_field)
        can_boxplot = selected_measure_field is not None and table.row_count >= 5 and _is_raw_distribution_field(selected_measure_field)
        precomputed_boxplot_fields = _precomputed_boxplot_fields(metadata, dimension_fields)
        can_multi_line = (
            selected_time_field is not None
            and selected_measure_field is not None
            and selected_dimension_field is not None
            and 2 <= series_count <= 8
            and table.row_count >= 3
        )
        can_wide_multi_line = selected_time_field is not None and len(measure_fields) >= 2 and table.row_count >= 3
        can_stacked_bar = (
            selected_discrete_field is not None
            and secondary_dimension_field is not None
            and selected_measure_field is not None
            and 2 <= _unique_count(table.rows, secondary_dimension_field) <= 8
        )
        can_heatmap = (
            heatmap_x_field is not None
            and heatmap_y_field is not None
            and selected_measure_field is not None
            and _unique_count(table.rows, heatmap_x_field) <= 40
            and _unique_count(table.rows, heatmap_y_field) <= 40
        )

        candidates: list[VisualizationCandidate] = []

        def add_candidate(chart_type: str, score: float, reason: str, *field_names: str | None) -> None:
            fields = [value for value in field_names if value]
            candidates.append(
                VisualizationCandidate(
                    chart_type=chart_type, score=score, reason=reason, fields=fields, spec={}
                )
            )

        if preferred_output == "table" or intent == "table":
            add_candidate("table", 1.0, "User requested table output.")
        if preferred_chart_type == "line" and selected_time_field and selected_measure_field:
            add_candidate("line", 0.98, "User preferred line chart.", selected_time_field.name, selected_measure_field.name)
        if preferred_chart_type == "bar" and selected_dimension_field and selected_measure_field:
            add_candidate("bar", 0.98, "User preferred bar chart.", selected_dimension_field.name, selected_measure_field.name)
        if preferred_chart_type == "scatter" and len(measure_fields) >= 2:
            add_candidate("scatter", 0.98, "User preferred scatter plot.", measure_fields[0].name, measure_fields[1].name)
        if preferred_chart_type == "scatter" and len(measure_fields) < 2 and selected_dimension_field and selected_measure_field:
            add_candidate("scatter", 0.98, "User preferred point chart.", selected_dimension_field.name, selected_measure_field.name)
        if preferred_chart_type == "area" and selected_time_field and selected_measure_field and table.row_count >= 3:
            add_candidate("area", 0.98, "User preferred area chart.", selected_time_field.name, selected_measure_field.name)
        if preferred_chart_type == "pie" and can_pie:
            add_candidate("pie", 0.98, "User preferred pie chart.", selected_dimension_field.name, selected_measure_field.name)
        if preferred_chart_type == "histogram" and can_histogram:
            add_candidate("histogram", 0.98, "User preferred histogram.", selected_measure_field.name)
        if preferred_chart_type == "stacked_bar" and can_stacked_bar:
            add_candidate("stacked_bar", 0.98, "User preferred stacked bar chart.", selected_discrete_field.name, selected_measure_field.name, secondary_dimension_field.name)
        if preferred_chart_type == "multi_line" and can_multi_line:
            add_candidate("multi_line", 0.98, "User preferred multi-line chart.", selected_time_field.name, selected_measure_field.name, selected_dimension_field.name)
        if preferred_chart_type == "multi_line" and not can_multi_line and can_wide_multi_line:
            add_candidate("multi_line", 0.98, "User preferred multi-line chart.", selected_time_field.name, *[field.name for field in measure_fields[:6]])
        if preferred_chart_type == "heatmap" and can_heatmap:
            add_candidate("heatmap", 0.98, "User preferred heatmap.", heatmap_x_field.name, heatmap_y_field.name, selected_measure_field.name)
        if preferred_chart_type == "boxplot" and can_boxplot:
            if selected_dimension_field and 2 <= category_count <= 20:
                add_candidate("boxplot", 0.98, "User preferred box plot.", selected_dimension_field.name, selected_measure_field.name)
            else:
                add_candidate("boxplot", 0.98, "User preferred box plot.", selected_measure_field.name)
        if multi_metric_query:
            add_candidate("table", 0.93, "Several measures are requested; table preserves all metrics.")
        if precomputed_boxplot_fields is not None and (intent == "boxplot" or _is_boxplot_query(request.user_query)):
            category_field, q1_field, median_field, q3_field, min_field, max_field = precomputed_boxplot_fields
            add_candidate(
                "boxplot",
                0.96,
                "Precomputed quartiles by group are suitable for a box plot.",
                category_field.name,
                q1_field.name,
                median_field.name,
                q3_field.name,
                min_field.name if min_field else None,
                max_field.name if max_field else None,
            )
        if can_boxplot and (intent == "boxplot" or _is_boxplot_query(request.user_query)):
            if selected_dimension_field and 2 <= category_count <= 20:
                add_candidate("boxplot", 0.94, "Distribution with group breakdown is suitable for a box plot.", selected_dimension_field.name, selected_measure_field.name)
            else:
                add_candidate("boxplot", 0.94, "Numeric distribution is suitable for a box plot.", selected_measure_field.name)
        if can_heatmap and (intent == "heatmap" or _is_heatmap_query(request.user_query)):
            add_candidate("heatmap", 0.93, "Two discrete axes and one measure are suitable for a heatmap.", heatmap_x_field.name, heatmap_y_field.name, selected_measure_field.name)
        if can_histogram and (intent in {"histogram", "distribution"} or (_is_histogram_query(request.user_query) and not selected_dimension_field)):
            add_candidate("histogram", 0.92, "A single numeric distribution is suitable for a histogram.", selected_measure_field.name)
        if can_pie and (intent == "part_to_whole" or _is_part_to_whole_query(request.user_query)):
            add_candidate("pie", 0.91, "Few non-negative categories are suitable for a part-to-whole chart.", selected_dimension_field.name, selected_measure_field.name)
        if can_stacked_bar and (intent == "composition" or _is_stacked_query(request.user_query)):
            add_candidate("stacked_bar", 0.9, "Two category fields and one measure are suitable for a stacked bar chart.", selected_discrete_field.name, selected_measure_field.name, secondary_dimension_field.name)
        if selected_time_field and selected_measure_field and table.row_count >= 3 and (intent == "area" or _is_area_query(request.user_query)):
            add_candidate("area", 0.9, "Time field and measure can show accumulated volume as an area chart.", selected_time_field.name, selected_measure_field.name)
        if can_multi_line and (intent == "trend" or _is_multi_series_query(request.user_query)):
            add_candidate("multi_line", 0.92, "Time, measure, and low-cardinality group are suitable for a multi-line chart.", selected_time_field.name, selected_measure_field.name, selected_dimension_field.name)
        if can_wide_multi_line and not multi_metric_query and _is_multi_series_query(request.user_query):
            add_candidate("multi_line", 0.91, "Several measures over time are suitable for a multi-line chart.", selected_time_field.name, *[field.name for field in measure_fields[:6]])
        if selected_time_field and selected_measure_field:
            add_candidate(
                "line",
                0.9 if intent == "trend" else 0.55,
                "Time field and measure are available.",
                selected_time_field.name,
                selected_measure_field.name,
            )
        if _is_scatter_query(request.user_query) and selected_dimension_field and selected_measure_field:
            add_candidate(
                "scatter",
                0.93,
                "User asked to show categorical values as points.",
                selected_dimension_field.name,
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
        if len(measure_fields) >= 2 and (intent == "correlation" or preferred_chart_type == "scatter" or _is_scatter_query(request.user_query)):
            score = 0.94 if intent == "correlation" or _is_scatter_query(request.user_query) else 0.45
            add_candidate("scatter", score, "Two measures are available.", measure_fields[0].name, measure_fields[1].name)
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
        field_by_name = {field.name: field for field in metadata}

        def named_field(name: str | None) -> FieldMetadata | None:
            return field_by_name.get(name) if name else None

        if chart_type == "line" and time_fields and measure_fields:
            x_field = _field_by_name(time_fields, selected_candidate.fields[0] if selected_candidate.fields else None, time_fields[0])
            y_field = _field_by_name(measure_fields, selected_candidate.fields[1] if len(selected_candidate.fields) > 1 else None, measure_fields[0])
            spec = chart_spec(
                chart_type="line",
                title=title,
                x_field=x_field,
                y_field=y_field,
                table=table,
            )
            selected = SelectedView(type="chart", chart_type="line", title=title, spec=spec, normalized_spec=spec)
            used_fields = [x_field.name, y_field.name]
        elif chart_type == "area" and time_fields and measure_fields:
            x_field = _field_by_name(time_fields, selected_candidate.fields[0] if selected_candidate.fields else None, time_fields[0])
            y_field = _field_by_name(measure_fields, selected_candidate.fields[1] if len(selected_candidate.fields) > 1 else None, measure_fields[0])
            spec = chart_spec(
                chart_type="area",
                title=title,
                x_field=x_field,
                y_field=y_field,
                table=table,
            )
            selected = SelectedView(type="chart", chart_type="area", title=title, spec=spec, normalized_spec=spec)
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
        elif chart_type == "pie" and len(selected_candidate.fields) >= 2:
            x_field = named_field(selected_candidate.fields[0])
            y_field = named_field(selected_candidate.fields[1])
            if x_field and y_field:
                spec = chart_spec(
                    chart_type="pie",
                    title=title,
                    x_field=x_field,
                    y_field=y_field,
                    table=table,
                )
                selected = SelectedView(type="chart", chart_type="pie", title=title, spec=spec, normalized_spec=spec)
                used_fields = [x_field.name, y_field.name]
            else:
                spec = table_spec(title, table)
                selected = SelectedView(type="table", chart_type="table", title=title, spec=spec, normalized_spec=spec)
                used_fields = list(table.columns)
        elif chart_type == "histogram" and selected_candidate.fields:
            x_field = named_field(selected_candidate.fields[0])
            if x_field:
                spec = chart_spec(
                    chart_type="histogram",
                    title=title,
                    x_field=x_field,
                    y_field=None,
                    table=table,
                )
                selected = SelectedView(type="chart", chart_type="histogram", title=title, spec=spec, normalized_spec=spec)
                used_fields = [x_field.name]
            else:
                spec = table_spec(title, table)
                selected = SelectedView(type="table", chart_type="table", title=title, spec=spec, normalized_spec=spec)
                used_fields = list(table.columns)
        elif chart_type == "stacked_bar" and len(selected_candidate.fields) >= 3:
            x_field = named_field(selected_candidate.fields[0])
            y_field = named_field(selected_candidate.fields[1])
            color_field = named_field(selected_candidate.fields[2])
            if x_field and y_field and color_field:
                spec = chart_spec(
                    chart_type="stacked_bar",
                    title=title,
                    x_field=x_field,
                    y_field=y_field,
                    color_field=color_field,
                    table=table,
                )
                selected = SelectedView(type="chart", chart_type="stacked_bar", title=title, spec=spec, normalized_spec=spec)
                used_fields = [x_field.name, y_field.name, color_field.name]
            else:
                spec = table_spec(title, table)
                selected = SelectedView(type="table", chart_type="table", title=title, spec=spec, normalized_spec=spec)
                used_fields = list(table.columns)
        elif chart_type == "multi_line" and len(selected_candidate.fields) >= 3:
            x_field = named_field(selected_candidate.fields[0])
            second_field = named_field(selected_candidate.fields[1])
            third_field = named_field(selected_candidate.fields[2])
            if x_field and second_field and third_field and third_field.semantic_role == "dimension":
                spec = chart_spec(
                    chart_type="multi_line",
                    title=title,
                    x_field=x_field,
                    y_field=second_field,
                    color_field=third_field,
                    table=table,
                )
                selected = SelectedView(type="chart", chart_type="multi_line", title=title, spec=spec, normalized_spec=spec)
                used_fields = [x_field.name, second_field.name, third_field.name]
            else:
                measure_series = [field for field in (named_field(name) for name in selected_candidate.fields[1:]) if field and field.semantic_role == "measure"]
                if x_field and len(measure_series) >= 2:
                    spec = multi_measure_line_spec(
                        title=title,
                        x_field=x_field,
                        measure_fields=measure_series,
                        table=table,
                    )
                    selected = SelectedView(type="chart", chart_type="multi_line", title=title, spec=spec, normalized_spec=spec)
                    used_fields = [x_field.name, *[field.name for field in measure_series]]
                else:
                    spec = table_spec(title, table)
                    selected = SelectedView(type="table", chart_type="table", title=title, spec=spec, normalized_spec=spec)
                    used_fields = list(table.columns)
        elif chart_type == "heatmap" and len(selected_candidate.fields) >= 3:
            x_field = named_field(selected_candidate.fields[0])
            y_field = named_field(selected_candidate.fields[1])
            color_field = named_field(selected_candidate.fields[2])
            if x_field and y_field and color_field:
                spec = chart_spec(
                    chart_type="heatmap",
                    title=title,
                    x_field=x_field,
                    y_field=y_field,
                    color_field=color_field,
                    table=table,
                )
                selected = SelectedView(type="chart", chart_type="heatmap", title=title, spec=spec, normalized_spec=spec)
                used_fields = [x_field.name, y_field.name, color_field.name]
            else:
                spec = table_spec(title, table)
                selected = SelectedView(type="table", chart_type="table", title=title, spec=spec, normalized_spec=spec)
                used_fields = list(table.columns)
        elif chart_type == "boxplot" and selected_candidate.fields:
            first_field = named_field(selected_candidate.fields[0])
            second_field = named_field(selected_candidate.fields[1]) if len(selected_candidate.fields) > 1 else None
            third_field = named_field(selected_candidate.fields[2]) if len(selected_candidate.fields) > 2 else None
            fourth_field = named_field(selected_candidate.fields[3]) if len(selected_candidate.fields) > 3 else None
            fifth_field = named_field(selected_candidate.fields[4]) if len(selected_candidate.fields) > 4 else None
            sixth_field = named_field(selected_candidate.fields[5]) if len(selected_candidate.fields) > 5 else None
            if first_field and second_field and third_field and fourth_field:
                spec = precomputed_boxplot_spec(
                    title=title,
                    category_field=first_field,
                    q1_field=second_field,
                    median_field=third_field,
                    q3_field=fourth_field,
                    min_field=fifth_field,
                    max_field=sixth_field,
                    table=table,
                )
                selected = SelectedView(type="chart", chart_type="boxplot", title=title, spec=spec, normalized_spec=spec)
                used_fields = [field.name for field in (first_field, second_field, third_field, fourth_field, fifth_field, sixth_field) if field]
            elif first_field and second_field:
                spec = chart_spec(
                    chart_type="boxplot",
                    title=title,
                    x_field=first_field,
                    y_field=second_field,
                    table=table,
                )
                selected = SelectedView(type="chart", chart_type="boxplot", title=title, spec=spec, normalized_spec=spec)
                used_fields = [first_field.name, second_field.name]
            elif first_field:
                spec = chart_spec(
                    chart_type="boxplot",
                    title=title,
                    x_field=first_field,
                    y_field=None,
                    table=table,
                )
                selected = SelectedView(type="chart", chart_type="boxplot", title=title, spec=spec, normalized_spec=spec)
                used_fields = [first_field.name]
            else:
                spec = table_spec(title, table)
                selected = SelectedView(type="table", chart_type="table", title=title, spec=spec, normalized_spec=spec)
                used_fields = list(table.columns)
        elif chart_type == "scatter":
            x_field = named_field(selected_candidate.fields[0]) if selected_candidate.fields else None
            y_field = named_field(selected_candidate.fields[1]) if len(selected_candidate.fields) > 1 else None
            if not (x_field and y_field) and len(measure_fields) >= 2:
                x_field = measure_fields[0]
                y_field = measure_fields[1]
            if x_field and y_field:
                spec = chart_spec(
                    chart_type="scatter",
                    title=title,
                    x_field=x_field,
                    y_field=y_field,
                    table=table,
                )
                selected = SelectedView(type="chart", chart_type="scatter", title=title, spec=spec, normalized_spec=spec)
                used_fields = [x_field.name, y_field.name]
            else:
                spec = table_spec(title, table)
                selected = SelectedView(type="table", chart_type="table", title=title, spec=spec, normalized_spec=spec)
                used_fields = list(table.columns)
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
        if chart_type == "area":
            return "Динамика объема"
        if chart_type == "bar":
            return "Сравнение по категориям"
        if chart_type == "scatter":
            return "Связь показателей"
        if chart_type == "pie":
            return "Доля от общего"
        if chart_type == "histogram":
            return "Распределение значений"
        if chart_type == "stacked_bar":
            return "Состав по категориям"
        if chart_type == "multi_line":
            return "Динамика по группам"
        if chart_type == "heatmap":
            return "Матрица значений"
        if chart_type == "boxplot":
            return "Разброс значений"
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
