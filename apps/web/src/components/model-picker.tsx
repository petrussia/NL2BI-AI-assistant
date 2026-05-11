"use client";

import { useEffect, useRef, useState } from "react";
import { AlertTriangle, Check, Cpu, Loader2 } from "lucide-react";
import { listModels, loadModel, type ModelCatalog } from "@/lib/api";

export function ModelPicker() {
  const [catalog, setCatalog] = useState<ModelCatalog | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement | null>(null);

  // Close the menu when the user clicks anywhere outside the picker, opens a
  // different overlay (we react to Escape too), or scrolls/resizes hard.
  useEffect(() => {
    if (!open) return;
    function onPointer(e: MouseEvent) {
      const node = rootRef.current;
      if (!node) return;
      if (!node.contains(e.target as Node)) setOpen(false);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  async function refresh() {
    try {
      const cat = await listModels();
      setCatalog(cat);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "list_models failed");
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  async function pick(modelId: string) {
    if (loading || !catalog) return;
    if (modelId === catalog.current && catalog.loaded) {
      setOpen(false);
      return;
    }
    const ok = window.confirm(
      `Загрузить ${modelId}?\nЗагрузка ~1-3 мин, во время неё запросы /extract будут падать с model_not_loaded.`,
    );
    if (!ok) return;
    setLoading(true);
    setError(null);
    try {
      const res = await loadModel(modelId);
      if (!res.model_loaded) {
        setError(res.load_error ?? "Загрузка не удалась");
      }
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "load_model failed");
    } finally {
      setLoading(false);
      setOpen(false);
    }
  }

  if (!catalog && !error) {
    return (
      <button type="button" className="modelPicker modelPicker--loading" disabled>
        <Cpu size={14} />
        <span>Загружаю список…</span>
      </button>
    );
  }

  // If we have no catalog because the call failed (502, Colab offline, etc.)
  // hide the JSON noise behind a short pill — clicking expands to a single
  // 'недоступно' list entry. The full reason is in title=… for inspection.
  if (!catalog) {
    return (
      <button
        type="button"
        className="modelPicker modelPicker--loading"
        disabled
        title={error ?? "Модель сейчас недоступна"}
      >
        <AlertTriangle size={14} color="#b45309" />
        <span>Модель недоступна</span>
      </button>
    );
  }

  const current = catalog.models.find((m) => m.id === catalog.current);
  const currentLabel = current?.label ?? catalog.current ?? "—";
  const archLabel = catalog.architecture_label ?? null;
  const plannerId = catalog.planner_id ?? null;
  const plannerLoaded = catalog.planner_loaded ?? false;
  const emitters = catalog.models.filter((m) => m.role !== "planner");
  const planners = catalog.models.filter((m) => m.role === "planner");

  return (
    <div className={`modelPicker ${open ? "modelPicker--open" : ""}`} ref={rootRef}>
      <button
        type="button"
        className="modelPicker__trigger"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        title={`HF id: ${catalog?.current ?? ""}${plannerId ? `\nPlanner: ${plannerId}` : ""}`}
      >
        {loading ? <Loader2 size={14} className="spin" /> : <Cpu size={14} />}
        <span className="modelPicker__label">
          {archLabel ? `${archLabel} · ${currentLabel}` : currentLabel}
        </span>
        {catalog?.loaded ? null : <AlertTriangle size={12} color="#b45309" />}
      </button>
      {open ? (
        <ul className="modelPicker__menu" role="listbox">
          {planners.length > 0 ? (
            <li className="modelPicker__group">Planner</li>
          ) : null}
          {planners.map((m) => {
            const isCurrent = m.id === plannerId;
            return (
              <li key={m.id}>
                <div
                  className={`modelPicker__item ${isCurrent ? "modelPicker__item--active" : ""}`}
                  aria-disabled
                >
                  <span className="modelPicker__itemLabel">
                    {m.label}
                    <em className="modelPicker__itemMeta">
                      {m.family} · ~{m.approx_vram_gb} GB VRAM ·{" "}
                      {isCurrent && plannerLoaded
                        ? "загружен"
                        : isCurrent
                          ? "загружается…"
                          : "не активен"}
                    </em>
                  </span>
                  {isCurrent && plannerLoaded ? <Check size={14} /> : null}
                </div>
              </li>
            );
          })}
          {planners.length > 0 ? (
            <li className="modelPicker__group">Emitter</li>
          ) : null}
          {emitters.map((m) => {
            const isCurrent = m.id === catalog.current;
            return (
              <li key={m.id}>
                <button
                  type="button"
                  className={`modelPicker__item ${isCurrent ? "modelPicker__item--active" : ""}`}
                  onClick={() => pick(m.id)}
                  disabled={loading}
                >
                  <span className="modelPicker__itemLabel">
                    {m.label}
                    <em className="modelPicker__itemMeta">
                      {m.family} · ~{m.approx_vram_gb} GB VRAM
                    </em>
                  </span>
                  {isCurrent ? <Check size={14} /> : null}
                </button>
              </li>
            );
          })}
          {error ? <li className="modelPicker__error">{error}</li> : null}
        </ul>
      ) : null}
      {/* No more inline JSON-shaped error here — see the catalog-null branch
       * above; if we *do* have a catalog and a transient error (e.g. load
       * failed), it surfaces inside the menu instead of leaking into the
       * page-wide header. */}
    </div>
  );
}
