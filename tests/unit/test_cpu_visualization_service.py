from contracts.extraction import DataExtractionResponse, DataSourceInfo, FieldMetadata, FieldProvenance, ResultTable
from contracts.visualization import PresentationPreferences, VisualizationRequest
from services.adapter.extraction_to_visualization import adapt_extraction_to_visualization
from services.visualization.cpu_visualization_service import CpuVisualizationService
from services.visualization.render import chart_spec


def test_time_series_becomes_line():
    request = VisualizationRequest(
        request_id="r1",
        user_query="Покажи динамику продаж по месяцам",
        data_source=DataSourceInfo(id="demo_concert_singer"),
        result_table=ResultTable(
            columns=["month", "revenue"],
            rows=[
                {"month": "2026-01", "revenue": 10},
                {"month": "2026-02", "revenue": 20},
                {"month": "2026-03", "revenue": 30},
            ],
            row_count=3,
        ),
        field_metadata=[
            FieldMetadata(name="month", data_type="date", semantic_role="time", allowed_aggregations=["none"], default_aggregation="none"),
            FieldMetadata(name="revenue", data_type="number", semantic_role="measure", allowed_aggregations=["sum"], default_aggregation="sum"),
        ],
    )
    response = CpuVisualizationService().visualize(request)
    assert response.status == "success"
    assert response.selected_view.chart_type == "line"


def test_year_month_result_uses_combined_month_axis():
    request = VisualizationRequest(
        request_id="r1",
        user_query="Monthly revenue trend by year and month",
        data_source=DataSourceInfo(id="spider2_retail_dbt"),
        result_table=ResultTable(
            columns=["year", "month", "completed_tasks_count"],
            rows=[
                {"year": 2023, "month": 8, "completed_tasks_count": 4},
                {"year": 2023, "month": 9, "completed_tasks_count": 2},
                {"year": 2024, "month": 1, "completed_tasks_count": 1},
            ],
            row_count=3,
        ),
        field_metadata=[
            FieldMetadata(name="year", data_type="number", semantic_role="time", allowed_aggregations=["none"], default_aggregation="none"),
            FieldMetadata(name="month", data_type="number", semantic_role="time", allowed_aggregations=["none"], default_aggregation="none"),
            FieldMetadata(name="completed_tasks_count", data_type="number", semantic_role="measure", allowed_aggregations=["none"], default_aggregation="none"),
        ],
    )

    response = CpuVisualizationService().visualize(request)

    assert response.status == "success"
    spec = response.selected_view.spec
    assert spec["encoding"]["x"]["field"] == "__period_month"
    assert spec["encoding"]["x"]["type"] == "temporal"
    assert spec["encoding"]["x"]["axis"]["format"] == "%Y-%m"
    assert spec["data"]["values"][0]["__period_month"] == "2023-08-01"
    assert spec["data"]["values"][2]["__period_month"] == "2024-01-01"


def test_russian_year_month_measure_uses_measure_on_y_axis():
    request = VisualizationRequest(
        request_id="r1",
        user_query="Динамика продаж по месяцам в 2024",
        data_source=DataSourceInfo(id="northwind_ru"),
        result_table=ResultTable(
            columns=["год", "месяц", "выручка"],
            rows=[
                {"год": 2024, "месяц": 1, "выручка": 100},
                {"год": 2024, "месяц": 2, "выручка": 200},
                {"год": 2024, "месяц": 3, "выручка": 150},
            ],
            row_count=3,
        ),
        field_metadata=[
            FieldMetadata(name="год", data_type="number", semantic_role="time", allowed_aggregations=["none"], default_aggregation="none"),
            FieldMetadata(name="месяц", data_type="number", semantic_role="time", allowed_aggregations=["none"], default_aggregation="none"),
            FieldMetadata(name="выручка", data_type="number", semantic_role="measure", allowed_aggregations=["none"], default_aggregation="none"),
        ],
    )

    response = CpuVisualizationService().visualize(request)

    assert response.selected_view.chart_type == "line"
    spec = response.selected_view.spec
    assert spec["encoding"]["x"]["field"] == "__period_month"
    assert spec["encoding"]["y"]["field"] == "выручка"
    assert spec["data"]["values"][0]["__period_month"] == "2024-01-01"


