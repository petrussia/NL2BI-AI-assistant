"use client";

import { useState } from "react";
import { Check, ClipboardCopy, Download, RotateCcw } from "lucide-react";
import type { Artifact } from "@/lib/api";
import { labelFor } from "@/lib/demo-schema";

type Props = {
  artifacts: Artifact[];
  onRegenerate?: () => void;
  regenerateDisabled?: boolean;
};

function findTable(artifacts: Artifact[]): Artifact | null {
  return artifacts.find((a) => a.artifact_type === "table") ?? null;
}

function findSql(artifacts: Artifact[]): string | null {
  // Prefer debug_sql artifact if exposed; otherwise check chart_spec / table
  // payloads for an attached sql string (none currently — kept for forward
  // compat). Returns null when SQL is not available to the client.
  const dbg = artifacts.find((a) => a.artifact_type === "debug_sql");
  if (dbg && typeof dbg.payload?.sql === "string") return dbg.payload.sql as string;
  return null;
}

function rowsToCsv(columns: string[], rows: Record<string, unknown>[]): string {
  const esc = (v: unknown) => {
    if (v === null || v === undefined) return "";
    const s = typeof v === "string" ? v : String(v);
    if (/[",\n]/.test(s)) return `"${s.replace(/"/g, '""')}"`;
    return s;
  };
  // CSV headers use the same Russian labels the on-screen table shows.
  // Excel's «cp1251 default» reads our UTF-8 fine because we prepend a BOM
  // at download time (see onCsv).
  const head = columns.map((c) => esc(labelFor(c))).join(",");
  const body = rows.map((r) => columns.map((c) => esc(r[c])).join(",")).join("\n");
  return `${head}\n${body}\n`;
}

function downloadBlob(name: string, mime: string, text: string) {
  const blob = new Blob([text], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 500);
}

export function MessageActions({ artifacts, onRegenerate, regenerateDisabled }: Props) {
  const [copyState, setCopyState] = useState<"idle" | "ok">("idle");
  const sql = findSql(artifacts);
  const table = findTable(artifacts);
  const tableRows = (table?.payload.rows as Record<string, unknown>[] | undefined) ?? [];
  const tableCols = (table?.payload.columns as string[] | undefined) ?? [];
  const canCsv = tableCols.length > 0 && tableRows.length > 0;

  async function onCopy() {
    if (!sql) return;
    try {
      await navigator.clipboard.writeText(sql);
      setCopyState("ok");
      setTimeout(() => setCopyState("idle"), 1500);
    } catch {
      // ignore — older browsers without clipboard
    }
  }

  function onCsv() {
    if (!canCsv) return;
    // BOM so Excel on Windows treats the file as UTF-8.
    const csv = "﻿" + rowsToCsv(tableCols, tableRows);
    downloadBlob(`nl2bi-${Date.now()}.csv`, "text/csv;charset=utf-8", csv);
  }

  return (
    <div className="messageActions">
      {onRegenerate ? (
        <button
          type="button"
          className="messageAction"
          onClick={onRegenerate}
          disabled={regenerateDisabled}
          title="Повторить тот же запрос"
        >
          <RotateCcw size={13} />
          Перезапустить
        </button>
      ) : null}
      {sql ? (
        <button
          type="button"
          className="messageAction"
          onClick={onCopy}
          title="Скопировать сгенерированный SQL"
        >
          {copyState === "ok" ? <Check size={13} /> : <ClipboardCopy size={13} />}
          {copyState === "ok" ? "Скопировано" : "Copy SQL"}
        </button>
      ) : null}
      {canCsv ? (
        <button
          type="button"
          className="messageAction"
          onClick={onCsv}
          title="Скачать таблицу в CSV (UTF-8, с запятой-разделителем)"
        >
          <Download size={13} />
          CSV
        </button>
      ) : null}
    </div>
  );
}
