"use client";

import { useEffect, useRef, useState } from "react";
import { Loader2 } from "lucide-react";

type Spec = Record<string, unknown>;

// Dynamic import keeps vega-embed (~600 KB) out of the SSR bundle and away
// from `window`-touching code in Next's server runtime.
export function VegaChart({ spec, title }: { spec: Spec | null; title: string }) {
  const ref = useRef<HTMLDivElement | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    let view: { finalize?: () => void } | null = null;

    if (!ref.current || !spec) {
      setLoading(false);
      return;
    }

    const enriched: Spec = {
      ...spec,
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
        bar: { color: "#2563eb", cornerRadiusEnd: 4 },
        line: { color: "#2563eb", strokeWidth: 2.5 },
        point: { color: "#1e3a8a", filled: true, size: 60 },
        view: { stroke: "transparent" },
      },
    };

    (async () => {
      try {
        const mod = await import("vega-embed");
        if (cancelled || !ref.current) return;
        const result = await mod.default(ref.current, enriched, {
          actions: { export: true, source: false, compiled: false, editor: false },
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
  }, [spec]);

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
