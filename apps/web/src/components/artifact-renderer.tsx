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

function NoticeArtifact({ artifact }: { artifact: Artifact }) {
  const isError = artifact.artifact_type === "error";
  const payload = artifact.payload as { message?: string; code?: string; details?: Record<string, unknown> };
  const detailEntries = payload.details ? Object.entries(payload.details) : [];
  return (
    <div className={isError ? "notice error" : "notice warning"}>
      {isError ? <AlertCircle size={16} /> : <Info size={16} />}
      <div>
        <strong>{payload.code ?? artifact.title}</strong>
        <p>{payload.message ?? artifact.title}</p>
        {detailEntries.length > 0 ? (
          <ul className="noticeDetails">
            {detailEntries.map(([k, v]) => (
              <li key={k}>
                <code>{k}</code>: {typeof v === "string" ? v : JSON.stringify(v)}
              </li>
            ))}
          </ul>
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

export function ArtifactRenderer({ artifact }: { artifact: Artifact }) {
  if (artifact.artifact_type === "table") {
    return <TableArtifact artifact={artifact} />;
  }
  if (artifact.artifact_type === "chart_spec") {
    return <ChartArtifact artifact={artifact} />;
  }
  if (artifact.artifact_type === "warning" || artifact.artifact_type === "error") {
    return <NoticeArtifact artifact={artifact} />;
  }
  if (artifact.artifact_type === "debug_sql") {
    return <DebugSqlArtifact artifact={artifact} />;
  }
  return null;
}
