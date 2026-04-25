from t2v_eval.data.schema import FieldMetadata, T2VExample, T2VPrediction


def test_t2v_example_roundtrip() -> None:
    field = FieldMetadata(
        name="sales",
        dtype="number",
        role="measure",
        description="Total sales",
        unit="USD",
        allowed_aggregations=["sum", "mean"],
    )
    example = T2VExample(
        example_id="sample_001",
        benchmark="unit",
        query="Show sales by month",
        table_path="datasets/samples/sample_001.csv",
        metadata={"fields": [field.to_dict()]},
        gold_spec={"mark": "bar"},
        gold_spec_normalized={"mark": "bar"},
    )

    restored = T2VExample.from_dict(example.to_dict())

    assert restored.example_id == "sample_001"
    assert restored.query == "Show sales by month"
    assert restored.fields[0].name == "sales"
    assert restored.fields[0].allowed_aggregations == ["sum", "mean"]


def test_failed_prediction_factory() -> None:
    prediction = T2VPrediction.failed(
        run_id="run_001",
        method="B0_rule_based",
        example_id="sample_001",
        error="no compatible fields",
    )

    assert prediction.status == "failed"
    assert prediction.error == "no compatible fields"
    assert prediction.to_dict()["method"] == "B0_rule_based"
