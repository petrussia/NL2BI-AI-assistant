from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pytest

from contracts.extraction import DataSourceInfo, FieldMetadata, ResultTable
from contracts.visualization import VisualizationRequest
from services.visualization.cpu_visualization_service import CpuVisualizationService


ExpectedChartType = Literal["bar", "line", "table"]


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
    time_values: tuple[str, ...] | tuple[int, ...]
    count_field: str
    metric_field: str
    min_field: str
    avg_field: str
    max_field: str


@dataclass(frozen=True)
class QueryCase:
    source_id: str
    query_type: str
    query: str
    expected_chart_type: ExpectedChartType
    request: VisualizationRequest


QUERY_TYPES: tuple[tuple[str, str, ExpectedChartType], ...] = (
    ("L1 count", "count", "table"),
    ("L1 top-n", "top_n", "bar"),
    ("L1 filter", "filter_count", "table"),
    ("L1 group-by", "group_by", "bar"),
    ("L2 ts", "time_series", "line"),
    ("L2 join", "join_list", "table"),
    ("L2 having", "having", "bar"),
    ("L3 mhop join", "multi_hop", "bar"),
    ("L3 subquery", "subquery", "bar"),
    ("L3 mulagg", "multi_aggregate", "table"),
)


SOURCE_QUERIES: dict[str, tuple[str, ...]] = {
    "demo_concert_singer": (
        "Сколько всего певцов в базе",
        "Топ-5 стадионов по вместимости",
        "Сколько певцов из Франции",
        "Сравни количество певцов по странам",
        "Количество концертов по годам",
        "Какие певцы участвовали в концерте Auditions",
        "Страны где больше 1 певца",
        "Топ-3 стадиона по количеству концертов",
        "Певцы старше среднего возраста",
        "Среднее, минимум и максимум возраста певцов по странам",
    ),
    "bird_student_club": (
        "How many members are in the club",
        "Top 5 members by attendance count",
        "How many events are completed",
        "Count of members per major",
        "Number of events per month",
        "List members who attended Yearly Kickoff event",
        "Majors with at least 2 members",
        "Total expense amount per event",
        "Members who attended more than average events",
        "Average expense per category with min and max",
    ),
    "spider2_retail_dbt": (
        "How many completed orders are in the retail dataset",
        "Top 5 product categories by revenue",
        "How many online orders were completed",
        "Revenue by sales channel",
        "Monthly revenue trend in 2024",
        "List top products with their category and total revenue",
        "Stores with revenue above 100000",
        "Revenue by customer segment and region",
        "Product categories with revenue above the average category revenue",
        "Min, avg, max order revenue by customer segment",
    ),
    "moscow_open": (
        "Сколько всего станций метро",
        "Топ-5 районов по населению",
        "Сколько станций открыто после 2010 года",
        "Сколько станций на каждой линии",
        "Сколько станций открыто по десятилетиям",
        "Сколько станций в каждом округе",
        "Линии с более чем 15 станциями",
        "Самые загруженные станции в Центральном округе",
        "Округа с населением выше среднего",
        "Минимум, среднее и максимум населения районов по округам",
    ),
    "northwind_ru": (
        "Сколько всего заказов",
        "Топ-5 товаров по выручке",
        "Сколько клиентов из сегмента HoReCa",
        "Сколько продано в каждой категории",
        "Динамика заказов по месяцам 2024",
        "Топ-5 клиентов по сумме заказов",
        "Категории с выручкой больше миллиона",
        "Выручка по федеральным округам России",
        "Клиенты с заказами выше среднего чека",
        "Минимум, среднее и максимум стоимости заказа по сегментам",
    ),
}


