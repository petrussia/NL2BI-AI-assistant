from __future__ import annotations

from dataclasses import dataclass

import pytest

from contracts.extraction import DataSourceInfo, FieldMetadata, ResultTable
from contracts.visualization import ChartType, VisualizationRequest
from services.visualization.cpu_visualization_service import CpuVisualizationService


CHART_TYPES: tuple[ChartType, ...] = (
    "bar",
    "line",
    "scatter",
    "area",
    "pie",
    "histogram",
    "stacked_bar",
    "multi_line",
    "heatmap",
    "boxplot",
)


@dataclass(frozen=True)
class SourceProfile:
    source_id: str
    entity_field: str
    entity_values: tuple[str, ...]
    group_field: str
    group_values: tuple[str, ...]
    secondary_field: str
    secondary_values: tuple[str, ...]
    time_field: str
    time_values: tuple[str, ...]
    metric_field: str
    metric2_field: str


@dataclass(frozen=True)
class ChartTypeCase:
    source_id: str
    expected_chart_type: ChartType
    query: str
    request: VisualizationRequest


SOURCE_PROFILES: tuple[SourceProfile, ...] = (
    SourceProfile(
        source_id="demo_concert_singer",
        entity_field="singer_name",
        entity_values=("Alice", "Bruno", "Carla", "Dmitry", "Eva"),
        group_field="country",
        group_values=("France", "USA", "Italy", "Spain"),
        secondary_field="concert_name",
        secondary_values=("Auditions", "Finals", "Encore"),
        time_field="year",
        time_values=("2021", "2022", "2023", "2024"),
        metric_field="concert_count",
        metric2_field="avg_age",
    ),
    SourceProfile(
        source_id="bird_student_club",
        entity_field="member_name",
        entity_values=("Alex", "Brooke", "Casey", "Dana", "Eli"),
        group_field="major",
        group_values=("CS", "Math", "Business", "Design"),
        secondary_field="event_name",
        secondary_values=("Kickoff", "Budget Review", "Career Night"),
        time_field="month",
        time_values=("2024-01", "2024-02", "2024-03", "2024-04"),
        metric_field="attendance_count",
        metric2_field="expense_amount",
    ),
    SourceProfile(
        source_id="spider2_retail_dbt",
        entity_field="category_name",
        entity_values=("Coffee and tea", "Electronics accessories", "Snacks", "Personal care", "Pet supplies"),
        group_field="channel",
        group_values=("store", "online", "marketplace", "call center"),
        secondary_field="region",
        secondary_values=("Central", "North-West", "Volga"),
        time_field="month",
        time_values=("2024-01", "2024-02", "2024-03", "2024-04"),
        metric_field="revenue",
        metric2_field="order_count",
    ),
    SourceProfile(
        source_id="moscow_open",
        entity_field="station_name",
        entity_values=("Aeroport", "Belorusskaya", "Dinamo", "Mayakovskaya", "Sokol"),
        group_field="line_name",
        group_values=("Green", "Red", "Blue", "Ring"),
        secondary_field="okrug_name",
        secondary_values=("Central", "North", "South"),
        time_field="year",
        time_values=("1990", "2000", "2010", "2020"),
        metric_field="station_count",
        metric2_field="population",
    ),
    SourceProfile(
        source_id="northwind_ru",
        entity_field="client_name",
        entity_values=("Alfa", "Beta", "Gamma", "Delta", "Epsilon"),
        group_field="category_name",
        group_values=("Beverages", "Snacks", "Seafood", "Dairy"),
        secondary_field="region_name",
        secondary_values=("Central", "Volga", "Siberia"),
        time_field="month",
        time_values=("2024-01", "2024-02", "2024-03", "2024-04"),
        metric_field="revenue",
        metric2_field="orders_count",
    ),
)


def _field(name: str, data_type: str, role: str) -> FieldMetadata:
    return FieldMetadata(
        name=name,
        data_type=data_type,
        semantic_role=role,
        allowed_aggregations=["none"],
        default_aggregation="none",
    )


def _request(profile: SourceProfile, chart_type: ChartType, query: str, columns: list[str], rows: list[dict], metadata: list[FieldMetadata]) -> VisualizationRequest:
    return VisualizationRequest(
        request_id=f"chart-type-{profile.source_id}-{chart_type}",
        user_query=query,
        data_source=DataSourceInfo(id=profile.source_id),
        result_table=ResultTable(columns=columns, rows=rows, row_count=len(rows)),
        field_metadata=metadata,
    )


def _group_rows(profile: SourceProfile, field: str, values: tuple[str, ...], metric: str) -> list[dict]:
    return [{field: value, metric: (index + 2) * 11} for index, value in enumerate(values)]


def _time_rows(profile: SourceProfile, *, grouped: bool = False) -> list[dict]:
    if not grouped:
        return [
            {profile.time_field: value, profile.metric_field: (index + 1) * 15}
            for index, value in enumerate(profile.time_values)
        ]
    rows: list[dict] = []
    for group_index, group in enumerate(profile.group_values[:3]):
        for time_index, value in enumerate(profile.time_values):
            rows.append(
                {
                    profile.time_field: value,
                    profile.group_field: group,
                    profile.metric_field: (time_index + 1) * 10 + group_index * 6,
                }
            )
    return rows


def _stacked_rows(profile: SourceProfile) -> list[dict]:
    rows: list[dict] = []
    for group_index, group in enumerate(profile.group_values[:3]):
        for secondary_index, secondary in enumerate(profile.secondary_values[:3]):
            rows.append(
                {
                    profile.group_field: group,
                    profile.secondary_field: secondary,
                    profile.metric_field: 20 + group_index * 8 + secondary_index * 5,
                }
            )
    return rows


