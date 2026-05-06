import json
from pathlib import Path

from t2v_eval.data.nvbench_adapter import (
    create_smoke_nvbench_source,
    prepare_nvbench_dataset,
)
from t2v_eval.utils.io import read_jsonl


def test_prepare_nvbench_smoke_fixture(tmp_path: Path) -> None:
    drive_root = tmp_path / "drive"
    raw_root = drive_root / "datasets" / "raw" / "nvbench_fixture"
    create_smoke_nvbench_source(raw_root)

    result = prepare_nvbench_dataset(
        drive_root=drive_root,
        sample_size=3,
        min_successful=3,
        allow_download=False,
        seed=42,
    )

    assert result.status == "ok"
    assert result.successful_examples == 3
    assert result.candidate_examples == 3
    assert result.sampling_strategy == "stratified"
    assert result.output_jsonl is not None
    assert result.dataset_card is not None
    assert result.quality_report is not None

    rows = read_jsonl(result.output_jsonl)
    assert rows[0]["benchmark"] == "nvbench"
    assert rows[0]["benchmark_source"] == "TsinghuaDatabaseGroup/nvBench"
    assert rows[0]["query"]
    assert Path(rows[0]["table_path"]).exists()
    assert rows[0]["metadata"]["fields"]
    assert rows[0]["metadata"]["materialization_source"] == "gold_sql"
    assert rows[0]["metadata"]["chart_type_signal"] in {"none", "explicit_bar"}
    assert rows[0]["metadata"]["quality"]["status"] == "ok"
    assert rows[0]["metadata"]["table_shape"] == "1_dimension_1_measure"
    assert rows[0]["gold_spec"]["mark"] == "bar"
    assert rows[0]["gold_spec_normalized"]["encoding"]["x"]["field"] == "Rank"
    assert Path(result.quality_report).exists()


def test_prepare_nvbench_default_sampling_does_not_stop_at_first_n(tmp_path: Path) -> None:
    drive_root = tmp_path / "drive"
    raw_root = drive_root / "datasets" / "raw" / "nvbench_fixture"
    create_smoke_nvbench_source(raw_root)
    fixture_path = raw_root / "NVBench.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    fixture["9"] = {
        **fixture["8"],
        "nl_queries": ["Show faculty ranks as a line chart."],
        "chart": "Line",
        "vis_obj": {**fixture["8"]["vis_obj"], "chart": "line"},
    }
    fixture_path.write_text(json.dumps(fixture), encoding="utf-8")

    result = prepare_nvbench_dataset(
        drive_root=drive_root,
        sample_size=1,
        min_successful=1,
        allow_download=False,
        seed=1,
    )

    assert result.status == "ok"
    assert result.candidate_examples == 4
    assert result.successful_examples == 1
    rows = read_jsonl(result.output_jsonl)
    assert rows[0]["example_id"] != "nvbench_8_00"
    tables_dir = drive_root / "datasets" / "processed" / "nvbench_postquery" / "tables"
    assert len(list(tables_dir.glob("*.csv"))) == 1


def test_prepare_nvbench_blocks_without_source(tmp_path: Path) -> None:
    result = prepare_nvbench_dataset(
        drive_root=tmp_path / "empty_drive",
        sample_size=3,
        min_successful=3,
        allow_download=False,
    )

    assert result.status == "blocked"
    assert result.failure_reasons["nvbench_json_not_found"] == 1
