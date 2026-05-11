from __future__ import annotations

import time
from typing import Any

from contracts.common import ErrorItem, WarningItem
from contracts.extraction import (
    DataExtractionRequest,
    DataExtractionResponse,
    DataSourceInfo,
    ExecutionInfo,
    QualityInfo,
    ResultTable,
    SqlInfo,
)
from colab.config import ColabServerConfig, resolve_data_source
from colab.db_engine import dialect_label


def _engine_to_dialect(engine: str) -> str:
    """Map our internal engine names to the canonical Dialect Literal."""
    return {"postgres": "postgresql", "sqlite": "sqlite", "duckdb": "duckdb"}.get(engine, "unknown")
from colab.errors import SAFE_USER_MESSAGES, ExtractionErrorCode
from colab.metadata import infer_field_metadata
from colab.model import TextToSqlModel
from colab.plan import build_plan
from colab.schema_loader import DatabaseSchema, load_schema
from colab.sql_guard import (
    apply_row_limit,
    extract_sql,
    repair_sql_for_empty_result,
    repair_sql_for_execution,
    validate_select_only,
)
from colab.sql_runner import execute_select


def _empty_data_source_info(req: DataExtractionRequest) -> DataSourceInfo:
    return DataSourceInfo(
        id=req.data_source.id,
        dialect=req.data_source.dialect,
        schema_version=req.data_source.schema_version,
    )


def _failed_response(
    req: DataExtractionRequest,
    code: ExtractionErrorCode,
    *,
    message: str | None = None,
    retryable: bool = False,
    details: dict[str, Any] | None = None,
    warnings: list[WarningItem] | None = None,
    sql: SqlInfo | None = None,
    plan_partial: bool = False,
) -> DataExtractionResponse:
    return DataExtractionResponse(
        request_id=req.request_id,
        status="failed",
        user_query=req.user_query,
        data_source=_empty_data_source_info(req),
        sql=sql or SqlInfo(query=None, dialect=req.data_source.dialect or "sqlite", validated=False, read_only=True),
        execution=ExecutionInfo(
            latency_ms=None,
            row_limit=req.constraints.row_limit,
            timeout_ms=req.constraints.timeout_ms,
            executable=False,
        ),
        quality=QualityInfo(confidence=None, warnings=[]),
        errors=[
            ErrorItem(
                code=code.value,
                message=message or SAFE_USER_MESSAGES[code],
                source="colab",
                retryable=retryable,
                details=details or {},
            )
        ],
        warnings=warnings or [],
    )


