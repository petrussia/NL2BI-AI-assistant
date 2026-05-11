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

  useEffect(() => {
    if (!catalog?.planner_loading) return;
    const id = window.setInterval(() => {
      void refresh();
    }, 5000);
    return () => window.clearInterval(id);
  }, [catalog?.planner_loading]);

  async function pick(modelId: string, target: "emitter" | "planner" = "emitter") {
    if (loading || !catalog) return;
    if (target === "emitter" && modelId === catalog.current && catalog.loaded) {
      setOpen(false);
      return;
    }
    if (
      target === "planner" &&
      modelId === catalog.planner_id &&
      (catalog.planner_loaded || catalog.planner_loading)
    ) {
      setOpen(false);
      return;
    }
    const targetLabel = target === "planner" ? "planner" : "emitter";
    const ok = window.confirm(
      target === "planner"
        ? `Запустить загрузку planner ${modelId}?\nEmitter останется активным, planner загрузится в фоне.`
        : `Загрузить emitter ${modelId}?\nЗагрузка ~1-3 мин, во время неё запросы /extract будут падать с model_not_loaded.`,
    );
    if (!ok) return;
    setLoading(true);
    setError(null);
    try {
      const res = await loadModel(modelId, target);
      if (res.status === "failed") {
        setError(res.load_error ?? `Загрузка ${targetLabel} не удалась`);
      } else if (target === "emitter" && !res.model_loaded) {
        setError(res.load_error ?? "Загрузка emitter не удалась");
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
  const plannerLoading = catalog.planner_loading ?? catalog.architecture === "planner_loading";
  const emitters = catalog.models.filter((m) => m.role !== "planner");
  const planners = catalog.models.filter((m) => m.role === "planner");

  return (
    <div className={`modelPicker ${open ? "modelPicker--open" : ""}`} ref={rootRef}>
      <button
        type="button"
        className="modelPicker__trigger"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        title={
          `HF id: ${catalog?.current ?? ""}` +
          (archLabel ? `\nАрхитектура: ${archLabel}` : "") +
          (plannerId ? `\nPlanner: ${plannerId}` : "")
        }
      >
        {loading ? <Loader2 size={14} className="spin" /> : <Cpu size={14} />}
        <span className="modelPicker__label">{currentLabel}</span>
        {catalog?.loaded ? null : <AlertTriangle size={12} color="#b45309" />}
      </button>
      {open ? (
        <ul className="modelPicker__menu" role="listbox">
          {planners.length > 0 ? (
            <li className="modelPicker__group">Planner</li>
          ) : null}
          {planners.map((m) => {
            const isCurrent = m.id === plannerId;
            const isLoading = isCurrent && plannerLoading && !plannerLoaded;
            return (
              <li key={m.id}>
                <button
                  type="button"
                  className={`modelPicker__item ${isCurrent ? "modelPicker__item--active" : ""}`}
                  onClick={() => pick(m.id, "planner")}
                  disabled={loading || isLoading}
                >
                  <span className="modelPicker__itemLabel">
                    {m.label}
                    <em className="modelPicker__itemMeta">
                      {m.family} · ~{m.approx_vram_gb} GB VRAM ·{" "}
                      {isCurrent && plannerLoaded
                        ? "загружен"
                        : isLoading
                          ? "загружается…"
                          : "не активен"}
                    </em>
                  </span>
                  {isLoading ? <Loader2 size={14} className="spin" /> : null}
                  {isCurrent && plannerLoaded ? <Check size={14} /> : null}
                </button>
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
                  onClick={() => pick(m.id, "emitter")}
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
          {catalog.planner_load_error ? (
            <li className="modelPicker__error">{catalog.planner_load_error}</li>
          ) : null}
        </ul>
      ) : null}
      {/* No more inline JSON-shaped error here — see the catalog-null branch
       * above; if we *do* have a catalog and a transient error (e.g. load
       * failed), it surfaces inside the menu instead of leaking into the
       * page-wide header. */}
    </div>
  );
}
