"use client";

import { AlertCircle, BarChart3, Database, Info, Table2 } from "lucide-react";
import type { Artifact } from "@/lib/api";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) {
    return "";
  }
  if (typeof value === "number") {
    return new Intl.NumberFormat("ru-RU").format(value);
  }
  return String(value);
}

function TableArtifact({ artifact }: { artifact: Artifact }) {
  const rows = Array.isArray(artifact.payload.rows) ? (artifact.payload.rows as Record<string, unknown>[]) : [];
  const columns = Array.isArray(artifact.payload.columns) ? (artifact.payload.columns as string[]) : [];
  return (
    <div className="artifact">
      <div className="artifactHeader">
        <Table2 size={16} />
        <span>{artifact.title}</span>
      </div>
      <div className="tableWrap">
        <table>
          <thead>
            <tr>
              {columns.map((column) => (
                <th key={column}>{column}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.slice(0, 10).map((row, index) => (
              <tr key={index}>
                {columns.map((column) => (
                  <td key={column}>{formatValue(row[column])}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ChartArtifact({ artifact }: { artifact: Artifact }) {
  const spec = isRecord(artifact.payload.spec) ? artifact.payload.spec : {};
  const data = isRecord(spec.data) && Array.isArray(spec.data.values) ? (spec.data.values as Record<string, unknown>[]) : [];
  const encoding = isRecord(spec.encoding) ? spec.encoding : {};
  const x = isRecord(encoding.x) ? String(encoding.x.field ?? "") : "";
  const y = isRecord(encoding.y) ? String(encoding.y.field ?? "") : "";
  const values = data.map((row) => Number(row[y] ?? 0));
  const max = Math.max(...values, 1);
  const mark = String(spec.mark ?? "bar");

  return (
    <div className="artifact">
      <div className="artifactHeader">
        <BarChart3 size={16} />
        <span>{artifact.title}</span>
      </div>
      {mark === "line" ? (
        <svg className="chart" viewBox="0 0 640 220" role="img" aria-label={artifact.title}>
          <polyline
            points={values
              .map((value, index) => {
                const px = 40 + (index * 560) / Math.max(values.length - 1, 1);
                const py = 190 - (value / max) * 150;
                return `${px},${py}`;
              })
              .join(" ")}
            fill="none"
            stroke="#2563eb"
            strokeWidth="4"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          {values.map((value, index) => {
            const px = 40 + (index * 560) / Math.max(values.length - 1, 1);
            const py = 190 - (value / max) * 150;
            return <circle key={index} cx={px} cy={py} r="5" fill="#0f172a" />;
          })}
        </svg>
      ) : (
        <div className="bars">
          {data.map((row, index) => {
            const value = Number(row[y] ?? 0);
            return (
              <div className="barRow" key={index}>
                <span>{formatValue(row[x])}</span>
                <div className="barTrack">
                  <div className="barFill" style={{ width: `${Math.max(4, (value / max) * 100)}%` }} />
                </div>
                <strong>{formatValue(value)}</strong>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function NoticeArtifact({ artifact }: { artifact: Artifact }) {
  const isError = artifact.artifact_type === "error";
  const payload = artifact.payload as { message?: string; code?: string };
  return (
    <div className={isError ? "notice error" : "notice warning"}>
      {isError ? <AlertCircle size={16} /> : <Info size={16} />}
      <div>
        <strong>{payload.code ?? artifact.title}</strong>
        <p>{payload.message ?? artifact.title}</p>
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