def test_visualizer_corrects_russian_time_fields_misclassified_as_measures():
    request = VisualizationRequest(
        request_id="r1",
        user_query="Сколько заказов в месяц было сделано",
        data_source=DataSourceInfo(id="northwind_ru"),
        result_table=ResultTable(
            columns=["год", "месяц", "количество_заказов"],
            rows=[
                {"год": 2024, "месяц": 1, "количество_заказов": 2},
                {"год": 2024, "месяц": 2, "количество_заказов": 2},
                {"год": 2024, "месяц": 3, "количество_заказов": 2},
            ],
            row_count=3,
        ),
        field_metadata=[
            FieldMetadata(name="год", data_type="number", semantic_role="measure"),
            FieldMetadata(name="месяц", data_type="number", semantic_role="measure"),
            FieldMetadata(name="количество_заказов", data_type="number", semantic_role="measure", allowed_aggregations=["none"], default_aggregation="none"),
        ],
    )

    response = CpuVisualizationService().visualize(request)

    assert response.selected_view.chart_type == "line"
    spec = response.selected_view.spec
    assert spec["encoding"]["x"]["field"] == "__period_month"
    assert spec["encoding"]["y"]["field"] == "количество_заказов"


def test_decade_time_series_does_not_become_scatter():
    request = VisualizationRequest(
        request_id="r1",
        user_query="Сколько станций открыто по десятилетиям",
        data_source=DataSourceInfo(id="moscow_open"),
        result_table=ResultTable(
            columns=["decade", "station_count"],
            rows=[
                {"decade": 1980, "station_count": 3},
                {"decade": 1990, "station_count": 4},
                {"decade": 2000, "station_count": 5},
            ],
            row_count=3,
        ),
        field_metadata=[
            FieldMetadata(name="decade", data_type="number", semantic_role="time"),
            FieldMetadata(name="station_count", data_type="number", semantic_role="measure", allowed_aggregations=["none"], default_aggregation="none"),
        ],
    )

    response = CpuVisualizationService().visualize(request)

    assert response.selected_view.chart_type == "line"
    assert response.selected_view.spec["encoding"]["x"]["type"] == "ordinal"
    assert response.selected_view.spec["encoding"]["y"]["field"] == "station_count"


def test_russian_scatter_prompt_with_two_measures_becomes_scatter():
    request = VisualizationRequest(
        request_id="r1",
        user_query="Построй точечную диаграмму: площадь района по X и население района по Y.",
        data_source=DataSourceInfo(id="moscow_open"),
        result_table=ResultTable(
            columns=["area_km2", "population"],
            rows=[
                {"area_km2": 18.65, "population": 161800},
                {"area_km2": 13.42, "population": 158700},
                {"area_km2": 5.04, "population": 110700},
                {"area_km2": 5.47, "population": 124200},
                {"area_km2": 3.7, "population": 61700},
            ],
            row_count=5,
        ),
        field_metadata=[
            FieldMetadata(name="area_km2", data_type="number", semantic_role="measure", allowed_aggregations=["none"], default_aggregation="none"),
            FieldMetadata(name="population", data_type="number", semantic_role="measure", allowed_aggregations=["none"], default_aggregation="none"),
        ],
    )

    response = CpuVisualizationService().visualize(request)

    assert response.selected_view.type == "chart"
    assert response.selected_view.chart_type == "scatter"
    assert response.selected_view.spec["mark"] == "point"
    assert response.selected_view.spec["encoding"]["x"]["field"] == "area_km2"
    assert response.selected_view.spec["encoding"]["y"]["field"] == "population"


def test_explicit_spider_scatter_with_label_uses_two_numeric_axes():
    request = VisualizationRequest(
        request_id="r1",
        user_query="Построй scatter plot без агрегации: возьми Capacity для X и Average для Y; подпиши точки названием стадиона.",
        data_source=DataSourceInfo(id="demo_concert_singer"),
        result_table=ResultTable(
            columns=["X", "Y", "Label"],
            rows=[
                {"X": 52063, "Y": 48000, "Label": "Hampden Park"},
                {"X": 67144, "Y": 59000, "Label": "Murrayfield Stadium"},
                {"X": 20866, "Y": 16000, "Label": "Pittodrie Stadium"},
            ],
            row_count=3,
        ),
        field_metadata=[
            FieldMetadata(name="X", data_type="number", semantic_role="measure", allowed_aggregations=["none"], default_aggregation="none"),
            FieldMetadata(name="Y", data_type="number", semantic_role="measure", allowed_aggregations=["none"], default_aggregation="none"),
            FieldMetadata(name="Label", data_type="string", semantic_role="dimension"),
        ],
    )

    response = CpuVisualizationService().visualize(request)

    assert response.selected_view.chart_type == "scatter"
    assert response.selected_view.spec["mark"] == "point"
    assert response.selected_view.spec["encoding"]["x"]["field"] == "X"
    assert response.selected_view.spec["encoding"]["y"]["field"] == "Y"


