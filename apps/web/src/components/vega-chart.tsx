"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Loader2 } from "lucide-react";
import { labelFor } from "@/lib/demo-schema";

type Spec = Record<string, unknown>;

// Walk a vega-lite encoding object and replace `title: field` defaults with
// human-readable Russian labels from demo-schema.COLUMN_LABELS_RU. Mutates
// the supplied spec subtree in place but only assigns absent / SQL-id-shaped
// titles — won't trample a real user-provided title.
// Match year-like column names so Vega axis doesn't render "2 014.00" with
// thousand-separator + decimals. Same regex used in the table renderer.
const YEAR_FIELD_RE = /(^|_)year$|^year_|^год$|_год$/i;

function humanizeEncoding(spec: Spec): void {
  const encoding = (spec.encoding as Record<string, unknown> | undefined) ?? undefined;
  if (!encoding) return;
  for (const channel of ["x", "y", "color", "size", "shape"]) {
    const ch = encoding[channel];
    if (!ch || typeof ch !== "object") continue;
    const obj = ch as Record<string, unknown>;
    const field = typeof obj.field === "string" ? obj.field : "";
    if (!field) continue;
    const currentTitle = typeof obj.title === "string" ? obj.title : "";
    // Replace when title is empty, equals the field, or is the bare snake/camel id.
    if (!currentTitle || currentTitle === field) {
      obj.title = labelFor(field);
    }
    // Years: cast quantitative integers to ordinal so the axis prints
    // 2014, 2015, ... instead of 2,014.00, 2,014.50, ...
    if (YEAR_FIELD_RE.test(field) && obj.type === "quantitative") {
      obj.type = "ordinal";
    }
  }
}

// Dynamic import keeps vega-embed (~600 KB) out of the SSR bundle and away
// from `window`-touching code in Next's server runtime.
export function VegaChart({ spec, title }: { spec: Spec | null; title: string }) {
  const ref = useRef<HTMLDivElement | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  // Memoize the enriched spec so the effect doesn't re-mount the chart on
  // every parent render.
  const enriched = useMemo<Spec | null>(() => {
    if (!spec) return null;
    const clone = JSON.parse(JSON.stringify(spec)) as Spec;
    humanizeEncoding(clone);
    return {
      ...clone,
      // Auto-size to the container, with sensible padding and a readable theme.
      width: "container",
      autosize: { type: "fit-x", contains: "padding" },
      background: "transparent",
      config: {
        font:
          'ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
        axis: {
          labelColor: "#475569",
          titleColor: "#0f172a",
          gridColor: "#e2e8f0",
          domainColor: "#cbd5e1",
          tickColor: "#cbd5e1",
          labelFontSize: 12,
          titleFontSize: 13,
          titlePadding: 8,
          // Horizontal labels by default — Vega auto-rotates short
          // category names to vertical which is annoying to read.
          labelAngle: 0,
        },
        axisY: {
          // Y-axis title runs vertical by default. Force horizontal so
          // "Средний возраст" doesn't read like a chimney.
          titleAngle: 0,
          titleAlign: "left",
          titleAnchor: "start",
          titleX: -8,
          titleY: -10,
          titleBaseline: "bottom",
        },
        axisX: {
          // Keep x-axis label rotation only when names would overlap.
          // labelAngle inherited from axis: 0 (above) — Vega will still
          // ellipsize long names via labelLimit.
          labelLimit: 120,
        },
        legend: {
          labelColor: "#475569",
          titleColor: "#0f172a",
          symbolStrokeWidth: 1.5,
        },
        title: {
          color: "#0f172a",
          fontSize: 14,
          fontWeight: 600,
          anchor: "start",
          offset: 8,
        },
        bar: { color: "#2563eb", cornerRadiusEnd: 4, tooltip: true },
        line: { color: "#2563eb", strokeWidth: 2.5, tooltip: true, point: true },
        point: { color: "#1e3a8a", filled: true, size: 60 },
        rect: { tooltip: true },
        view: { stroke: "transparent" },
      },
    };
  }, [spec]);

  useEffect(() => {
    let cancelled = false;
    let view: { finalize?: () => void } | null = null;

    if (!ref.current || !enriched) {
      setLoading(false);
      return;
    }

    (async () => {
      try {
        const mod = await import("vega-embed");
        if (cancelled || !ref.current) return;
        const result = await mod.default(ref.current, enriched, {
          // Hide vega's three-dot actions menu — it confused users on the
          // demo (looked like a broken column of black circles when sized
          // by stretched CSS, and exposed Save SVG/PNG/View Source which
          // we don't surface as features). Real export lives in the
          // MessageActions toolbar (CSV).
          actions: false,
          renderer: "svg",
          theme: undefined,
        });
        view = result.view as unknown as { finalize?: () => void };
        setLoading(false);
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "Не удалось отрисовать график");
        setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
      try {
        view?.finalize?.();
      } catch {
        // ignore teardown errors
      }
    };
  }, [enriched]);

  if (!spec) {
    return <p className="chartFallback">{title}: нет данных для графика.</p>;
  }
  return (
    <div className="vegaChartWrap" aria-label={title}>
      {loading ? (
        <div className="chartLoader">
          <Loader2 className="spin" size={14} />
          <span>Рисую график…</span>
        </div>
      ) : null}
      {error ? <p className="chartFallback chartError">{error}</p> : null}
      <div ref={ref} className="vegaChart" />
    </div>
  );
}
