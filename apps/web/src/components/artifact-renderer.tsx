"use client";

import { useMemo, useState } from "react";
import { AlertCircle, BarChart3, ChevronDown, ChevronRight, Database, Info, Table2 } from "lucide-react";
import type { Artifact } from "@/lib/api";
import { VegaChart } from "@/components/vega-chart";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function formatValue(value: unknown): { text: string; numeric: boolean } {
  if (value === null || value === undefined) {
    return { text: "—", numeric: false };
  }
  if (typeof value === "number") {
    return { text: new Intl.NumberFormat("ru-RU").format(value), numeric: true };
  }
  if (typeof value === "boolean") {
    return { text: value ? "да" : "нет", numeric: false };
  }
  return { text: String(value), numeric: false };
}

function inferNumericColumns(
  columns: string[],
  rows: Record<string, unknown>[],
): Set<string> {
  const numeric = new Set<string>();
  for (const col of columns) {
    let hadValue = false;
    let allNumeric = true;
    for (let i = 0; i < Math.min(rows.length, 20); i += 1) {
      const v = rows[i]?.[col];
      if (v === null || v === undefined) continue;
      hadValue = true;
      if (typeof v !== "number") {
        allNumeric = false;
        break;
      }
    }
    if (hadValue && allNumeric) numeric.add(col);
  }
  return numeric;
}

const TABLE_PREVIEW_ROWS = 25;

function TableArtifact({ artifact }: { artifact: Artifact }) {
  const rows = useMemo(
    () => (Array.isArray(artifact.payload.rows) ? (artifact.payload.rows as Record<string, unknown>[]) : []),
    [artifact],
  );
  const columns = useMemo(
    () => (Array.isArray(artifact.payload.columns) ? (artifact.payload.columns as string[]) : []),
    [artifact],
  );
  const numericCols = useMemo(() => inferNumericColumns(columns, rows), [columns, rows]);
  const [expanded, setExpanded] = useState(false);

  const totalRows = rows.length;
  const shown = expanded ? rows : rows.slice(0, TABLE_PREVIEW_ROWS);
  const hidden = Math.max(0, totalRows - shown.length);

  return (
    <div className="artifact tableArtifact">
      <div className="artifactHeader">
        <Table2 size={16} />
        <span>{artifact.title}</span>
        <span className="artifactBadge">{totalRows.toLocaleString("ru-RU")} строк</span>
      </div>
      <div className="tableWrap">
        <table>
          <thead>
            <tr>
              {columns.map((column) => (
                <th key={column} className={numericCols.has(column) ? "numeric" : undefined}>
                  {column}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {shown.map((row, index) => (
              <tr key={index}>
                {columns.map((column) => {
                  const { text, numeric } = formatValue(row[column]);
                  return (
                    <td
                      key={column}
                      className={numeric || numericCols.has(column) ? "numeric" : undefined}
                      title={text}
                    >
                      {text}
                    </td>
                  );
                })}
              </tr>
            ))}
            {totalRows === 0 ? (
              <tr>
                <td colSpan={Math.max(columns.length, 1)} className="emptyRow">
                  Пустой результат
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
      {hidden > 0 ? (
        <button
          type="button"
          className="tableMoreToggle"
          onClick={() => setExpanded((prev) => !prev)}
        >
          {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          {expanded ? "Скрыть остальные" : `Показать ещё ${hidden.toLocaleString("ru-RU")}`}
        </button>
      ) : null}
    </div>
  );
}

function ChartArtifact({ artifact }: { artifact: Artifact }) {
  const spec = useMemo(() => {
    const raw = artifact.payload.spec;
    return isRecord(raw) ? (raw as Record<string, unknown>) : null;
  }, [artifact]);

  return (
    <div className="artifact chartArtifact">
      <div className="artifactHeader">
        <BarChart3 size={16} />
        <span>{artifact.title}</span>
      </div>
      <VegaChart spec={spec} title={artifact.title} />
    </div>
  );
}

// Friendly Russian message for common error codes, used in Business mode
// where raw sqlite_error / stack-shaped details would feel like a system
// crash to a non-technical reviewer.
const FRIENDLY_ERROR_RU: Record<string, string> = {
  sql_execution_failed:
    "В текущем источнике данных нет таблиц или колонок, нужных для этого запроса. Попробуйте один из готовых запросов под схемой или переформулируйте.",
  schema_not_found:
    "Не удалось найти схему выбранного источника данных. Переключитесь на другой источник из списка.",
  sql_validation_failed:
    "Сгенерированный SQL не прошёл проверку безопасности. Попробуйте переформулировать запрос.",
  sql_generation_failed:
    "Модель не смогла сформировать SQL по этому запросу. Попробуйте сформулировать конкретнее.",
  timeout: "Запрос выполнялся слишком долго и был остановлен.",
  empty_result: "Запрос корректный, но не вернул данных.",
  row_limit_exceeded: "Результат превысил лимит строк — показана только часть данных.",
  metadata_incomplete: "Не удалось определить полные метаданные для всех колонок результата.",
  colab_unavailable: "Сервис генерации SQL временно недоступен. Попробуйте позже.",
  extraction_timeout: "Сервис генерации SQL не ответил вовремя.",
  invalid_extraction_response: "Сервис генерации SQL вернул некорректный ответ.",
};

function NoticeArtifact({ artifact, technical }: { artifact: Artifact; technical: boolean }) {
  const isError = artifact.artifact_type === "error";
  const payload = artifact.payload as { message?: string; code?: string; details?: Record<string, unknown> };
  const code = payload.code ?? artifact.title;
  const friendly = (typeof code === "string" ? FRIENDLY_ERROR_RU[code] : undefined) ?? payload.message ?? artifact.title;
  const detailEntries = payload.details ? Object.entries(payload.details) : [];
  return (
    <div className={isError ? "notice error" : "notice warning"}>
      {isError ? <AlertCircle size={16} /> : <Info size={16} />}
      <div>
        <strong>
          {technical ? (typeof code === "string" ? code : artifact.title) : isError ? "Не удалось получить данные" : "Внимание"}
        </strong>
        <p>{friendly}</p>
        {technical && detailEntries.length > 0 ? (
          <ul className="noticeDetails">
            {detailEntries.map(([k, v]) => (
              <li key={k}>
                <code>{k}</code>: {typeof v === "string" ? v : JSON.stringify(v)}
              </li>
            ))}
          </ul>
        ) : null}
        {technical && payload.message && payload.message !== friendly ? (
          <p className="noticeRawMessage">{payload.message}</p>
        ) : null}
      </div>
    </div>
  );
}

function DebugSqlArtifact({ artifact }: { artifact: Artifact }) {
  return (
    <div className="artifact debug">
      <div className="artifactHeader">
        <Database size={16} />
        <span>{artifact.title}</span>
      </div>
      <pre>{String(artifact.payload.sql ?? "")}</pre>
    </div>
  );
}

export function ArtifactRenderer({
  artifact,
  technical = false,
}: {
  artifact: Artifact;
  technical?: boolean;
}) {
  if (artifact.artifact_type === "table") {
    return <TableArtifact artifact={artifact} />;
  }
  if (artifact.artifact_type === "chart_spec") {
    return <ChartArtifact artifact={artifact} />;
  }
  if (artifact.artifact_type === "warning" || artifact.artifact_type === "error") {
    return <NoticeArtifact artifact={artifact} technical={technical} />;
  }
  if (artifact.artifact_type === "debug_sql") {
    // SQL artifact is technical-only: in Business mode hide it entirely.
    if (!technical) return null;
    return <DebugSqlArtifact artifact={artifact} />;
  }
  return null;
}