def test_explicit_point_prompt_with_dimension_and_measure_uses_points_not_bar():
    request = VisualizationRequest(
        request_id="r1",
        user_query="Покажи точками вместимость каждого стадиона по названию.",
        data_source=DataSourceInfo(id="demo_concert_singer"),
        result_table=ResultTable(
            columns=["Name", "Capacity"],
            rows=[
                {"Name": "Caledonian Stadium", "Capacity": 7500},
                {"Name": "Dens Park", "Capacity": 11506},
                {"Name": "Hampden Park", "Capacity": 52063},
            ],
            row_count=3,
        ),
        field_metadata=[
            FieldMetadata(name="Name", data_type="string", semantic_role="dimension"),
            FieldMetadata(name="Capacity", data_type="number", semantic_role="measure", default_aggregation="sum"),
        ],
    )

    response = CpuVisualizationService().visualize(request)

    assert response.selected_view.chart_type == "scatter"
    assert response.selected_view.spec["mark"] == "point"
    assert response.selected_view.spec["encoding"]["x"]["field"] == "Name"
    assert response.selected_view.spec["encoding"]["y"]["field"] == "Capacity"
    assert "aggregate" not in response.selected_view.spec["encoding"]["y"]


def test_multi_metric_query_prefers_table_to_preserve_metrics():
    request = VisualizationRequest(
        request_id="r1",
        user_query="Минимум, среднее и максимум населения районов по округам",
        data_source=DataSourceInfo(id="moscow_open"),
        result_table=ResultTable(
            columns=["okrug_name", "min_population", "avg_population", "max_population"],
            rows=[
                {"okrug_name": "Центральный", "min_population": 10, "avg_population": 20, "max_population": 30},
                {"okrug_name": "Северный", "min_population": 11, "avg_population": 21, "max_population": 31},
            ],
            row_count=2,
        ),
        field_metadata=[
            FieldMetadata(name="okrug_name", data_type="string", semantic_role="dimension"),
            FieldMetadata(name="min_population", data_type="number", semantic_role="measure"),
            FieldMetadata(name="avg_population", data_type="number", semantic_role="measure"),
            FieldMetadata(name="max_population", data_type="number", semantic_role="measure"),
        ],
    )

    response = CpuVisualizationService().visualize(request)

    assert response.selected_view.type == "table"


def test_bar_uses_query_relevant_measure_not_first_numeric_column():
    request = VisualizationRequest(
        request_id="r1",
        user_query="Линии с более чем 15 станциями",
        data_source=DataSourceInfo(id="moscow_open"),
        result_table=ResultTable(
            columns=["line_id", "number", "name", "year_opened", "length_km", "station_count"],
            rows=[
                {"line_id": 1, "number": "1", "name": "Сокольническая", "year_opened": 1935, "length_km": 44.1, "station_count": 26},
                {"line_id": 2, "number": "2", "name": "Замоскворецкая", "year_opened": 1938, "length_km": 42.8, "station_count": 24},
                {"line_id": 3, "number": "3", "name": "Арбатско-Покровская", "year_opened": 1938, "length_km": 45.1, "station_count": 22},
            ],
            row_count=3,
        ),
        field_metadata=[
            FieldMetadata(name="line_id", data_type="number", semantic_role="id"),
            FieldMetadata(name="number", data_type="string", semantic_role="dimension"),
            FieldMetadata(name="name", data_type="string", semantic_role="dimension"),
            FieldMetadata(name="year_opened", data_type="number", semantic_role="time"),
            FieldMetadata(name="length_km", data_type="number", semantic_role="measure"),
            FieldMetadata(name="station_count", data_type="number", semantic_role="measure", allowed_aggregations=["none"], default_aggregation="none"),
        ],
    )

    response = CpuVisualizationService().visualize(request)

    assert response.selected_view.chart_type == "bar"
    assert response.selected_view.spec["encoding"]["x"]["field"] == "name"
    assert response.selected_view.spec["encoding"]["y"]["field"] == "station_count"


def test_area_chart_selected_for_explicit_area_time_series():
    request = VisualizationRequest(
        request_id="r1",
        user_query="Покажи областной график объема продаж по месяцам",
        data_source=DataSourceInfo(id="northwind_ru"),
        result_table=ResultTable(
            columns=["month", "revenue"],
            rows=[
                {"month": "2024-01", "revenue": 100},
                {"month": "2024-02", "revenue": 140},
                {"month": "2024-03", "revenue": 120},
            ],
            row_count=3,
        ),
        field_metadata=[
            FieldMetadata(name="month", data_type="date", semantic_role="time", allowed_aggregations=["none"], default_aggregation="none"),
            FieldMetadata(name="revenue", data_type="number", semantic_role="measure", allowed_aggregations=["none"], default_aggregation="none"),
        ],
    )

    response = CpuVisualizationService().visualize(request)

    assert response.selected_view.chart_type == "area"
    assert response.selected_view.spec["mark"]["type"] == "area"