def run_extraction(
    request: DataExtractionRequest,
    config: ColabServerConfig,
    model: TextToSqlModel,
    planner: TextToSqlModel | None = None,
) -> DataExtractionResponse:
    started = time.monotonic()

    if not model.is_ready():
        return _failed_response(
            request,
            ExtractionErrorCode.MODEL_NOT_LOADED,
            retryable=True,
            details={"model_id": config.model_id, "load_error": model.state.load_error},
        )

    spec = resolve_data_source(config, request.data_source.id)
    if spec is None:
        return _failed_response(
            request,
            ExtractionErrorCode.SCHEMA_NOT_FOUND,
            retryable=False,
            details={"data_source_id": request.data_source.id},
        )
    # For sqlite/duckdb, verify the file exists upfront — surfaces a
    # clearer error than the engine's "open failed".
    if spec.engine in ("sqlite", "duckdb") and (spec.path is None or not spec.path.exists()):
        return _failed_response(
            request,
            ExtractionErrorCode.SCHEMA_NOT_FOUND,
            retryable=False,
            details={"data_source_id": request.data_source.id, "engine": spec.engine, "path": str(spec.path)},
        )

    try:
        schema: DatabaseSchema = load_schema(
            spec,
            data_source_id=request.data_source.id,
            schema_version=request.data_source.schema_version,
        )
    except Exception as exc:
        return _failed_response(
            request,
            ExtractionErrorCode.SCHEMA_NOT_FOUND,
            retryable=False,
            details={"data_source_id": request.data_source.id, "engine": spec.engine, "error": str(exc)[:200]},
        )

    # Two-stage planner→emitter path is used whenever a planner instance
    # was passed in AND it's ready. Otherwise fall back to single-shot
    # anchor mode (current Qwen2.5-Coder-7B path).
    plan_text: str | None = None
    try:
        if planner is not None and planner.is_ready():
            try:
                plan_text = planner.generate_plan(
                    request.user_query, schema, locale=request.locale,
                )
            except Exception:
                plan_text = None
        if plan_text:
            raw_output = model.generate_sql_with_plan(
                request.user_query, schema, plan_text, locale=request.locale,
            )
        else:
            raw_output = model.generate_sql(
                request.user_query, schema, locale=request.locale,
            )
    except Exception as exc:
        return _failed_response(
            request,
            ExtractionErrorCode.SQL_GENERATION_FAILED,
            retryable=True,
            details={"error_type": type(exc).__name__},
        )

    candidate_sql = extract_sql(raw_output)
    guard = validate_select_only(candidate_sql)
    if not guard.ok:
        return _failed_response(
            request,
            ExtractionErrorCode.SQL_VALIDATION_FAILED,
            retryable=True,
            details={"reason": guard.reason},
            sql=SqlInfo(query=candidate_sql or None, dialect=_engine_to_dialect(spec.engine), validated=False, read_only=True),
        )

    bounded_sql, limit_added = apply_row_limit(guard.sql, request.constraints.row_limit)
    sql_info = SqlInfo(query=bounded_sql, dialect=_engine_to_dialect(spec.engine), validated=True, read_only=True)

    exec_result = execute_select(
        spec,
        bounded_sql,
        timeout_ms=request.constraints.timeout_ms,
        row_limit=request.constraints.row_limit,
        read_only=True,
    )

    def _execute_repair_candidate(repair_output: str | None):
        if not repair_output:
            return None
        repaired_sql = extract_sql(repair_output)
        repaired_guard = validate_select_only(repaired_sql)
        if not repaired_guard.ok:
            return None
        repaired_bounded_sql, _ = apply_row_limit(repaired_guard.sql, request.constraints.row_limit)
        repaired_sql_info = SqlInfo(
            query=repaired_bounded_sql,
            dialect=_engine_to_dialect(spec.engine),
            validated=True,
            read_only=True,
        )
        repaired_exec_result = execute_select(
            spec,
            repaired_bounded_sql,
            timeout_ms=request.constraints.timeout_ms,
            row_limit=request.constraints.row_limit,
            read_only=True,
        )
        return repaired_bounded_sql, repaired_sql_info, repaired_exec_result

    if request.constraints.allow_llm_repair and exec_result.error is not None:
        base_sql = bounded_sql
        base_error = exec_result.error
        repaired_sql = repair_sql_for_execution(
            base_sql,
            engine=spec.engine,
            data_source_id=spec.id,
            user_query=request.user_query,
            error=base_error,
            schema=schema,
        )
        deterministic_attempt = _execute_repair_candidate(repaired_sql)
        if deterministic_attempt is not None:
            cand_sql, cand_sql_info, cand_exec = deterministic_attempt
            if cand_exec.error is None and not cand_exec.timed_out:
                bounded_sql, sql_info, exec_result = cand_sql, cand_sql_info, cand_exec
            else:
                base_sql = cand_sql
                base_error = cand_exec.error or base_error

        if exec_result.error is not None:
            llm_repair_output = model.repair_sql(
                request.user_query,
                schema,
                base_sql,
                f"Database execution error:\n{base_error}",
                locale=request.locale,
            )
            llm_attempt = _execute_repair_candidate(llm_repair_output)
            if llm_attempt is not None:
                cand_sql, cand_sql_info, cand_exec = llm_attempt
                if cand_exec.error is None and not cand_exec.timed_out:
                    bounded_sql, sql_info, exec_result = cand_sql, cand_sql_info, cand_exec

    if (
        request.constraints.allow_llm_repair
        and exec_result.error is None
        and not exec_result.timed_out
        and exec_result.row_count == 0
    ):
        empty_repair_sql = repair_sql_for_empty_result(
            bounded_sql,
            engine=spec.engine,
            data_source_id=spec.id,
            user_query=request.user_query,
            schema=schema,
        )
        empty_attempt = _execute_repair_candidate(empty_repair_sql)
        if empty_attempt is not None:
            cand_sql, cand_sql_info, cand_exec = empty_attempt
            if cand_exec.error is None and not cand_exec.timed_out and cand_exec.row_count > 0:
                bounded_sql, sql_info, exec_result = cand_sql, cand_sql_info, cand_exec

    if (
        request.constraints.allow_llm_repair
        and exec_result.error is None
        and not exec_result.timed_out
        and exec_result.row_count == 0
    ):
        llm_repair_output = model.repair_sql(
            request.user_query,
            schema,
            bounded_sql,
            (
                "The SQL executed successfully but returned zero rows. "
                "If this is caused by an impossible filter or wrong join path, repair it. "
                "Preserve the original analytical intent."
            ),
            locale=request.locale,
        )
        llm_attempt = _execute_repair_candidate(llm_repair_output)
        if llm_attempt is not None:
            cand_sql, cand_sql_info, cand_exec = llm_attempt
            if cand_exec.error is None and not cand_exec.timed_out and cand_exec.row_count > 0:
                bounded_sql, sql_info, exec_result = cand_sql, cand_sql_info, cand_exec

    if exec_result.timed_out:
        return _failed_response(
            request,
            ExtractionErrorCode.TIMEOUT,
            retryable=True,
            details={"timeout_ms": request.constraints.timeout_ms},
            sql=sql_info,
        )
    if exec_result.error is not None:
        return _failed_response(
            request,
            ExtractionErrorCode.SQL_EXECUTION_FAILED,
            retryable=False,
            details={"sqlite_error": exec_result.error[:200]},
            sql=sql_info,
        )

    field_metadata, metadata_warnings = infer_field_metadata(
        exec_result.columns,
        exec_result.column_sql_types,
        exec_result.rows,
        bounded_sql,
        schema,
    )
    plan = build_plan(bounded_sql, exec_result.columns)

    warnings: list[WarningItem] = []
    if exec_result.truncated:
        warnings.append(
            WarningItem(
                code=ExtractionErrorCode.ROW_LIMIT_EXCEEDED.value,
                message=SAFE_USER_MESSAGES[ExtractionErrorCode.ROW_LIMIT_EXCEEDED],
                source="colab",
                details={"row_limit": request.constraints.row_limit},
            )
        )
    if exec_result.row_count == 0:
        warnings.append(
            WarningItem(
                code=ExtractionErrorCode.EMPTY_RESULT.value,
                message=SAFE_USER_MESSAGES[ExtractionErrorCode.EMPTY_RESULT],
                source="colab",
            )
        )
    for code in metadata_warnings:
        warnings.append(
            WarningItem(
                code=code,
                message=SAFE_USER_MESSAGES[ExtractionErrorCode(code)],
                source="colab",
            )
        )

    status = "success"
    if exec_result.row_count == 0 or any(
        w.code == ExtractionErrorCode.METADATA_INCOMPLETE.value for w in warnings
    ):
        status = "partial_success"

    overall_latency = int((time.monotonic() - started) * 1000)

    return DataExtractionResponse(
        request_id=request.request_id,
        status=status,
        user_query=request.user_query,
        normalized_query=None,
        data_source=DataSourceInfo(
            id=request.data_source.id,
            name=spec.name,
            dialect=_engine_to_dialect(spec.engine),
            schema_version=schema.schema_version or request.data_source.schema_version,
        ),
        plan=plan,
        sql=sql_info,
        result_table=ResultTable(
            format="records",
            columns=exec_result.columns,
            rows=exec_result.rows,
            uri=None,
            row_count=exec_result.row_count,
            truncated=exec_result.truncated,
        ),
        field_metadata=field_metadata,
        execution=ExecutionInfo(
            latency_ms=max(overall_latency, exec_result.latency_ms),
            row_limit=request.constraints.row_limit,
            timeout_ms=request.constraints.timeout_ms,
            executable=True,
        ),
        quality=QualityInfo(
            confidence=None,
            warnings=[w.code for w in warnings],
        ),
        errors=[],
        warnings=warnings,
    )
