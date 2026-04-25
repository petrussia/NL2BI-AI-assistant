from t2v_eval.normalization.vega_lite import canonical_json, normalize_spec


def test_normalize_spec_canonicalizes_key_order() -> None:
    left = {
        "mark": {"type": "Bar"},
        "encoding": {
            "y": {"type": "quantitative", "field": "sales", "aggregate": "sum"},
            "x": {"field": "region", "type": "nominal"},
        },
    }
    right = {
        "encoding": {
            "x": {"type": "nominal", "field": "region"},
            "y": {"aggregate": "sum", "field": "sales", "type": "quantitative"},
        },
        "mark": "bar",
    }

    normalized_left = normalize_spec(left)
    normalized_right = normalize_spec(right)

    assert normalized_left["valid"]
    assert normalized_left["chart_type"] == "bar"
    assert normalized_left["canonical_json"] == normalized_right["canonical_json"]
    assert normalized_left["fields"] == ["region", "sales"]


def test_normalize_invalid_spec_returns_error_without_exception() -> None:
    normalized = normalize_spec({"encoding": {"x": {"field": "region"}}})

    assert normalized["valid"] is False
    assert normalized["error"] == "missing_mark"
    assert canonical_json({"a": 1, "b": 2}) == '{"a":1,"b":2}'


def test_normalize_extracts_transform_fields() -> None:
    normalized = normalize_spec(
        {
            "mark": "line",
            "encoding": {"x": "month:T", "y": {"field": "sales", "type": "Q"}},
            "transform": [
                {"filter": {"field": "region", "equal": "West"}},
                {"aggregate": [{"op": "sum", "field": "sales", "as": "total_sales"}]},
            ],
        }
    )

    assert normalized["valid"]
    assert set(normalized["fields"]) == {"month", "region", "sales"}
    assert len(normalized["transform"]) == 2