def test_pie_chart_selected_for_small_part_to_whole():
    request = VisualizationRequest(
        request_id="r1",
        user_query="Покажи долю продаж по категориям круговой диаграммой",
        data_source=DataSourceInfo(id="northwind_ru"),
        result_table=ResultTable(
            columns=["category", "revenue"],
            rows=[
                {"category": "A", "revenue": 100},
                {"category": "B", "revenue": 80},
                {"category": "C", "revenue": 40},
            ],
            row_count=3,
        ),
        field_metadata=[
            FieldMetadata(name="category", data_type="string", semantic_role="dimension"),
            FieldMetadata(name="revenue", data_type="number", semantic_role="measure", allowed_aggregations=["none"], default_aggregation="none"),
        ],
    )

    response = CpuVisualizationService().visualize(request)

    assert response.selected_view.chart_type == "pie"
    assert response.selected_view.spec["mark"]["type"] == "arc"
    assert response.selected_view.spec["encoding"]["theta"]["field"] == "revenue"


def test_pie_chart_avoids_too_many_categories_and_uses_bar():
    rows = [{"category": f"C{i}", "revenue": i + 1} for i in range(10)]
    request = VisualizationRequest(
        request_id="r1",
        user_query="Покажи долю продаж по категориям",
        data_source=DataSourceInfo(id="northwind_ru"),
        result_table=ResultTable(columns=["category", "revenue"], rows=rows, row_count=len(rows)),
        field_metadata=[
            FieldMetadata(name="category", data_type="string", semantic_role="dimension"),
            FieldMetadata(name="revenue", data_type="number", semantic_role="measure", allowed_aggregations=["none"], default_aggregation="none"),
        ],
    )

    response = CpuVisualizationService().visualize(request)

    assert response.selected_view.chart_type == "bar"


def test_histogram_selected_for_numeric_distribution():
    request = VisualizationRequest(
        request_id="r1",
        user_query="Покажи распределение суммы заказов гистограммой",
        data_source=DataSourceInfo(id="northwind_ru"),
        result_table=ResultTable(
            columns=["order_amount"],
            rows=[{"order_amount": value} for value in [10, 12, 18, 21, 28, 35, 40, 55]],
            row_count=8,
        ),
        field_metadata=[
            FieldMetadata(name="order_amount", data_type="number", semantic_role="measure", allowed_aggregations=["none"], default_aggregation="none"),
        ],
    )

    response = CpuVisualizationService().visualize(request)

    assert response.selected_view.chart_type == "histogram"
    assert response.selected_view.spec["encoding"]["x"]["bin"]["maxbins"] == 20
    assert response.selected_view.spec["encoding"]["y"]["aggregate"] == "count"


def test_stacked_bar_selected_for_breakdown_by_two_categories():
    request = VisualizationRequest(
        request_id="r1",
        user_query="Покажи продажи по регионам с разбивкой по категориям",
        data_source=DataSourceInfo(id="northwind_ru"),
        result_table=ResultTable(
            columns=["region", "category", "revenue"],
            rows=[
                {"region": "North", "category": "A", "revenue": 100},
                {"region": "North", "category": "B", "revenue": 80},
                {"region": "South", "category": "A", "revenue": 90},
                {"region": "South", "category": "B", "revenue": 70},
            ],
            row_count=4,
        ),
        field_metadata=[
            FieldMetadata(name="region", data_type="string", semantic_role="dimension"),
            FieldMetadata(name="category", data_type="string", semantic_role="dimension"),
            FieldMetadata(name="revenue", data_type="number", semantic_role="measure", allowed_aggregations=["none"], default_aggregation="none"),
        ],
    )

    response = CpuVisualizationService().visualize(request)

    assert response.selected_view.chart_type == "stacked_bar"
    assert response.selected_view.spec["mark"] == "bar"
    assert response.selected_view.spec["encoding"]["color"]["field"] in {"region", "category"}
    assert response.selected_view.spec["encoding"]["y"]["stack"] == "zero"


def test_multi_line_selected_for_time_series_with_group():
    request = VisualizationRequest(
        request_id="r1",
        user_query="Покажи динамику продаж по месяцам в разрезе регионов",
        data_source=DataSourceInfo(id="northwind_ru"),
        result_table=ResultTable(
            columns=["month", "region", "revenue"],
            rows=[
                {"month": "2024-01", "region": "North", "revenue": 100},
                {"month": "2024-02", "region": "North", "revenue": 120},
                {"month": "2024-03", "region": "North", "revenue": 140},
                {"month": "2024-01", "region": "South", "revenue": 80},
                {"month": "2024-02", "region": "South", "revenue": 90},
                {"month": "2024-03", "region": "South", "revenue": 100},
            ],
            row_count=6,
        ),
        field_metadata=[
            FieldMetadata(name="month", data_type="date", semantic_role="time", allowed_aggregations=["none"], default_aggregation="none"),
            FieldMetadata(name="region", data_type="string", semantic_role="dimension"),
            FieldMetadata(name="revenue", data_type="number", semantic_role="measure", allowed_aggregations=["none"], default_aggregation="none"),
        ],
    )

    response = CpuVisualizationService().visualize(request)

    assert response.selected_view.chart_type == "multi_line"
    assert response.selected_view.spec["mark"] == {"type": "line", "point": True}
    assert response.selected_view.spec["encoding"]["color"]["field"] == "region"


