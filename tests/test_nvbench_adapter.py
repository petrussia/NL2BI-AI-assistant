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
    assert result.output_jsonl is not None
    assert result.dataset_card is not None

    rows = read_jsonl(result.output_jsonl)
    assert rows[0]["benchmark"] == "nvbench"
    assert rows[0]["benchmark_source"] == "TsinghuaDatabaseGroup/nvBench"
    assert rows[0]["query"]
    assert Path(rows[0]["table_path"]).exists()
    assert rows[0]["metadata"]["fields"]
    assert rows[0]["metadata"]["materialization_source"] == "gold_sql"
    assert rows[0]["gold_spec"]["mark"] == "bar"
    assert rows[0]["gold_spec_normalized"]["encoding"]["x"]["field"] == "Rank"


def test_prepare_nvbench_blocks_without_source(tmp_path: Path) -> None:
    result = prepare_nvbench_dataset(
        drive_root=tmp_path / "empty_drive",
        sample_size=3,
        min_successful=3,
        allow_download=False,
    )

    assert result.status == "blocked"
    assert result.failure_reasons["nvbench_json_not_found"] == 1
