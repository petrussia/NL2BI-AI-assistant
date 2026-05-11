"use client";

import { useEffect, useState } from "react";
import { CircleDot } from "lucide-react";
import { getRuntime, type RuntimeStatus } from "@/lib/api";

type Tone = "green" | "yellow" | "red" | "gray";

function classify(
  r: RuntimeStatus | null,
  err: string | null,
  checking: boolean,
): { tone: Tone; label: string; hint: string } {
  if (checking && !r && !err) {
    // First /runtime request hasn't returned yet — show a neutral 'checking'
    // pill so we don't flash red before we know anything.
    return { tone: "gray", label: "Проверяю сервер…", hint: "Жду первый ответ от /api/server/runtime" };
  }
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
  if (r.colab_health.demo_db_ready === false) {
    return {
      tone: "yellow",
      label: "Нет демо-данных",
      hint: "model_loaded=true, но demo_db_ready=false — Spider SQLite registry не подмонтирован, /extract вернёт schema_not_found",
    };
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
  const [checking, setChecking] = useState<boolean>(true);

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
        if (!cancelled) {
          setChecking(false);
          timer = setTimeout(tick, pollMs);
        }
      }
    };
    void tick();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [pollMs]);

  const { tone, label, hint } = classify(runtime, error, checking);
  return (
    <span className={`statusPill statusPill--${tone}`} title={hint}>
      <CircleDot size={12} />
      {label}
    </span>
  );
}