SOURCE_PROFILES: dict[str, SourceProfile] = {
    "demo_concert_singer": SourceProfile(
        source_id="demo_concert_singer",
        entity_field="singer_name",
        entity_values=("Alice", "Bruno", "Carla", "Dmitry", "Eva"),
        group_field="country",
        group_values=("France", "USA", "Italy", "Spain"),
        secondary_field="concert_name",
        secondary_values=("Auditions", "Finals", "Encore"),
        time_field="year",
        time_values=(2021, 2022, 2023),
        count_field="singer_count",
        metric_field="age",
        min_field="min_age",
        avg_field="avg_age",
        max_field="max_age",
    ),
    "bird_student_club": SourceProfile(
        source_id="bird_student_club",
        entity_field="member_name",
        entity_values=("Alex", "Brooke", "Casey", "Dana", "Eli"),
        group_field="major",
        group_values=("CS", "Math", "Business", "Design"),
        secondary_field="event_name",
        secondary_values=("Yearly Kickoff", "Budget Review", "Career Night"),
        time_field="month",
        time_values=("2024-01", "2024-02", "2024-03"),
        count_field="attendance_count",
        metric_field="expense_amount",
        min_field="min_expense",
        avg_field="avg_expense",
        max_field="max_expense",
    ),
    "spider2_retail_dbt": SourceProfile(
        source_id="spider2_retail_dbt",
        entity_field="category_name",
        entity_values=("Coffee and tea", "Electronics accessories", "Snacks", "Personal care", "Pet supplies"),
        group_field="channel",
        group_values=("store", "online", "marketplace", "call center"),
        secondary_field="region",
        secondary_values=("Central", "North-West", "Volga"),
        time_field="month",
        time_values=("2024-01", "2024-02", "2024-03"),
        count_field="order_count",
        metric_field="revenue",
        min_field="min_order_revenue",
        avg_field="avg_order_revenue",
        max_field="max_order_revenue",
    ),
    "moscow_open": SourceProfile(
        source_id="moscow_open",
        entity_field="station_name",
        entity_values=("Aeroport", "Belorusskaya", "Dinamo", "Mayakovskaya", "Sokol"),
        group_field="line_name",
        group_values=("Green", "Red", "Blue", "Ring"),
        secondary_field="okrug_name",
        secondary_values=("Central", "North", "South"),
        time_field="decade",
        time_values=(1990, 2000, 2010),
        count_field="station_count",
        metric_field="population",
        min_field="min_population",
        avg_field="avg_population",
        max_field="max_population",
    ),
    "northwind_ru": SourceProfile(
        source_id="northwind_ru",
        entity_field="client_name",
        entity_values=("Alfa", "Beta", "Gamma", "Delta", "Epsilon"),
        group_field="category_name",
        group_values=("Beverages", "Snacks", "Seafood", "Dairy"),
        secondary_field="region_name",
        secondary_values=("Central", "Volga", "Siberia"),
        time_field="month",
        time_values=("2024-01", "2024-02", "2024-03"),
        count_field="orders_count",
        metric_field="revenue",
        min_field="min_order_value",
        avg_field="avg_order_value",
        max_field="max_order_value",
    ),
}


def _field(name: str, data_type: str, role: str) -> FieldMetadata:
    return FieldMetadata(
        name=name,
        data_type=data_type,
        semantic_role=role,
        allowed_aggregations=["none"],
        default_aggregation="none",
    )


def _request(
    *,
    profile: SourceProfile,
    query: str,
    columns: list[str],
    rows: list[dict],
    metadata: list[FieldMetadata],
) -> VisualizationRequest:
    return VisualizationRequest(
        request_id=f"test-{profile.source_id}-{abs(hash(query))}",
        user_query=query,
        data_source=DataSourceInfo(id=profile.source_id),
        result_table=ResultTable(columns=columns, rows=rows, row_count=len(rows)),
        field_metadata=metadata,
    )


def _rows_for_bar(dim: str, values: tuple[str, ...], measure: str) -> list[dict]:
    return [{dim: value, measure: (index + 2) * 10} for index, value in enumerate(values)]


