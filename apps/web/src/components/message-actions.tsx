"use client";

import { useState } from "react";
import { Check, ClipboardCopy, Download, FileJson, ImageDown, RotateCcw } from "lucide-react";
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

function downloadBlob(name: string, mime: string, body: BlobPart) {
  const blob = body instanceof Blob ? body : new Blob([body], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 500);
}

// Find the Vega SVG that belongs to this message — walk up from the button
// to the .message wrapper, then look inside for .vegaChart svg. Returns
// null if the artifact didn't render or the message has no chart.
function chartSvgFor(button: Element): SVGSVGElement | null {
  const msg = button.closest(".message");
  if (!msg) return null;
  return msg.querySelector(".vegaChart svg") as SVGSVGElement | null;
}

function svgToString(svg: SVGSVGElement): string {
  const clone = svg.cloneNode(true) as SVGSVGElement;
  // Ensure xmlns attributes survive standalone viewing.
  clone.setAttribute("xmlns", "http://www.w3.org/2000/svg");
  if (!clone.getAttribute("xmlns:xlink")) {
    clone.setAttribute("xmlns:xlink", "http://www.w3.org/1999/xlink");
  }
  return new XMLSerializer().serializeToString(clone);
}

function svgToPng(svg: SVGSVGElement, scale = 2): Promise<Blob> {
  // Rasterize the live SVG via an Image + Canvas. Scale up so the PNG
  // looks sharp on retina; users typically want a deck-ready export.
  return new Promise((resolve, reject) => {
    const svgText = svgToString(svg);
    const svgBlob = new Blob([svgText], { type: "image/svg+xml;charset=utf-8" });
    const url = URL.createObjectURL(svgBlob);
    const img = new Image();
    img.onload = () => {
      const rect = svg.getBoundingClientRect();
      const w = Math.max(1, Math.round(rect.width * scale));
      const h = Math.max(1, Math.round(rect.height * scale));
      const canvas = document.createElement("canvas");
      canvas.width = w;
      canvas.height = h;
      const ctx = canvas.getContext("2d");
      if (!ctx) {
        URL.revokeObjectURL(url);
        return reject(new Error("canvas 2D context unavailable"));
      }
      ctx.fillStyle = "#ffffff";
      ctx.fillRect(0, 0, w, h);
      ctx.drawImage(img, 0, 0, w, h);
      URL.revokeObjectURL(url);
      canvas.toBlob((blob) => {
        if (blob) resolve(blob);
        else reject(new Error("toBlob returned null"));
      }, "image/png");
    };
    img.onerror = (e) => {
      URL.revokeObjectURL(url);
      reject(new Error("svg rasterize failed: " + String(e)));
    };
    img.src = url;
  });
}

function findChart(artifacts: Artifact[]): Artifact | null {
  return artifacts.find((a) => a.artifact_type === "chart_spec" || a.artifact_type === "chart_image") ?? null;
}

export function MessageActions({ artifacts, onRegenerate, regenerateDisabled }: Props) {
  const [copyState, setCopyState] = useState<"idle" | "ok">("idle");
  const [chartErr, setChartErr] = useState<string | null>(null);
  const sql = findSql(artifacts);
  const table = findTable(artifacts);
  const chart = findChart(artifacts);
  const tableRows = (table?.payload.rows as Record<string, unknown>[] | undefined) ?? [];
  const tableCols = (table?.payload.columns as string[] | undefined) ?? [];
  const canCsv = tableCols.length > 0 && tableRows.length > 0;
  const canJson = canCsv;
  const canChart = !!chart;

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

  function onJson() {
    if (!canJson) return;
    const payload = {
      columns: tableCols.map((c) => ({ id: c, label: labelFor(c) })),
      rows: tableRows,
      exported_at: new Date().toISOString(),
    };
    downloadBlob(
      `nl2bi-${Date.now()}.json`,
      "application/json;charset=utf-8",
      JSON.stringify(payload, null, 2),
    );
  }

  function onChartSvg(e: React.MouseEvent<HTMLButtonElement>) {
    const svg = chartSvgFor(e.currentTarget);
    if (!svg) {
      setChartErr("Не нашёл график в этом сообщении");
      return;
    }
    setChartErr(null);
    downloadBlob(`nl2bi-${Date.now()}.svg`, "image/svg+xml;charset=utf-8", svgToString(svg));
  }

  async function onChartPng(e: React.MouseEvent<HTMLButtonElement>) {
    const svg = chartSvgFor(e.currentTarget);
    if (!svg) {
      setChartErr("Не нашёл график в этом сообщении");
      return;
    }
    try {
      setChartErr(null);
      const blob = await svgToPng(svg, 2);
      downloadBlob(`nl2bi-${Date.now()}.png`, "image/png", blob);
    } catch (err) {
      setChartErr(err instanceof Error ? err.message : "PNG export failed");
    }
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
      {canJson ? (
        <button
          type="button"
          className="messageAction"
          onClick={onJson}
          title="Скачать таблицу в JSON (колонки + строки)"
        >
          <FileJson size={13} />
          JSON
        </button>
      ) : null}
      {canChart ? (
        <button
          type="button"
          className="messageAction"
          onClick={onChartPng}
          title="Скачать график как PNG (2x retina, белый фон)"
        >
          <ImageDown size={13} />
          PNG
        </button>
      ) : null}
      {canChart ? (
        <button
          type="button"
          className="messageAction"
          onClick={onChartSvg}
          title="Скачать график как SVG (векторный исходник Vega-Lite)"
        >
          <Download size={13} />
          SVG
        </button>
      ) : null}
      {chartErr ? <span className="messageActionsError">{chartErr}</span> : null}
    </div>
  );
}