def test_russian_monthly_breakdown_selects_multi_line_with_year_month_axis():
    request = VisualizationRequest(
        request_id="r1",
        user_query="Покажите ежемесячный доход в 2024 году в разбивке по каналам продаж",
        data_source=DataSourceInfo(id="northwind_ru"),
        result_table=ResultTable(
            columns=["год", "месяц", "сегмент", "доход"],
            rows=[
                {"год": 2024, "месяц": 1, "сегмент": "B2B", "доход": 680000},
                {"год": 2024, "месяц": 1, "сегмент": "HoReCa", "доход": 650000},
                {"год": 2024, "месяц": 2, "сегмент": "B2B", "доход": 740000},
                {"год": 2024, "месяц": 2, "сегмент": "HoReCa", "доход": 610000},
                {"год": 2024, "месяц": 3, "сегмент": "B2B", "доход": 810000},
                {"год": 2024, "месяц": 3, "сегмент": "HoReCa", "доход": 805000},
            ],
            row_count=6,
        ),
        field_metadata=[
            FieldMetadata(name="год", data_type="number", semantic_role="time", allowed_aggregations=["none"], default_aggregation="none"),
            FieldMetadata(name="месяц", data_type="number", semantic_role="time", allowed_aggregations=["none"], default_aggregation="none"),
            FieldMetadata(name="сегмент", data_type="string", semantic_role="dimension"),
            FieldMetadata(name="доход", data_type="number", semantic_role="measure", allowed_aggregations=["none"], default_aggregation="none"),
        ],
    )

    response = CpuVisualizationService().visualize(request)

    assert response.selected_view.chart_type == "multi_line"
    spec = response.selected_view.spec
    assert spec["mark"] == {"type": "line", "point": True}
    assert spec["encoding"]["x"]["field"] == "__period_month"
    assert spec["encoding"]["x"]["type"] == "temporal"
    assert spec["encoding"]["y"]["field"] == "доход"
    assert spec["encoding"]["color"]["field"] == "сегмент"


def test_heatmap_selected_for_two_factor_matrix():
    request = VisualizationRequest(
        request_id="r1",
        user_query="Построй тепловую карту продаж по дню недели и часу",
        data_source=DataSourceInfo(id="northwind_ru"),
        result_table=ResultTable(
            columns=["weekday", "hour", "orders_count"],
            rows=[
                {"weekday": "Mon", "hour": "09", "orders_count": 10},
                {"weekday": "Mon", "hour": "10", "orders_count": 15},
                {"weekday": "Tue", "hour": "09", "orders_count": 7},
                {"weekday": "Tue", "hour": "10", "orders_count": 11},
            ],
            row_count=4,
        ),
        field_metadata=[
            FieldMetadata(name="weekday", data_type="string", semantic_role="dimension"),
            FieldMetadata(name="hour", data_type="string", semantic_role="dimension"),
            FieldMetadata(name="orders_count", data_type="number", semantic_role="measure", allowed_aggregations=["none"], default_aggregation="none"),
        ],
    )

    response = CpuVisualizationService().visualize(request)

    assert response.selected_view.chart_type == "heatmap"
    assert response.selected_view.spec["mark"] == "rect"
    assert response.selected_view.spec["encoding"]["color"]["field"] == "orders_count"


def test_heatmap_respects_russian_explicit_x_y_axes():
    request = VisualizationRequest(
        request_id="r1",
        user_query=(
            "Мне нужен обзор активности студенческого клуба: сгруппируй мероприятия по месяцам и типам, "
            "посчитай количество мероприятий и покажи тепловую карту, где месяц по X, "
            "тип мероприятия по Y, а цвет показывает количество."
        ),
        data_source=DataSourceInfo(id="bird_student_club"),
        result_table=ResultTable(
            columns=["month", "type", "event_count"],
            rows=[
                {"month": "2019-09", "type": "Budget", "event_count": 1},
                {"month": "2019-09", "type": "Game", "event_count": 3},
                {"month": "2019-10", "type": "Budget", "event_count": 1},
                {"month": "2019-10", "type": "Meeting", "event_count": 2},
            ],
            row_count=4,
        ),
        field_metadata=[
            FieldMetadata(name="month", data_type="date", semantic_role="time", allowed_aggregations=["none"], default_aggregation="none"),
            FieldMetadata(name="type", data_type="string", semantic_role="dimension", allowed_aggregations=["none"], default_aggregation="none"),
            FieldMetadata(name="event_count", data_type="number", semantic_role="measure", allowed_aggregations=["none"], default_aggregation="none"),
        ],
    )

    response = CpuVisualizationService().visualize(request)

    assert response.selected_view.chart_type == "heatmap"
    spec = response.selected_view.spec
    assert spec["mark"] == "rect"
    assert spec["encoding"]["x"]["field"] == "month"
    assert spec["encoding"]["y"]["field"] == "type"
    assert spec["encoding"]["color"]["field"] == "event_count"


