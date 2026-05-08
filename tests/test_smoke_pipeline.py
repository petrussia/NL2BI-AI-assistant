import t2v_eval
from t2v_eval.utils.io import read_jsonl, write_jsonl


def test_package_import_and_jsonl_roundtrip(tmp_path) -> None:
    path = tmp_path / "rows.jsonl"
    rows = [
        {"example_id": "a", "query": "show sales"},
        {"example_id": "b", "query": "show profit"},
    ]

    write_jsonl(path, rows)
    loaded = read_jsonl(path)

    assert t2v_eval.__version__
    assert loaded == rows
