"""nvBench adapter for post-query Text-to-Visualization experiments.

The adapter never generates SQL. If nvBench SQL is available, it is used only as
gold materialization to produce an input table. If databases are unavailable or
the query fails, the adapter can fall back to the benchmark's `vis_obj` data,
which already stores gold visualization values.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import time
import urllib.request
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from t2v_eval.data.schema import FieldMetadata, T2VExample
from t2v_eval.utils.io import write_json, write_jsonl
from t2v_eval.utils.reproducibility import git_sha, runtime_info, set_seed


OFFICIAL_REPO_URL = "https://github.com/TsinghuaDatabaseGroup/nvBench.git"
OFFICIAL_ARCHIVE_URL = (
    "https://github.com/TsinghuaDatabaseGroup/nvBench/archive/refs/heads/main.zip"
)
CANONICAL_DRIVE_ROOT = Path(
    "/content/drive/MyDrive/diploma/petr_text_to_visualization_part"
)


@dataclass(slots=True)
class NVBenchPaths:
    drive_root: Path
    raw_dir: Path
    processed_dir: Path
    tables_dir: Path
    failures_dir: Path
    nvbench_root: Path | None = None
    json_path: Path | None = None


@dataclass(slots=True)
class NVBenchPrepareResult:
    status: str
    requested_sample_size: int | None
    total_visualizations_seen: int = 0
    total_nl_pairs_seen: int = 0
    successful_examples: int = 0
    failed_visualizations: int = 0
    output_jsonl: str | None = None
    dataset_card: str | None = None
    source_root: str | None = None
    official_download_attempted: bool = False
    failure_reasons: dict[str, int] = field(default_factory=dict)
    elapsed_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def default_drive_root() -> Path:
    return Path(os.environ.get("T2V_DRIVE_ROOT", str(CANONICAL_DRIVE_ROOT)))


def build_paths(drive_root: Path | str | None = None) -> NVBenchPaths:
    root = Path(drive_root) if drive_root is not None else default_drive_root()
    processed = root / "datasets" / "processed" / "nvbench_postquery"
    return NVBenchPaths(
        drive_root=root,
        raw_dir=root / "datasets" / "raw",
        processed_dir=processed,
        tables_dir=processed / "tables",
        failures_dir=processed / "failures",
    )


def find_nvbench_json(search_roots: Iterable[Path]) -> Path | None:
    candidates: list[Path] = []
    for root in search_roots:
        if not root.exists():
            continue
        for pattern in ("NVBench.json", "nvBench.json", "nvbench.json"):
            candidates.extend(root.rglob(pattern))
    if not candidates:
        return None
    return sorted(candidates, key=lambda path: (len(path.parts), str(path).lower()))[0]


def locate_nvbench(paths: NVBenchPaths) -> NVBenchPaths:
    json_path = find_nvbench_json(
        [
            paths.raw_dir,
            paths.drive_root / "benchmarks",
            paths.drive_root,
        ]
    )
    if json_path is None:
        return paths
    paths.json_path = json_path
    paths.nvbench_root = json_path.parent
    return paths


def _download_archive(destination: Path) -> None:
    archive = destination / "nvbench_main.zip"
    urllib.request.urlretrieve(OFFICIAL_ARCHIVE_URL, archive)
    with zipfile.ZipFile(archive) as zf:
        zf.extractall(destination)


def ensure_nvbench_source(paths: NVBenchPaths, *, allow_download: bool = True) -> tuple[NVBenchPaths, bool]:
    paths.raw_dir.mkdir(parents=True, exist_ok=True)
    paths = locate_nvbench(paths)
    if paths.json_path is not None:
        return paths, False
    if not allow_download:
        return paths, False

    target = paths.raw_dir / "nvbench_official"
    if target.exists() and not any(target.iterdir()):
        target.rmdir()
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            subprocess.run(
                ["git", "clone", "--depth", "1", OFFICIAL_REPO_URL, str(target)],
                check=True,
                text=True,
                capture_output=True,
            )
        except (OSError, subprocess.CalledProcessError):
            target.mkdir(parents=True, exist_ok=True)
            _download_archive(target)

    paths = locate_nvbench(paths)
    return paths, True


def extract_databases_if_needed(nvbench_root: Path) -> None:
    database_dirs = [
        nvbench_root / "database",
        nvbench_root / "databases",
    ]
    if any(path.exists() for path in database_dirs):
        return

    for archive in nvbench_root.rglob("databases.zip"):
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(nvbench_root)
        return


def load_nvbench_objects(json_path: Path) -> list[tuple[str, dict[str, Any]]]:
    data = json.loads(json_path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        return [(str(key), value) for key, value in data.items() if isinstance(value, dict)]
    if isinstance(data, list):
        rows: list[tuple[str, dict[str, Any]]] = []
        for index, value in enumerate(data):
            if not isinstance(value, dict):
                continue
            key = str(value.get("key") or value.get("id") or index)
            rows.append((key, value))
        return rows
    raise ValueError(f"Unsupported nvBench JSON root type: {type(data).__name__}")


def extract_sql(record: dict[str, Any]) -> str | None:
    vis_query = record.get("vis_query") or {}
    if isinstance(vis_query, dict):
        data_part = vis_query.get("data_part") or {}
        if isinstance(data_part, dict):
            sql = data_part.get("sql_part") or data_part.get("sql")
            if sql:
                return str(sql)
        for key in ("sql_part", "sql", "query"):
            if vis_query.get(key):
                return str(vis_query[key])
    for key in ("sql", "query_sql", "gold_sql"):
        if record.get(key):
            return str(record[key])
    return None


def nl_queries(record: dict[str, Any]) -> list[str]:
    queries = record.get("nl_queries") or record.get("questions") or record.get("utterances")
    if isinstance(queries, list):
        return [str(item) for item in queries if str(item).strip()]
    for key in ("nl_query", "question", "query", "utterance"):
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return [value]
    return []


def find_sqlite_path(nvbench_root: Path, db_id: str) -> Path | None:
    if not db_id:
        return None
    names = [f"{db_id}.sqlite", f"{db_id}.db"]
    roots = [
        nvbench_root,
        nvbench_root / "database",
        nvbench_root / "databases",
    ]
    for root in roots:
        if not root.exists():
            continue
        for name in names:
            direct_candidates = [
                root / db_id / name,
                root / name,
            ]
            for candidate in direct_candidates:
                if candidate.exists():
                    return candidate
        for suffix in ("*.sqlite", "*.db"):
            for candidate in root.rglob(suffix):
                if candidate.stem.lower() == db_id.lower():
                    return candidate
    return None


def dataframe_from_sql(sqlite_path: Path, sql: str) -> pd.DataFrame:
    with sqlite3.connect(sqlite_path) as connection:
        return pd.read_sql_query(sql, connection)


def _first_list(value: Any) -> list[Any]:
    if isinstance(value, list) and value and isinstance(value[0], list):
        return list(value[0])
    if isinstance(value, list):
        return list(value)
    return []


def dataframe_from_vis_obj(vis_obj: dict[str, Any]) -> pd.DataFrame:
    x_name = str(vis_obj.get("x_name") or "x")
    y_name = str(vis_obj.get("y_name") or "y")
    classify_name = str(vis_obj.get("classify_name") or "classify")
    x_series = vis_obj.get("x_data") or []
    y_series = vis_obj.get("y_data") or []
    classify = vis_obj.get("classify") or []

    rows: list[dict[str, Any]] = []
    if (
        isinstance(x_series, list)
        and isinstance(y_series, list)
        and x_series
        and y_series
        and isinstance(x_series[0], list)
        and isinstance(y_series[0], list)
    ):
        for series_index, (xs, ys) in enumerate(zip(x_series, y_series)):
            label = None
            if isinstance(classify, list) and series_index < len(classify):
                label = classify[series_index]
            for x_value, y_value in zip(xs, ys):
                row = {x_name: x_value, y_name: y_value}
                if label is not None:
                    row[classify_name] = label
                rows.append(row)
    else:
        for x_value, y_value in zip(_first_list(x_series), _first_list(y_series)):
            rows.append({x_name: x_value, y_name: y_value})

    if not rows:
        raise ValueError("vis_obj does not contain usable x/y data")
    return pd.DataFrame(rows)


def infer_role(dtype: str, name: str) -> str:
    lowered = name.lower()
    if "date" in lowered or "time" in lowered or "year" in lowered or "month" in lowered:
        return "time"
    if dtype in {"integer", "number"}:
        return "measure"
    if lowered.endswith("_id") or lowered == "id":
        return "id"
    return "dimension"


def pandas_dtype_to_t2v(dtype: Any) -> str:
    if pd.api.types.is_datetime64_any_dtype(dtype):
        return "datetime"
    if pd.api.types.is_integer_dtype(dtype):
        return "integer"
    if pd.api.types.is_numeric_dtype(dtype):
        return "number"
    if pd.api.types.is_bool_dtype(dtype):
        return "boolean"
    return "string"


def metadata_from_dataframe(df: pd.DataFrame) -> dict[str, Any]:
    fields = []
    for column in df.columns:
        dtype = pandas_dtype_to_t2v(df[column].dtype)
        role = infer_role(dtype, str(column))
        allowed = ["sum", "mean", "min", "max"] if role == "measure" else []
        fields.append(
            FieldMetadata(
                name=str(column),
                dtype=dtype,
                role=role,  # type: ignore[arg-type]
                allowed_aggregations=allowed,
            ).to_dict()
        )
    return {"fields": fields}


def chart_to_mark(chart: str | None) -> str:
    normalized = (chart or "").strip().lower().replace("_", " ")
    mapping = {
        "bar": "bar",
        "stacked bar": "bar",
        "pie": "arc",
        "line": "line",
        "grouping line": "line",
        "scatter": "point",
        "grouping scatter": "point",
    }
    return mapping.get(normalized, normalized or "bar")


def channel_type(field: str, metadata: dict[str, Any]) -> str:
    for item in metadata.get("fields", []):
        if item.get("name") == field:
            dtype = item.get("dtype")
            role = item.get("role")
            if role == "time" or dtype == "datetime":
                return "temporal"
            if role == "measure" or dtype in {"number", "integer"}:
                return "quantitative"
            return "nominal"
    return "nominal"


def make_gold_spec(record: dict[str, Any], df: pd.DataFrame, metadata: dict[str, Any]) -> dict[str, Any]:
    vis_obj = record.get("vis_obj") or {}
    chart = record.get("chart") or vis_obj.get("chart")
    mark = chart_to_mark(str(chart) if chart is not None else None)
    fields = [str(column) for column in df.columns]
    x_field = str(vis_obj.get("x_name") or (fields[0] if fields else "x"))
    y_field = str(vis_obj.get("y_name") or (fields[1] if len(fields) > 1 else fields[0]))
    if x_field not in fields and fields:
        x_field = fields[0]
    if y_field not in fields and len(fields) > 1:
        y_field = fields[1]

    spec: dict[str, Any] = {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "mark": mark,
        "encoding": {
            "x": {"field": x_field, "type": channel_type(x_field, metadata)},
            "y": {"field": y_field, "type": channel_type(y_field, metadata)},
        },
    }
    classify_field = None
    for candidate in ("classify", "series", "category"):
        if candidate in fields:
            classify_field = candidate
            break
    if classify_field is None and len(fields) > 2:
        classify_field = fields[2]
    chart_lower = str(chart).lower()
    if classify_field and ("grouping" in chart_lower or chart_lower == "stacked bar"):
        spec["encoding"]["color"] = {
            "field": classify_field,
            "type": channel_type(classify_field, metadata),
        }
    if mark == "arc":
        spec["encoding"] = {
            "theta": {"field": y_field, "type": channel_type(y_field, metadata)},
            "color": {"field": x_field, "type": channel_type(x_field, metadata)},
        }
    return spec


def normalize_gold_spec(spec: dict[str, Any]) -> dict[str, Any]:
    encoding = spec.get("encoding") or {}
    normalized_encoding = {}
    for channel, definition in encoding.items():
        if isinstance(definition, dict):
            normalized_encoding[channel] = {
                key: definition[key]
                for key in ("field", "type", "aggregate", "bin", "timeUnit", "sort")
                if key in definition
            }
    return {
        "mark": spec.get("mark", "bar"),
        "encoding": normalized_encoding,
    }


def safe_id(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in value)


def materialize_record(
    *,
    key: str,
    record: dict[str, Any],
    nvbench_root: Path,
    tables_dir: Path,
) -> tuple[pd.DataFrame, Path, str]:
    db_id = str(record.get("db_id") or "")
    sql = extract_sql(record)
    sqlite_path = find_sqlite_path(nvbench_root, db_id)
    source = "vis_obj"
    if sql and sqlite_path is not None:
        try:
            df = dataframe_from_sql(sqlite_path, sql)
            source = "gold_sql"
        except Exception:
            vis_obj = record.get("vis_obj") or {}
            df = dataframe_from_vis_obj(vis_obj)
            source = "vis_obj_after_sql_failure"
    else:
        vis_obj = record.get("vis_obj") or {}
        df = dataframe_from_vis_obj(vis_obj)

    if df.empty:
        raise ValueError("materialized table is empty")
    table_path = tables_dir / f"{safe_id(key)}.csv"
    tables_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(table_path, index=False)
    return df, table_path, source


def prepare_nvbench_dataset(
    *,
    drive_root: Path | str | None = None,
    sample_size: int | None = None,
    allow_download: bool = True,
    min_successful: int = 50,
    seed: int = 42,
) -> NVBenchPrepareResult:
    started = time.time()
    set_seed(seed)
    paths = build_paths(drive_root)
    paths.processed_dir.mkdir(parents=True, exist_ok=True)
    paths.tables_dir.mkdir(parents=True, exist_ok=True)
    paths.failures_dir.mkdir(parents=True, exist_ok=True)

    paths, downloaded = ensure_nvbench_source(paths, allow_download=allow_download)
    if paths.json_path is None or paths.nvbench_root is None:
        result = NVBenchPrepareResult(
            status="blocked",
            requested_sample_size=sample_size,
            official_download_attempted=downloaded,
            failure_reasons={"nvbench_json_not_found": 1},
            elapsed_seconds=round(time.time() - started, 3),
        )
        write_json(paths.processed_dir / "prepare_result.json", result.to_dict())
        return result

    extract_databases_if_needed(paths.nvbench_root)
    objects = load_nvbench_objects(paths.json_path)
    output_name = f"examples_sample{sample_size}.jsonl" if sample_size else "examples_all.jsonl"
    output_jsonl = paths.processed_dir / output_name
    latest_jsonl = paths.processed_dir / "examples.jsonl"
    failures_path = paths.failures_dir / f"failures_sample{sample_size or 'all'}.jsonl"

    examples: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    failure_reasons: dict[str, int] = {}
    nl_seen = 0

    for key, record in objects:
        queries = nl_queries(record)
        if not queries:
            reason = "missing_nl_queries"
            failure_reasons[reason] = failure_reasons.get(reason, 0) + 1
            failures.append({"key": key, "reason": reason})
            continue
        try:
            df, table_path, materialization_source = materialize_record(
                key=key,
                record=record,
                nvbench_root=paths.nvbench_root,
                tables_dir=paths.tables_dir,
            )
        except Exception as exc:
            reason = type(exc).__name__
            failure_reasons[reason] = failure_reasons.get(reason, 0) + 1
            failures.append({"key": key, "reason": reason, "error": str(exc)})
            continue

        metadata = metadata_from_dataframe(df)
        gold_spec = make_gold_spec(record, df, metadata)
        normalized = normalize_gold_spec(gold_spec)
        for query_index, query in enumerate(queries):
            nl_seen += 1
            example_id = f"nvbench_{safe_id(key)}_{query_index:02d}"
            example = T2VExample(
                example_id=example_id,
                benchmark="nvbench",
                benchmark_source="TsinghuaDatabaseGroup/nvBench",
                query=query,
                table_path=str(table_path),
                metadata={
                    **metadata,
                    "db_id": record.get("db_id"),
                    "chart": record.get("chart"),
                    "materialization_source": materialization_source,
                    "source_key": key,
                },
                gold_spec=gold_spec,
                gold_spec_normalized=normalized,
            )
            examples.append(example.to_dict())
            if sample_size is not None and len(examples) >= sample_size:
                break
        if sample_size is not None and len(examples) >= sample_size:
            break

    write_jsonl(output_jsonl, examples)
    write_jsonl(latest_jsonl, examples)
    write_jsonl(failures_path, failures)

    result = NVBenchPrepareResult(
        status="ok" if len(examples) >= min_successful else "blocked",
        requested_sample_size=sample_size,
        total_visualizations_seen=len(objects),
        total_nl_pairs_seen=nl_seen,
        successful_examples=len(examples),
        failed_visualizations=len(failures),
        output_jsonl=str(output_jsonl),
        dataset_card=str(paths.processed_dir / "dataset_card.md"),
        source_root=str(paths.nvbench_root),
        official_download_attempted=downloaded,
        failure_reasons=failure_reasons,
        elapsed_seconds=round(time.time() - started, 3),
    )
    write_dataset_card(paths, result, failures_path)
    write_json(paths.processed_dir / "prepare_result.json", result.to_dict())
    write_json(
        paths.processed_dir / "runtime_info.json",
        {
            "git_sha": git_sha(Path.cwd()),
            "runtime": runtime_info(Path.cwd()),
            "seed": seed,
            "official_repo": OFFICIAL_REPO_URL,
        },
    )
    return result


def write_dataset_card(paths: NVBenchPaths, result: NVBenchPrepareResult, failures_path: Path) -> None:
    lines = [
        "# nvBench post-query dataset card",
        "",
        f"Source: `{OFFICIAL_REPO_URL}`",
        f"Source root: `{result.source_root}`",
        f"Processed root: `{paths.processed_dir}`",
        "",
        "## Counts",
        "",
        f"- Requested sample size: `{result.requested_sample_size}`",
        f"- Visualizations seen: `{result.total_visualizations_seen}`",
        f"- NL pairs seen during preparation: `{result.total_nl_pairs_seen}`",
        f"- Successful post-query examples: `{result.successful_examples}`",
        f"- Failed visualizations: `{result.failed_visualizations}`",
        "",
        "## Post-query boundary",
        "",
        "Gold SQL from nvBench is used only to materialize an input table when the SQLite database is available.",
        "No Text-to-SQL generation or evaluation is performed.",
        "When SQL materialization is unavailable, the adapter can use `vis_obj` gold values as a table extraction fallback.",
        "",
        "## Outputs",
        "",
        f"- Examples JSONL: `{result.output_jsonl}`",
        f"- Latest examples alias: `{paths.processed_dir / 'examples.jsonl'}`",
        f"- Tables directory: `{paths.tables_dir}`",
        f"- Failures JSONL: `{failures_path}`",
        "",
        "## Failure reasons",
        "",
    ]
    if result.failure_reasons:
        for reason, count in sorted(result.failure_reasons.items()):
            lines.append(f"- `{reason}`: {count}")
    else:
        lines.append("- none recorded")
    (paths.processed_dir / "dataset_card.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def create_smoke_nvbench_source(root: Path) -> Path:
    """Create a tiny nvBench-like fixture for unit tests only."""

    root.mkdir(parents=True, exist_ok=True)
    db_dir = root / "database" / "activity_1"
    db_dir.mkdir(parents=True, exist_ok=True)
    sqlite_path = db_dir / "activity_1.sqlite"
    with sqlite3.connect(sqlite_path) as connection:
        connection.execute("CREATE TABLE Faculty (Rank TEXT)")
        connection.executemany(
            "INSERT INTO Faculty (Rank) VALUES (?)",
            [("Professor",), ("Professor",), ("Instructor",), ("AsstProf",)],
        )
        connection.commit()
    data = {
        "8": {
            "vis_query": {
                "data_part": {
                    "sql_part": "SELECT Rank, COUNT(Rank) as count_rank FROM Faculty GROUP BY Rank"
                }
            },
            "chart": "Bar",
            "hardness": "Easy",
            "db_id": "activity_1",
            "vis_obj": {
                "chart": "bar",
                "x_name": "Rank",
                "y_name": "count_rank",
                "x_data": [["AsstProf", "Instructor", "Professor"]],
                "y_data": [[1, 1, 2]],
                "classify": [],
            },
            "nl_queries": [
                "Show the number of faculty by rank.",
                "Create a bar chart of faculty count by rank.",
                "How many faculty members are in each rank?",
            ],
        }
    }
    (root / "NVBench.json").write_text(json.dumps(data), encoding="utf-8")
    return root


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--drive-root", type=Path, default=default_drive_root())
    parser.add_argument("--sample-size", type=int, default=None)
    parser.add_argument("--min-successful", type=int, default=50)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--no-download", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = prepare_nvbench_dataset(
        drive_root=args.drive_root,
        sample_size=args.sample_size,
        allow_download=not args.no_download,
        min_successful=args.min_successful,
        seed=args.seed,
    )
    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(f"status={result.status}")
        print(f"successful_examples={result.successful_examples}")
        print(f"output_jsonl={result.output_jsonl}")
        print(f"dataset_card={result.dataset_card}")
    return 0 if result.status == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