def test_heatmap_typo_with_axis_color_prompt_does_not_become_scatter():
    request = VisualizationRequest(
        request_id="r1",
        user_query=(
            "Мне нужен обзор активности студенческого клуба. Для этого сгруппируй мероприятия "
            "по месяцам и типам, затем посчитай количество мероприятий и покажи тепровую карту, "
            "где месяц по X, тип мероприятия по Y, а цвет показывает количество"
        ),
        data_source=DataSourceInfo(id="bird_student_club"),
        result_table=ResultTable(
            columns=["month", "type", "event_count"],
            rows=[
                {"month": "2019-09", "type": "Budget", "event_count": 1},
                {"month": "2019-09", "type": "Game", "event_count": 3},
                {"month": "2019-10", "type": "Budget", "event_count": 1},
                {"month": "2019-10", "type": "Meeting", "event_count": 2},
            ],
            row_count=4,
        ),
        field_metadata=[
            FieldMetadata(name="month", data_type="date", semantic_role="time", allowed_aggregations=["none"], default_aggregation="none"),
            FieldMetadata(name="type", data_type="string", semantic_role="dimension", allowed_aggregations=["none"], default_aggregation="none"),
            FieldMetadata(name="event_count", data_type="number", semantic_role="measure", allowed_aggregations=["none"], default_aggregation="none"),
        ],
    )

    response = CpuVisualizationService().visualize(request)

    assert response.selected_view.chart_type == "heatmap"
    spec = response.selected_view.spec
    assert spec["mark"] == "rect"
    assert spec["encoding"]["x"]["field"] == "month"
    assert spec["encoding"]["y"]["field"] == "type"
    assert spec["encoding"]["color"]["field"] == "event_count"


def test_boxplot_selected_for_grouped_raw_distribution():
    request = VisualizationRequest(
        request_id="r1",
        user_query="Покажи boxplot суммы заказов по регионам и выбросы",
        data_source=DataSourceInfo(id="northwind_ru"),
        result_table=ResultTable(
            columns=["region", "order_amount"],
            rows=[
                {"region": "North", "order_amount": 10},
                {"region": "North", "order_amount": 12},
                {"region": "North", "order_amount": 50},
                {"region": "South", "order_amount": 8},
                {"region": "South", "order_amount": 9},
                {"region": "South", "order_amount": 30},
            ],
            row_count=6,
        ),
        field_metadata=[
            FieldMetadata(name="region", data_type="string", semantic_role="dimension"),
            FieldMetadata(name="order_amount", data_type="number", semantic_role="measure", allowed_aggregations=["none"], default_aggregation="none"),
        ],
    )

    response = CpuVisualizationService().visualize(request)

    assert response.selected_view.chart_type == "boxplot"
    assert response.selected_view.spec["mark"]["type"] == "boxplot"
    assert response.selected_view.spec["encoding"]["y"]["field"] == "order_amount"
    assert "aggregate" not in response.selected_view.spec["encoding"]["y"]


def test_raw_boxplot_keeps_distribution_rows_beyond_table_preview_limit():
    rows = [
        {"segment": segment, "order_value": value}
        for segment in ["Corporate", "Loyalty", "Online-only", "Retail", "Wholesale"]
        for value in range(1, 31)
    ]
    table = ResultTable(
        columns=["segment", "order_value"],
        rows=rows,
        row_count=len(rows),
    )

    spec = chart_spec(
        chart_type="boxplot",
        title="Разброс значений",
        x_field=FieldMetadata(name="segment", data_type="string", semantic_role="dimension"),
        y_field=FieldMetadata(name="order_value", data_type="number", semantic_role="measure", default_aggregation="none"),
        table=table,
    )

    assert len(spec["data"]["values"]) == 150
    assert {row["segment"] for row in spec["data"]["values"]} == {
        "Corporate",
        "Loyalty",
        "Online-only",
        "Retail",
        "Wholesale",
    }


