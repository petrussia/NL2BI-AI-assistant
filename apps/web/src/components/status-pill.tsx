"use client";

import { useEffect, useState } from "react";
import { CircleDot } from "lucide-react";
import { getRuntime, type RuntimeStatus } from "@/lib/api";

type Tone = "green" | "yellow" | "red";

function classify(r: RuntimeStatus | null, err: string | null): { tone: Tone; label: string; hint: string } {
  if (err || !r) {
    return { tone: "red", label: "Сервер недоступен", hint: err ?? "GET /runtime упал" };
  }
  if (r.extraction_mode === "mock") {
    return {
      tone: "yellow",
      label: "Mock-режим",
      hint: "extraction_mode=mock, реальная Colab-модель не используется",
    };
  }
  if (r.extraction_mode !== "colab") {
    return { tone: "yellow", label: "Без Text-to-SQL", hint: `extraction_mode=${r.extraction_mode}` };
  }
  if (!r.colab_available) {
    return { tone: "red", label: "Colab offline", hint: "Сервис /extract не отвечает" };
  }
  if (r.colab_health.model_loaded === false) {
    return { tone: "yellow", label: "Модель не загружена", hint: "Colab жив, но model_loaded=false" };
  }
  const gpu = r.colab_health.gpu_name ?? "GPU";
  return {
    tone: "green",
    label: `${gpu} · ready`,
    hint: r.colab_health.mock_model ? "mock_model=true" : "/health.model_loaded=true",
  };
}

export function StatusPill({ pollMs = 30000 }: { pollMs?: number }) {
  const [runtime, setRuntime] = useState<RuntimeStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    const tick = async () => {
      try {
        const data = await getRuntime();
        if (!cancelled) {
          setRuntime(data);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "fetch failed");
      } finally {
        if (!cancelled) timer = setTimeout(tick, pollMs);
      }
    };
    void tick();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [pollMs]);

  const { tone, label, hint } = classify(runtime, error);
  return (
    <span className={`statusPill statusPill--${tone}`} title={hint}>
      <CircleDot size={12} />
      {label}
    </span>
  );
}
