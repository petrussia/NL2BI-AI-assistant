"use client";

import { X } from "lucide-react";

type Props = { onClose: () => void };

export function AboutModal({ onClose }: Props) {
  return (
    <div className="modalBackdrop" role="dialog" aria-modal="true" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <button type="button" className="modalClose" onClick={onClose} aria-label="Закрыть">
          <X size={16} />
        </button>
        <h2>NL2BI AI Assistant</h2>
        <p className="modalLead">
          Прототип BI-чата уровня дипломного проекта: бизнес-вопрос на естественном языке → SQL →
          ответ + график. Без OpenAI, всё локально.
        </p>
        <h3>Архитектура</h3>
        <pre className="modalDiagram">
{`        Браузер (Next.js)
              │  /api/server/*
              ▼
        FastAPI gateway          (CPU, без LLM)
   ┌──────────┼───────────────────────────┐
   │          │                           │
   │   auth · chats · artifacts           │
   │          │                           │
   │          ▼                           │
   │   Nl2ChartOrchestrator               │
   │          │                           │
   │          ├── ColabExtractionClient (Bearer)
   │          │                           │
   │          ▼                           ▼
   │   /extract на ngrok-туннеле   CpuVisualizationService
   │          │                           │
   │          ▼                           ▼
   │   Qwen2.5-Coder (4-bit)        Vega-Lite spec
   │   на NVIDIA L4 (Colab)
   │          │
   │          ▼
   │   SQLite (Spider read-only)
   └──────────────────────────────────────`}
        </pre>
        <h3>Контракт</h3>
        <ul>
          <li>
            <code>POST /api/server/chats/{"{id}"}/messages</code> — отправка запроса в чат.
          </li>
          <li>
            <code>POST /api/server/nl2chart</code> — низкоуровневый orchestrator-вход.
          </li>
          <li>
            <code>POST /extract</code> на Colab (Bearer auth) — Qwen2.5-Coder → SQL →
            <code>DataExtractionResponse</code>.
          </li>
          <li>Артефакты: <code>table</code>, <code>chart_spec</code> (Vega-Lite), <code>warning</code>, <code>error</code>.</li>
        </ul>
        <h3>Гарантии</h3>
        <ul>
          <li>Bearer-auth на <code>/extract</code>, <code>/reload_model</code>.</li>
          <li>SELECT-only guard на стороне Colab, row_limit + timeout.</li>
          <li>field_metadata: для агрегированных колонок <code>default_aggregation=&quot;none&quot;</code>.</li>
          <li>Никаких raw-tracebacks в ответе пользователю — только enum-коды.</li>
        </ul>
      </div>
    </div>
  );
}