def test_unhashable_dimension_values_do_not_crash_category_count():
    request = VisualizationRequest(
        request_id="r1",
        user_query="Покажи boxplot стоимости доставки по сегментам клиентов",
        data_source=DataSourceInfo(id="northwind_ru"),
        result_table=ResultTable(
            columns=["сегмент", "стоимость_доставки"],
            rows=[
                {"сегмент": ["B2B"], "стоимость_доставки": 700},
                {"сегмент": ["B2B"], "стоимость_доставки": 1300},
                {"сегмент": ["Розница"], "стоимость_доставки": 900},
                {"сегмент": ["Розница"], "стоимость_доставки": 1600},
                {"сегмент": ["HoReCa"], "стоимость_доставки": 2200},
            ],
            row_count=5,
        ),
        field_metadata=[
            FieldMetadata(name="сегмент", data_type="string", semantic_role="dimension"),
            FieldMetadata(name="стоимость_доставки", data_type="number", semantic_role="measure", allowed_aggregations=["none"], default_aggregation="none"),
        ],
    )

    response = CpuVisualizationService().visualize(request)

    assert response.status in {"success", "partial_success"}
    assert response.selected_view.chart_type == "boxplot"


def test_precomputed_quartiles_by_group_render_as_boxplot_not_bar():
    request = VisualizationRequest(
        request_id="r1",
        user_query="Покажи ящик с усами стоимости заказов по сегментам клиентов",
        data_source=DataSourceInfo(id="northwind_ru"),
        result_table=ResultTable(
            columns=["сегмент", "q1", "median", "q3"],
            rows=[
                {"сегмент": "B2B", "q1": 940, "median": 1250, "q3": 1710},
                {"сегмент": "HoReCa", "q1": 760, "median": 1040, "q3": 1480},
                {"сегмент": "Розница", "q1": 520, "median": 720, "q3": 990},
            ],
            row_count=3,
        ),
        field_metadata=[
            FieldMetadata(name="сегмент", data_type="string", semantic_role="dimension"),
            FieldMetadata(name="q1", data_type="number", semantic_role="measure", allowed_aggregations=["none"], default_aggregation="none"),
            FieldMetadata(name="median", data_type="number", semantic_role="measure", allowed_aggregations=["none"], default_aggregation="none"),
            FieldMetadata(name="q3", data_type="number", semantic_role="measure", allowed_aggregations=["none"], default_aggregation="none"),
        ],
    )

    response = CpuVisualizationService().visualize(request)

    assert response.selected_view.chart_type == "boxplot"
    spec = response.selected_view.spec
    assert "layer" in spec
    assert spec["layer"][0]["mark"]["type"] == "bar"
    assert spec["layer"][0]["encoding"]["y"]["field"] == "q1"
    assert spec["layer"][0]["encoding"]["y2"]["field"] == "q3"
    assert spec["layer"][1]["mark"]["type"] == "tick"
    assert spec["layer"][1]["encoding"]["y"]["field"] == "median"


def test_spider2_quartiles_with_average_center_render_as_boxplot_not_bar():
    request = VisualizationRequest(
        request_id="r1",
        user_query="Покажи ящик с усами стоимости заказов по сегментам клиентов",
        data_source=DataSourceInfo(id="spider2_retail_dbt"),
        result_table=ResultTable(
            columns=[
                "segment",
                "min_order_value",
                "max_order_value",
                "avg_order_value",
                "q1_order_value",
                "q3_order_value",
            ],
            rows=[
                {
                    "segment": "Retail",
                    "min_order_value": 183980,
                    "max_order_value": 183980,
                    "avg_order_value": 183980,
                    "q1_order_value": 183980,
                    "q3_order_value": 183980,
                },
                {
                    "segment": "Wholesale",
                    "min_order_value": 264330,
                    "max_order_value": 264330,
                    "avg_order_value": 264330,
                    "q1_order_value": 264330,
                    "q3_order_value": 264330,
                },
                {
                    "segment": "Loyalty",
                    "min_order_value": 183160,
                    "max_order_value": 183160,
                    "avg_order_value": 183160,
                    "q1_order_value": 183160,
                    "q3_order_value": 183160,
                },
            ],
            row_count=3,
        ),
        field_metadata=[
            FieldMetadata(name="segment", data_type="string", semantic_role="dimension"),
            FieldMetadata(name="min_order_value", data_type="number", semantic_role="measure"),
            FieldMetadata(name="max_order_value", data_type="number", semantic_role="measure"),
            FieldMetadata(name="avg_order_value", data_type="number", semantic_role="measure"),
            FieldMetadata(name="q1_order_value", data_type="number", semantic_role="measure"),
            FieldMetadata(name="q3_order_value", data_type="number", semantic_role="measure"),
        ],
    )

    response = CpuVisualizationService().visualize(request)

    assert response.selected_view.chart_type == "boxplot"
    spec = response.selected_view.spec
    assert [layer["mark"]["type"] for layer in spec["layer"]] == ["rule", "bar", "tick"]
    assert spec["layer"][0]["encoding"]["y"]["field"] == "min_order_value"
    assert spec["layer"][0]["encoding"]["y2"]["field"] == "max_order_value"
    assert spec["layer"][1]["encoding"]["y"]["field"] == "q1_order_value"
    assert spec["layer"][1]["encoding"]["y2"]["field"] == "q3_order_value"
    assert spec["layer"][2]["encoding"]["y"]["field"] == "avg_order_value"


