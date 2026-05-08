import pandas as pd

from t2v_eval.data.quality import (
    acceptable_marks,
    build_quality_metadata,
    detect_chart_type_signal,
    is_pie_or_arc_example,
    select_examples,
)


def test_detect_chart_type_signal_distinguishes_explicit_and_implicit() -> None:
    explicit = detect_chart_type_signal("Create a pie chart of faculty ranks.")
    implicit = detect_chart_type_signal("Show faculty ranks and counts. Show the proportion.")

    assert explicit["chart_type_mentioned"] is True
    assert explicit["chart_type_signal"] == "explicit_pie"
    assert implicit["chart_type_mentioned"] is False
    assert implicit["chart_type_signal"] == "proportion"


def test_acceptable_marks_excludes_arc_from_relaxed_marks() -> None:
    assert acceptable_marks("arc", "proportion") == []
    assert acceptable_marks("arc", "explicit_pie") == []
    assert acceptable_marks("bar", "none") == ["bar"]


def test_pie_or_arc_examples_are_flagged_as_unsupported() -> None:
    assert is_pie_or_arc_example(
        {
            "primary_mark": "arc",
            "chart_type_signal": "proportion",
            "mentioned_chart_type": None,
            "chart": "Pie",
            "acceptable_marks": ["bar"],
        }
    )
    assert is_pie_or_arc_example(
        {
            "primary_mark": "bar",
            "chart_type_signal": "explicit_pie",
            "mentioned_chart_type": "pie",
            "chart": "Bar",
            "acceptable_marks": ["bar"],
        }
    )
    assert not is_pie_or_arc_example(
        {
            "primary_mark": "bar",
            "chart_type_signal": "explicit_bar",
            "mentioned_chart_type": "bar",
            "chart": "Bar",
            "acceptable_marks": ["bar"],
        }
    )


def test_quality_metadata_validates_fields_and_table(tmp_path) -> None:
    df = pd.DataFrame({"Rank": ["Professor"], "count_rank": [2]})
    table_path = tmp_path / "table.csv"
    df.to_csv(table_path, index=False)
    metadata = {
        "fields": [
            {"name": "Rank", "dtype": "string", "role": "dimension"},
            {"name": "count_rank", "dtype": "integer", "role": "measure"},
        ]
    }
    gold_spec = {
        "mark": "arc",
        "encoding": {
            "theta": {"field": "count_rank", "type": "quantitative"},
            "color": {"field": "Rank", "type": "nominal"},
        },
    }

    quality = build_quality_metadata(
        query="Show the proportion of faculty ranks.",
        metadata=metadata,
        gold_spec=gold_spec,
        df=df,
        table_path=table_path,
    )

    assert quality["quality"]["status"] == "ok"
    assert quality["chart_type_signal"] == "proportion"
    assert quality["acceptable_marks"] == []
    assert quality["table_shape"] == "1_dimension_1_measure"


def test_stratified_sampling_is_seeded_and_not_first_n() -> None:
    examples = [
        _example("first", "bar", True, "db1"),
        _example("second", "bar", True, "db1"),
        _example("third", "arc", False, "db2"),
        _example("fourth", "point", True, "db3"),
    ]

    sampled = select_examples(examples, sample_size=2, strategy="stratified", seed=7)

    assert [item["example_id"] for item in sampled] != ["first", "second"]
    assert sampled == select_examples(examples, sample_size=2, strategy="stratified", seed=7)


def _example(example_id: str, mark: str, explicit: bool, db_id: str) -> dict:
    return {
        "example_id": example_id,
        "metadata": {
            "primary_mark": mark,
            "chart_type_mentioned": explicit,
            "db_id": db_id,
        },
        "gold_spec": {"mark": mark},
    }