def _distribution_rows(profile: SourceProfile) -> list[dict]:
    values = (10, 12, 15, 18, 22, 28, 35, 45, 58, 72)
    return [{profile.metric_field: value} for value in values]


def _grouped_distribution_rows(profile: SourceProfile) -> list[dict]:
    rows: list[dict] = []
    values = (10, 12, 15, 18, 28, 34)
    for group_index, group in enumerate(profile.group_values[:3]):
        for value in values:
            rows.append({profile.group_field: group, profile.metric_field: value + group_index * 7})
    return rows


def _case(profile: SourceProfile, chart_type: ChartType) -> ChartTypeCase:
    if chart_type == "bar":
        query = f"Сравни {profile.metric_field} по {profile.group_field} столбчатой диаграммой"
        columns = [profile.group_field, profile.metric_field]
        rows = _group_rows(profile, profile.group_field, profile.group_values, profile.metric_field)
        metadata = [_field(profile.group_field, "string", "dimension"), _field(profile.metric_field, "number", "measure")]
    elif chart_type == "line":
        query = f"Покажи динамику {profile.metric_field} по {profile.time_field} линейным графиком"
        columns = [profile.time_field, profile.metric_field]
        rows = _time_rows(profile)
        metadata = [_field(profile.time_field, "date", "time"), _field(profile.metric_field, "number", "measure")]
    elif chart_type == "scatter":
        query = f"Покажи корреляцию между {profile.metric_field} и {profile.metric2_field} scatter"
        columns = [profile.metric_field, profile.metric2_field]
        rows = [
            {profile.metric_field: 10 + index * 7, profile.metric2_field: 20 + index * 9}
            for index in range(8)
        ]
        metadata = [_field(profile.metric_field, "number", "measure"), _field(profile.metric2_field, "number", "measure")]
    elif chart_type == "area":
        query = f"Покажи областной график динамики {profile.metric_field} по {profile.time_field}"
        columns = [profile.time_field, profile.metric_field]
        rows = _time_rows(profile)
        metadata = [_field(profile.time_field, "date", "time"), _field(profile.metric_field, "number", "measure")]
    elif chart_type == "pie":
        query = f"Покажи долю {profile.metric_field} по {profile.group_field} круговой диаграммой"
        columns = [profile.group_field, profile.metric_field]
        rows = _group_rows(profile, profile.group_field, profile.group_values, profile.metric_field)
        metadata = [_field(profile.group_field, "string", "dimension"), _field(profile.metric_field, "number", "measure")]
    elif chart_type == "histogram":
        query = f"Покажи распределение {profile.metric_field} гистограммой"
        columns = [profile.metric_field]
        rows = _distribution_rows(profile)
        metadata = [_field(profile.metric_field, "number", "measure")]
    elif chart_type == "stacked_bar":
        query = f"Покажи {profile.metric_field} по {profile.group_field} с разбивкой по {profile.secondary_field} stacked"
        columns = [profile.group_field, profile.secondary_field, profile.metric_field]
        rows = _stacked_rows(profile)
        metadata = [
            _field(profile.group_field, "string", "dimension"),
            _field(profile.secondary_field, "string", "dimension"),
            _field(profile.metric_field, "number", "measure"),
        ]
    elif chart_type == "multi_line":
        query = f"Покажи динамику {profile.metric_field} по {profile.time_field} в разрезе {profile.group_field} несколькими линиями"
        columns = [profile.time_field, profile.group_field, profile.metric_field]
        rows = _time_rows(profile, grouped=True)
        metadata = [
            _field(profile.time_field, "date", "time"),
            _field(profile.group_field, "string", "dimension"),
            _field(profile.metric_field, "number", "measure"),
        ]
    elif chart_type == "heatmap":
        query = f"Построй тепловую карту {profile.metric_field} по {profile.group_field} и {profile.secondary_field}"
        columns = [profile.group_field, profile.secondary_field, profile.metric_field]
        rows = _stacked_rows(profile)
        metadata = [
            _field(profile.group_field, "string", "dimension"),
            _field(profile.secondary_field, "string", "dimension"),
            _field(profile.metric_field, "number", "measure"),
        ]
    elif chart_type == "boxplot":
        query = f"Покажи boxplot {profile.metric_field} по {profile.group_field}, ящик с усами и выбросы"
        columns = [profile.group_field, profile.metric_field]
        rows = _grouped_distribution_rows(profile)
        metadata = [_field(profile.group_field, "string", "dimension"), _field(profile.metric_field, "number", "measure")]
    else:
        raise AssertionError(f"unexpected chart type: {chart_type}")

    return ChartTypeCase(
        source_id=profile.source_id,
        expected_chart_type=chart_type,
        query=query,
        request=_request(profile, chart_type, query, columns, rows, metadata),
    )


def build_all_chart_type_cases() -> list[ChartTypeCase]:
    return [_case(profile, chart_type) for profile in SOURCE_PROFILES for chart_type in CHART_TYPES]


@pytest.mark.parametrize(
    "case",
    build_all_chart_type_cases(),
    ids=lambda case: f"{case.source_id}::{case.expected_chart_type}",
)
def test_all_chart_types_are_selected_for_each_source(case: ChartTypeCase):
    response = CpuVisualizationService().visualize(case.request)

    assert response.status == "success"
    assert response.selected_view.type == "chart"
    assert response.selected_view.chart_type == case.expected_chart_type
    assert response.selected_view.spec["data"]["values"]
    assert response.selected_view.spec["encoding"]