def _case_for_kind(profile: SourceProfile, query_type: str, query: str, kind: str, expected: ExpectedChartType) -> QueryCase:
    if kind == "count":
        columns = [profile.count_field]
        rows = [{profile.count_field: 42}]
        metadata = [_field(profile.count_field, "number", "measure")]
    elif kind == "filter_count":
        columns = [profile.count_field]
        rows = [{profile.count_field: 7}]
        metadata = [_field(profile.count_field, "number", "measure")]
    elif kind == "top_n":
        columns = [profile.entity_field, profile.metric_field]
        rows = _rows_for_bar(profile.entity_field, profile.entity_values, profile.metric_field)
        metadata = [_field(profile.entity_field, "string", "dimension"), _field(profile.metric_field, "number", "measure")]
    elif kind == "group_by":
        columns = [profile.group_field, profile.count_field]
        rows = _rows_for_bar(profile.group_field, profile.group_values, profile.count_field)
        metadata = [_field(profile.group_field, "string", "dimension"), _field(profile.count_field, "number", "measure")]
    elif kind == "time_series":
        columns = [profile.time_field, profile.count_field]
        rows = [{profile.time_field: value, profile.count_field: (index + 1) * 8} for index, value in enumerate(profile.time_values)]
        time_type = "number" if all(isinstance(value, int) for value in profile.time_values) else "date"
        metadata = [_field(profile.time_field, time_type, "time"), _field(profile.count_field, "number", "measure")]
    elif kind == "join_list":
        columns = [profile.entity_field, profile.secondary_field]
        rows = [
            {profile.entity_field: profile.entity_values[index], profile.secondary_field: profile.secondary_values[index % len(profile.secondary_values)]}
            for index in range(3)
        ]
        metadata = [_field(profile.entity_field, "string", "dimension"), _field(profile.secondary_field, "string", "dimension")]
    elif kind == "having":
        columns = [profile.group_field, profile.count_field]
        rows = _rows_for_bar(profile.group_field, profile.group_values, profile.count_field)
        metadata = [_field(profile.group_field, "string", "dimension"), _field(profile.count_field, "number", "measure")]
    elif kind == "multi_hop":
        columns = [profile.secondary_field, profile.metric_field]
        rows = _rows_for_bar(profile.secondary_field, profile.secondary_values, profile.metric_field)
        metadata = [_field(profile.secondary_field, "string", "dimension"), _field(profile.metric_field, "number", "measure")]
    elif kind == "subquery":
        columns = [profile.entity_field, profile.metric_field]
        rows = _rows_for_bar(profile.entity_field, profile.entity_values, profile.metric_field)
        metadata = [_field(profile.entity_field, "string", "dimension"), _field(profile.metric_field, "number", "measure")]
    elif kind == "multi_aggregate":
        columns = [profile.group_field, profile.min_field, profile.avg_field, profile.max_field]
        rows = [
            {
                profile.group_field: value,
                profile.min_field: 10 + index,
                profile.avg_field: 20 + index,
                profile.max_field: 30 + index,
            }
            for index, value in enumerate(profile.group_values[:3])
        ]
        metadata = [
            _field(profile.group_field, "string", "dimension"),
            _field(profile.min_field, "number", "measure"),
            _field(profile.avg_field, "number", "measure"),
            _field(profile.max_field, "number", "measure"),
        ]
    else:
        raise AssertionError(f"unknown query kind: {kind}")

    return QueryCase(
        source_id=profile.source_id,
        query_type=query_type,
        query=query,
        expected_chart_type=expected,
        request=_request(profile=profile, query=query, columns=columns, rows=rows, metadata=metadata),
    )


def build_all_source_query_cases() -> list[QueryCase]:
    cases: list[QueryCase] = []
    for source_id, queries in SOURCE_QUERIES.items():
        profile = SOURCE_PROFILES[source_id]
        assert len(queries) == len(QUERY_TYPES)
        for (query_type, kind, expected), query in zip(QUERY_TYPES, queries, strict=True):
            cases.append(_case_for_kind(profile, query_type, query, kind, expected))
    return cases


@pytest.mark.parametrize(
    "case",
    build_all_source_query_cases(),
    ids=lambda case: f"{case.source_id}::{case.query_type}",
)
def test_all_source_queries_select_expected_visualization(case: QueryCase):
    response = CpuVisualizationService().visualize(case.request)

    assert response.status == "success"
    assert response.selected_view.chart_type == case.expected_chart_type
    if case.expected_chart_type == "table":
        assert response.selected_view.type == "table"
        assert response.selected_view.spec["type"] == "table"
    else:
        assert response.selected_view.type == "chart"
        assert response.selected_view.spec["data"]["values"]
        assert response.selected_view.spec["encoding"]