def test_preferred_new_chart_type_is_accepted_by_contract_and_service():
    request = VisualizationRequest(
        request_id="r1",
        user_query="Покажи распределение суммы заказов",
        data_source=DataSourceInfo(id="northwind_ru"),
        result_table=ResultTable(
            columns=["order_amount"],
            rows=[{"order_amount": value} for value in [10, 12, 18, 21, 28]],
            row_count=5,
        ),
        field_metadata=[
            FieldMetadata(name="order_amount", data_type="number", semantic_role="measure", allowed_aggregations=["none"], default_aggregation="none"),
        ],
        presentation_preferences=PresentationPreferences(preferred_chart_type="histogram"),
    )

    response = CpuVisualizationService().visualize(request)

    assert response.selected_view.chart_type == "histogram"


def test_empty_rows_failed_safely():
    request = VisualizationRequest(
        request_id="r1",
        user_query="Покажи пустой результат",
        data_source=DataSourceInfo(id="demo_concert_singer"),
        result_table=ResultTable(columns=["category", "revenue"], rows=[], row_count=0),
        field_metadata=[
            FieldMetadata(name="category", data_type="string", semantic_role="dimension"),
            FieldMetadata(name="revenue", data_type="number", semantic_role="measure"),
        ],
    )
    response = CpuVisualizationService().visualize(request)
    assert response.status == "failed"
    assert response.errors[0].code == "empty_result"


def test_derived_count_alias_does_not_add_vega_aggregate():
    table = ResultTable(
        columns=["Country", "NumberOfSingers"],
        rows=[{"Country": "France", "NumberOfSingers": 2}],
        row_count=1,
    )
    spec = chart_spec(
        chart_type="bar",
        title="Сравнение по категориям",
        x_field=FieldMetadata(name="Country", data_type="string", semantic_role="dimension"),
        y_field=FieldMetadata(
            name="NumberOfSingers",
            data_type="number",
            semantic_role="measure",
            default_aggregation="count",
            provenance=FieldProvenance(expression="*", aggregation="count", derived=True),
        ),
        table=table,
    )
    assert spec["encoding"]["y"]["field"] == "NumberOfSingers"
    assert "aggregate" not in spec["encoding"]["y"]


def test_raw_measure_can_still_use_vega_aggregate():
    table = ResultTable(
        columns=["Country", "Capacity"],
        rows=[{"Country": "France", "Capacity": 10}],
        row_count=1,
    )
    spec = chart_spec(
        chart_type="bar",
        title="Сравнение по категориям",
        x_field=FieldMetadata(name="Country", data_type="string", semantic_role="dimension"),
        y_field=FieldMetadata(
            name="Capacity",
            data_type="number",
            semantic_role="measure",
            default_aggregation="sum",
            provenance=FieldProvenance(expression="stadium.Capacity", aggregation=None, derived=False),
        ),
        table=table,
    )
    assert spec["encoding"]["y"]["aggregate"] == "sum"


def test_real_colab_like_category_count_alias_has_no_vega_aggregate():
    extraction = DataExtractionResponse(
        request_id="r1",
        status="success",
        user_query="Сравни количество певцов по странам",
        data_source=DataSourceInfo(id="demo_concert_singer", dialect="sqlite"),
        result_table=ResultTable(
            columns=["Country", "NumberOfSingers"],
            rows=[
                {"Country": "France", "NumberOfSingers": 2},
                {"Country": "United States", "NumberOfSingers": 1},
            ],
            row_count=2,
            truncated=False,
        ),
        field_metadata=[
            FieldMetadata(
                name="Country",
                data_type="string",
                semantic_role="dimension",
                allowed_aggregations=["count"],
                default_aggregation="count",
                provenance=FieldProvenance(expression=None, aggregation=None, derived=False),
            ),
            FieldMetadata(
                name="NumberOfSingers",
                data_type="number",
                semantic_role="measure",
                allowed_aggregations=["none"],
                default_aggregation="none",
                provenance=FieldProvenance(expression="*", aggregation="count", derived=True),
            ),
        ],
    )

    request = adapt_extraction_to_visualization(extraction).request
    response = CpuVisualizationService().visualize(request)

    assert response.selected_view.chart_type == "bar"
    y_encoding = response.selected_view.spec["encoding"]["y"]
    assert y_encoding["field"] == "NumberOfSingers"
    assert "aggregate" not in y_encoding
    assert response.explanation.used_aggregations == ["count"]
