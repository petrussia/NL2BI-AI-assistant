"use client";

import { FormEvent, KeyboardEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  BarChart3,
  ChevronDown,
  ChevronRight,
  Database,
  HelpCircle,
  Info,
  Loader2,
  LogIn,
  LogOut,
  Menu,
  MessageSquarePlus,
  MoreVertical,
  PanelLeftClose,
  PanelLeftOpen,
  Pencil,
  Plus,
  Send,
  Sparkles,
  Table2,
  Trash2,
  X,
} from "lucide-react";
import {
  ChatMessage,
  ChatSession,
  createChat,
  deleteChat as apiDeleteChat,
  listChats,
  listMessages,
  login,
  logout as apiLogout,
  me,
  register,
  sendMessage,
  updateChat as apiUpdateChat,
} from "@/lib/api";
import { ArtifactRenderer } from "@/components/artifact-renderer";
import { StatusPill } from "@/components/status-pill";
import { ModelPicker } from "@/components/model-picker";
import { MessageActions } from "@/components/message-actions";
import { SkeletonMessage } from "@/components/skeleton-message";
import { AboutModal } from "@/components/about-modal";
import { DEFAULT_DATA_SOURCE_ID, DEMO_DATA_SOURCES, findDataSource } from "@/lib/demo-schema";

type User = {
  username: string;
  role: string;
};

const DEFAULT_CHAT_TITLE = "Новый чат";
const FIRST_DEFAULT_CHAT_TITLE = "Демо: певцы и концерты";

function isGenericChatTitle(t: string | undefined | null): boolean {
  if (!t) return true;
  const trimmed = t.trim();
  return (
    trimmed === DEFAULT_CHAT_TITLE ||
    trimmed === FIRST_DEFAULT_CHAT_TITLE ||
    trimmed === "Demo NL2BI" ||
    trimmed === "Новый анализ" ||
    trimmed === ""
  );
}

function shortenForTitle(text: string, n = 42): string {
  const clean = text.replace(/\s+/g, " ").trim();
  if (clean.length <= n) return clean;
  return clean.slice(0, n - 1) + "…";
}

function lastAssistantHasSqlExecutionError(messages: ChatMessage[]): boolean {
  for (let i = messages.length - 1; i >= 0; i -= 1) {
    const m = messages[i];
    if (m.role !== "assistant") continue;
    return (m.artifacts ?? []).some(
      (a) =>
        a.artifact_type === "error" &&
        typeof a.payload?.code === "string" &&
        (a.payload.code === "sql_execution_failed" || a.payload.code === "schema_not_found"),
    );
  }
  return false;
}

function timingFor(message: ChatMessage): { extraction?: number; visualization?: number; total?: number } | null {
  const debug = (message.metadata?.debug ?? {}) as Record<string, unknown>;
  const timing = (debug.timing ?? {}) as Record<string, unknown>;
  const out: { extraction?: number; visualization?: number; total?: number } = {};
  if (typeof timing.extraction_ms === "number") out.extraction = timing.extraction_ms;
  if (typeof timing.visualization_ms === "number") out.visualization = timing.visualization_ms;
  if (typeof timing.total_ms === "number") out.total = timing.total_ms;
  return Object.keys(out).length > 0 ? out : null;
}

function fmtMs(ms: number): string {
  if (ms < 1000) return `${ms} мс`;
  return `${(ms / 1000).toFixed(1)} с`;
}

// Reorders/filters artifacts based on preferred_output and response_style.
// preferred=chart promotes the chart_spec above the table. preferred=table
// hides chart_spec entirely. business hides debug_sql + warning details
// (gating happens inside ArtifactRenderer for warning/error/debug_sql).
function filteredArtifacts(
  artifacts: ChatMessage["artifacts"],
  preferred: "auto" | "chart" | "table",
): ChatMessage["artifacts"] {
  const list = artifacts ?? [];
  if (preferred === "table") {
    return list.filter((a) => a.artifact_type !== "chart_spec");
  }
  if (preferred === "chart") {
    const chart = list.find((a) => a.artifact_type === "chart_spec");
    if (chart) {
      return [chart, ...list.filter((a) => a.artifact_type !== "chart_spec")];
    }
    return list;
  }
  return list;
}

export function ChatApp() {
  const [user, setUser] = useState<User | null>(null);
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
  const [username, setUsername] = useState("analyst");
  const [password, setPassword] = useState("demo123");
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSession, setActiveSession] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [dataSourceId, setDataSourceId] = useState<string>(DEFAULT_DATA_SOURCE_ID);
  const [input, setInput] = useState<string>(findDataSource(DEFAULT_DATA_SOURCE_ID).suggestions[0]);
  const [preferredOutput, setPreferredOutput] = useState<"auto" | "chart" | "table">("auto");
  const [responseStyle, setResponseStyle] = useState<"business" | "technical">("business");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [schemaOpen, setSchemaOpen] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  // Desktop-only "hide sidebar" toggle (separate from the mobile drawer
  // state above). Persisted in localStorage so it survives reload.
  const [sidebarCollapsed, setSidebarCollapsed] = useState<boolean>(() => {
    if (typeof window === "undefined") return false;
    return window.localStorage.getItem("nl2bi.sidebarCollapsed") === "1";
  });
  const [aboutOpen, setAboutOpen] = useState(false);
  // Composer popover with response-format / response-style / suggestions toggle
  const [composerMenuOpen, setComposerMenuOpen] = useState(false);
  // User can hide the suggestion-chip row beneath the composer
  const [suggestionsEnabled, setSuggestionsEnabled] = useState(true);
  // Local-only chat title overrides — backend has no PATCH /chats yet,
  // so when the user sends the first message we rename the chat in-memory
  // for the sidebar without round-tripping.
  const [localTitles, setLocalTitles] = useState<Record<string, string>>({});
  // Sidebar per-session menu: which session has its kebab menu open
  const [menuFor, setMenuFor] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  // Close composer popover on outside click + Escape
  useEffect(() => {
    if (!composerMenuOpen) return;
    function onPointer(e: MouseEvent) {
      const target = e.target as HTMLElement;
      if (!target.closest?.(".composerMenu") && !target.closest?.(".composerMenuToggle")) {
        setComposerMenuOpen(false);
      }
    }
    function onKey(e: globalThis.KeyboardEvent) {
      if (e.key === "Escape") setComposerMenuOpen(false);
    }
    document.addEventListener("mousedown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [composerMenuOpen]);

  // Close kebab menu on outside click + Escape
  useEffect(() => {
    if (!menuFor) return;
    function onPointer(e: MouseEvent) {
      const target = e.target as HTMLElement;
      if (!target.closest?.(".sessionMenu") && !target.closest?.(".sessionKebab")) {
        setMenuFor(null);
      }
    }
    function onKey(e: globalThis.KeyboardEvent) { if (e.key === "Escape") setMenuFor(null); }
    document.addEventListener("mousedown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [menuFor]);

  async function handleRename(session: ChatSession) {
    const current = (localTitles[session.session_id] ?? session.title) || "";
    const next = window.prompt("Переименовать чат", current);
    if (next === null) return;
    const clean = next.trim();
    if (!clean || clean === current) return;
    try {
      const updated = await apiUpdateChat(session.session_id, { title: clean });
      setSessions((prev) => prev.map((s) => (s.session_id === session.session_id ? { ...s, title: updated.title } : s)));
      setLocalTitles((prev) => {
        const copy = { ...prev };
        delete copy[session.session_id];
        return copy;
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось переименовать чат");
    } finally {
      setMenuFor(null);
    }
  }

  async function handleDelete(session: ChatSession) {
    const title = localTitles[session.session_id] ?? session.title ?? "чат";
    const ok = window.confirm(`Удалить «${title}»? Сообщения тоже пропадут.`);
    if (!ok) return;
    try {
      await apiDeleteChat(session.session_id);
      setMenuFor(null);
      setLocalTitles((prev) => {
        const copy = { ...prev };
        delete copy[session.session_id];
        return copy;
      });
      const remaining = sessions.filter((s) => s.session_id !== session.session_id);
      setSessions(remaining);
      if (activeSession === session.session_id) {
        if (remaining.length > 0) {
          setActiveSession(remaining[0].session_id);
        } else {
          // No chats left — make a fresh empty one so the user lands in a
          // usable state rather than an empty pane.
          const created = await createChat(FIRST_DEFAULT_CHAT_TITLE);
          setSessions([created]);
          setActiveSession(created.session_id);
          setMessages([]);
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось удалить чат");
    }
  }

  const dataSource = useMemo(() => findDataSource(dataSourceId), [dataSourceId]);
  const technical = responseStyle === "technical";

  // Pull the request settings persisted on a message (by the server's
  // chats router). Used by Regenerate so it replays the *original*
  // data_source / output mode / response style, not the (possibly now
  // changed) global toggles.
  function settingsForMessage(message: ChatMessage): {
    data_source_id: string;
    preferred_output: "auto" | "chart" | "table";
    response_style: "business" | "technical";
  } | null {
    const md = (message.metadata?.request_settings ?? null) as Record<string, unknown> | null;
    if (!md) return null;
    const ds = typeof md.data_source_id === "string" ? md.data_source_id : null;
    const po = md.preferred_output === "auto" || md.preferred_output === "chart" || md.preferred_output === "table"
      ? md.preferred_output
      : null;
    const rs = md.response_style === "business" || md.response_style === "technical" ? md.response_style : null;
    if (!ds || !po || !rs) return null;
    return { data_source_id: ds, preferred_output: po, response_style: rs };
  }

  useEffect(() => {
    me()
      .then((payload) => {
        if (payload.authenticated && payload.username && payload.role) {
          setUser({ username: payload.username, role: payload.role });
        }
      })
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!user) return;
    void refreshChats();
  }, [user]);

  useEffect(() => {
    if (!activeSession) return;
    listMessages(activeSession)
      .then((payload) => {
        setMessages(payload.messages);
        // If the chat already has messages, drop the pre-filled suggestion
        // from the composer so the user isn't tempted to accidentally send
        // a duplicate of the first sample query. New empty chats keep the
        // suggestion as a hint.
        if (payload.messages.length > 0) {
          setInput("");
        } else {
          // For a brand-new empty session, refresh the suggestion to match
          // the *currently selected* data source (matters after switching
          // sources without a reload).
          setInput(findDataSource(dataSourceId).suggestions[0] ?? "");
        }
      })
      .catch((err: Error) => setError(err.message));
  }, [activeSession]);

  // Autoscroll to the bottom whenever the message list changes OR the
  // skeleton lights up, including after switching chats.
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: "smooth", block: "end" });
    }
  }, [messages.length, loading, activeSession]);

  async function refreshChats() {
    const payload = await listChats();
    if (payload.sessions.length === 0) {
      const created = await createChat(FIRST_DEFAULT_CHAT_TITLE);
      setSessions([created]);
      setActiveSession(created.session_id);
      return;
    }
    setSessions(payload.sessions);
    setActiveSession((current) => current ?? payload.sessions[0].session_id);
  }

  async function handleAuth(event: FormEvent) {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      const result = authMode === "login" ? await login(username, password) : await register(username, password);
      setUser(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось войти");
    } finally {
      setLoading(false);
    }
  }

  async function handleLogout() {
    try {
      await apiLogout();
    } catch {
      // ignore — clear local state anyway
    }
    setUser(null);
    setSessions([]);
    setActiveSession(null);
    setMessages([]);
    setLocalTitles({});
    setSidebarOpen(false);
    setSchemaOpen(false);
    setAboutOpen(false);
    setError("");
  }

  const handleSend = useCallback(
    async (
      rawContent?: string,
      overrides?: {
        preferred_output?: "auto" | "chart" | "table";
        response_style?: "business" | "technical";
        data_source_id?: string;
      },
    ) => {
      const content = (rawContent ?? input).trim();
      if (!activeSession || !content) return;
      const usedSource = overrides?.data_source_id ?? dataSourceId;
      const usedOutput = overrides?.preferred_output ?? preferredOutput;
      const usedStyle = overrides?.response_style ?? responseStyle;
      setError("");
      setLoading(true);
      // Auto-collapse the schema panel — the user is asking now, no need
      // to keep eating vertical space with a reference card.
      setSchemaOpen(false);
      const optimistic: ChatMessage = {
        message_id: `local-${Date.now()}`,
        session_id: activeSession,
        role: "user",
        content,
        metadata: {
          request_settings: {
            data_source_id: usedSource,
            preferred_output: usedOutput,
            response_style: usedStyle,
          },
        },
        artifacts: [],
        created_at: Math.floor(Date.now() / 1000),
      };
      setMessages((current) => [...current, optimistic]);
      // If the active chat still has a generic title, rename it locally
      // from the user's first non-trivial query so the sidebar makes sense.
      const sessionTitleNow = sessions.find((s) => s.session_id === activeSession)?.title;
      if (isGenericChatTitle(localTitles[activeSession] ?? sessionTitleNow)) {
        setLocalTitles((prev) => ({ ...prev, [activeSession]: shortenForTitle(content) }));
      }
      try {
        const result = await sendMessage(activeSession, content, {
          preferred_output: usedOutput,
          response_style: usedStyle,
          data_source_id: usedSource,
        });
        setMessages((current) => [
          ...current.filter((m) => m.message_id !== optimistic.message_id),
          result.user_message,
          result.assistant_message,
        ]);
        setInput("");
        await refreshChats();
      } catch (err) {
        const message = err instanceof Error ? err.message : "Ошибка запроса";
        setError(
          message.includes("colab")
            ? "Модель извлечения данных временно недоступна."
            : message,
        );
      } finally {
        setLoading(false);
      }
    },
    [activeSession, input, preferredOutput, responseStyle, dataSourceId, sessions, localTitles],
  );

  function regenerate(assistantMessageId: string) {
    const idx = messages.findIndex((m) => m.message_id === assistantMessageId);
    if (idx < 1) return;
    const userMsg = messages[idx - 1];
    if (!userMsg || userMsg.role !== "user") return;
    // Replay with the *original* settings stored on the user message (the
    // server persists request_settings on the user message metadata). Falls
    // back to current globals if the message pre-dates that change.
    const original = settingsForMessage(userMsg);
    void handleSend(userMsg.content, original ?? undefined);
  }

  function fillSuggestion(query: string) {
    // Auto-send on chip click: the chip text is a complete, well-formed
    // suggestion, so making the user click Send again is busywork.
    setInput("");
    void handleSend(query);
  }

  function toggleSidebarCollapsed() {
    setSidebarCollapsed((prev) => {
      const next = !prev;
      if (typeof window !== "undefined") {
        window.localStorage.setItem("nl2bi.sidebarCollapsed", next ? "1" : "0");
      }
      return next;
    });
  }

  function handleComposerKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
      event.preventDefault();
      void handleSend();
    }
  }

  function titleFor(session: ChatSession): string {
    return localTitles[session.session_id] ?? session.title ?? DEFAULT_CHAT_TITLE;
  }

  const activeTitle = useMemo(() => {
    const s = sessions.find((session) => session.session_id === activeSession);
    return s ? titleFor(s) : DEFAULT_CHAT_TITLE;
  }, [activeSession, sessions, localTitles]);

  // When the user explicitly turns suggestions ON in the composer popover,
  // they want them visible at all times — not gated on empty chat / SQL
  // error like the v0.9 auto-show behavior.
  const showSuggestions = useMemo(() => suggestionsEnabled, [suggestionsEnabled]);

  if (!user) {
    return (
      <main className="authScreen">
        <section className="authPanel">
          <div className="authHero">
            <div className="brandMark" aria-hidden="true">
              <BarChart3 size={22} />
            </div>
            <h1>NL2BI AI Assistant</h1>
            <p>
              Дипломный проект: бизнес-вопрос на естественном языке → SQL → таблица и график.
              Colab-GPU Qwen2.5-Coder, без OpenAI.
            </p>
          </div>
          <div className="authTabs" role="tablist">
            <button
              type="button"
              role="tab"
              aria-selected={authMode === "login"}
              className={`authTab ${authMode === "login" ? "authTab--active" : ""}`}
              onClick={() => setAuthMode("login")}
            >
              Войти
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={authMode === "register"}
              className={`authTab ${authMode === "register" ? "authTab--active" : ""}`}
              onClick={() => setAuthMode("register")}
            >
              Зарегистрироваться
            </button>
          </div>
          <form onSubmit={handleAuth} className="authForm">
            <label>
              Логин
              <input
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                autoComplete="username"
                spellCheck={false}
              />
            </label>
            <label>
              Пароль
              <input
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                autoComplete={authMode === "login" ? "current-password" : "new-password"}
              />
            </label>
            <p className="authHint">Демо-доступ: <code>analyst</code> / <code>demo123</code>.</p>
            {error ? <p className="formError">{error}</p> : null}
            <button type="submit" disabled={loading}>
              {loading ? <Loader2 className="spin" size={16} /> : <LogIn size={16} />}
              {authMode === "login" ? "Войти" : "Создать аккаунт"}
            </button>
          </form>
        </section>
      </main>
    );
  }

  return (
    <main className={`appShell ${sidebarOpen ? "appShell--sidebarOpen" : ""} ${sidebarCollapsed ? "appShell--sidebarCollapsed" : ""}`}>
      {sidebarOpen ? (
        <div className="sidebarBackdrop" onClick={() => setSidebarOpen(false)} aria-hidden="true" />
      ) : null}
      <aside className="sidebar">
        <div className="brand">
          <div className="brandMark brandMark--sm" aria-hidden="true">
            <BarChart3 size={16} />
          </div>
          <strong>NL2BI</strong>
          <button
            type="button"
            className="sidebarCollapseToggle sidebarCollapseToggle--inside"
            onClick={toggleSidebarCollapsed}
            aria-label="Скрыть боковую панель"
            title="Скрыть боковую панель"
          >
            <PanelLeftClose size={16} />
          </button>
          <span className="brandUser">{user.username}</span>
        </div>
        <button
          className="newChat"
          onClick={async () => {
            const created = await createChat(DEFAULT_CHAT_TITLE);
            setSessions((current) => [created, ...current]);
            setActiveSession(created.session_id);
            setMessages([]);
            setSidebarOpen(false);
          }}
        >
          <MessageSquarePlus size={16} />
          Новый чат
        </button>
        <nav>
          {sessions.map((session) => {
            const t = titleFor(session);
            const isActive = session.session_id === activeSession;
            const isMenuOpen = menuFor === session.session_id;
            return (
              <div key={session.session_id} className={`sessionRow ${isActive ? "sessionRow--active" : ""}`}>
                <button
                  className={isActive ? "session active" : "session"}
                  onClick={() => {
                    setActiveSession(session.session_id);
                    setSidebarOpen(false);
                  }}
                  title={t}
                >
                  {t}
                </button>
                <button
                  type="button"
                  className="sessionKebab"
                  aria-label="Действия с чатом"
                  onClick={(e) => {
                    e.stopPropagation();
                    setMenuFor((cur) => (cur === session.session_id ? null : session.session_id));
                  }}
                >
                  <MoreVertical size={14} />
                </button>
                {isMenuOpen ? (
                  <div className="sessionMenu" role="menu">
                    <button type="button" role="menuitem" onClick={() => handleRename(session)}>
                      <Pencil size={13} /> Переименовать
                    </button>
                    <button
                      type="button"
                      role="menuitem"
                      className="sessionMenu__danger"
                      onClick={() => handleDelete(session)}
                    >
                      <Trash2 size={13} /> Удалить
                    </button>
                  </div>
                ) : null}
              </div>
            );
          })}
        </nav>
        <div className="sidebarFooterRow">
          <button type="button" className="sidebarFooter" onClick={() => setAboutOpen(true)}>
            <Info size={14} />
            О проекте
          </button>
          <button type="button" className="sidebarFooter" onClick={handleLogout} title="Выйти из аккаунта">
            <LogOut size={14} />
            Выйти
          </button>
        </div>
      </aside>
      {sidebarCollapsed ? (
        <button
          type="button"
          className="sidebarExpandFloat"
          onClick={toggleSidebarCollapsed}
          aria-label="Показать список чатов"
          title="Показать боковую панель"
        >
          <PanelLeftOpen size={16} />
        </button>
      ) : null}
      <section className="chatPane">
        <header className="chatHeader">
          <button
            type="button"
            className="hamburger"
            onClick={() => setSidebarOpen((v) => !v)}
            aria-label={sidebarOpen ? "Закрыть меню" : "Открыть меню"}
          >
            {sidebarOpen ? <X size={18} /> : <Menu size={18} />}
          </button>
          <div className="chatHeaderTitle">
            <h1>{activeTitle}</h1>
            <button
              type="button"
              className="schemaToggle"
              onClick={() => setSchemaOpen((open) => !open)}
              aria-expanded={schemaOpen}
            >
              {schemaOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
              <Database size={14} />
              <span>
                Источник: <code>{dataSource.id}</code> ({dataSource.label})
              </span>
            </button>
          </div>
          <div className="toggles">
            <div className="headerChip">
              <StatusPill />
              <span
                className="hintMark"
                data-tooltip={
                  "Статус Colab GPU и модели.\n" +
                  "Зелёный — модель и демо-БД готовы.\n" +
                  "Жёлтый — нет модели или нет демо-данных.\n" +
                  "Красный — Colab офлайн, /extract упадёт."
                }
                tabIndex={0}
                aria-label="Подсказка"
              >
                <HelpCircle size={12} />
              </span>
            </div>
            <div className="headerChip">
              <ModelPicker />
              <span
                className="hintMark"
                data-tooltip={
                  "Активная LLM на Colab GPU.\n" +
                  "Клик — переключение на другую модель (1-3 мин).\n" +
                  "Во время загрузки /extract падает с model_not_loaded."
                }
                tabIndex={0}
                aria-label="Подсказка"
              >
                <HelpCircle size={12} />
              </span>
            </div>
            <div className="headerChip">
              <select
                value={dataSourceId}
                onChange={(event) => setDataSourceId(event.target.value)}
                title="Выбрать демо-источник данных"
                className="toggleSelect toggleSelect--source"
              >
                {DEMO_DATA_SOURCES.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.label}
                  </option>
                ))}
              </select>
              <span
                className="hintMark"
                data-tooltip={
                  "Демо-источник данных (Spider SQLite).\n" +
                  "Переключите, если вопрос про другую схему.\n" +
                  "Источник прибивается к каждому сообщению."
                }
                tabIndex={0}
                aria-label="Подсказка"
              >
                <HelpCircle size={12} />
              </span>
            </div>
            {/* Авто/Бизнес moved into the composer's "+" popover so the
             *  header isn't a wall of selects. Source select stays here —
             *  it changes per-message context, not a session preference. */}
          </div>
        </header>
        {schemaOpen ? (
          <section className="schemaPanel" aria-label="Схема демонстрационной БД">
            <p className="schemaHint">
              <strong>{dataSource.label}</strong> — {dataSource.blurb}{" "}
              {technical ? (
                <>
                  Запросы про сущности, которых нет в таблицах, упрутся в{" "}
                  <code>sql_execution_failed</code>.
                </>
              ) : (
                <>
                  Если запрос не подходит под схему, система покажет понятную ошибку и
                  предложит готовые варианты.
                </>
              )}
            </p>
            <ul>
              {dataSource.tables.map((table) => (
                <li key={table.name}>
                  <strong>{table.name}</strong>
                  <span className="schemaTableDesc">{table.description}</span>
                  <div className="schemaCols">
                    {table.columns.map((col) => (
                      <span key={col.name} className="schemaCol">
                        {col.name}
                        <em>{col.type}</em>
                      </span>
                    ))}
                  </div>
                </li>
              ))}
            </ul>
          </section>
        ) : null}
        <div className="messages">
          {messages.length === 0 && !loading ? (
            <div className="emptyState">
              <Sparkles size={18} />
              <div>
                <p>Введите бизнес-вопрос — получите таблицу и график.</p>
                <div className="emptyStateMock" aria-hidden="true">
                  <div className="emptyStateMock__col">
                    <Table2 size={12} />
                    <div className="skelTableRow skelTableRow--mini" />
                    <div className="skelTableRow skelTableRow--mini" />
                    <div className="skelTableRow skelTableRow--mini" />
                  </div>
                  <div className="emptyStateMock__col">
                    <BarChart3 size={12} />
                    <div className="emptyStateMock__bars">
                      <span style={{ height: "60%" }} />
                      <span style={{ height: "30%" }} />
                      <span style={{ height: "85%" }} />
                    </div>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            messages.map((message) => {
              const t = timingFor(message);
              const arts = filteredArtifacts(message.artifacts, preferredOutput);
              const msgSettings = settingsForMessage(message);
              const msgSource = msgSettings?.data_source_id;
              const msgSourceLabel = msgSource ? findDataSource(msgSource).label : null;
              return (
                <article key={message.message_id} className={`message ${message.role}`}>
                  <p>{message.content}</p>
                  {arts.map((artifact) => (
                    <ArtifactRenderer
                      key={artifact.artifact_id}
                      artifact={artifact}
                      technical={technical}
                    />
                  ))}
                  {message.role === "assistant" ? (
                    <div className="messageFooter">
                      <div className="messageMeta">
                        {msgSource ? (
                          <span
                            className={
                              "sourceBadge" +
                              (msgSource !== dataSourceId ? " sourceBadge--mismatch" : "")
                            }
                            title={
                              msgSource !== dataSourceId
                                ? `Этот ответ построен на источнике ${msgSource}, отличном от текущего ${dataSourceId}`
                                : `Источник этого ответа: ${msgSource}`
                            }
                          >
                            <Database size={11} />
                            {msgSourceLabel ?? msgSource}
                          </span>
                        ) : null}
                        {t && technical ? (
                          <span className="timingStrip" title="Время компонентов пайплайна">
                            {t.extraction !== undefined ? <span>~SQL {fmtMs(t.extraction)}</span> : null}
                            {t.visualization !== undefined ? <span>· визуализация {fmtMs(t.visualization)}</span> : null}
                            {t.total !== undefined ? <span>· итого {fmtMs(t.total)}</span> : null}
                          </span>
                        ) : t && !technical && t.total !== undefined ? (
                          <span className="timingStrip" title="Время полного запроса">
                            Готово за {fmtMs(t.total)}
                          </span>
                        ) : null}
                      </div>
                      <MessageActions
                        artifacts={arts}
                        onRegenerate={() => regenerate(message.message_id)}
                        regenerateDisabled={loading}
                      />
                    </div>
                  ) : null}
                </article>
              );
            })
          )}
          {loading ? <SkeletonMessage /> : null}
          {error ? <div className="notice error">{error}</div> : null}
          <div ref={messagesEndRef} />
        </div>
        {showSuggestions ? (
          <section className="suggestions" aria-label="Готовые запросы">
            {lastAssistantHasSqlExecutionError(messages) ? (
              <p className="suggestionsLead">
                Похоже, запрос не подходит под схему <code>{dataSource.id}</code>. Попробуйте один из этих:
              </p>
            ) : (
              <p className="suggestionsLead">Готовые запросы для <code>{dataSource.id}</code>:</p>
            )}
            <div className="chipRow">
              {dataSource.suggestions.map((q) => (
                <button
                  key={q}
                  type="button"
                  className="chip"
                  onClick={() => fillSuggestion(q)}
                  disabled={loading}
                >
                  {q}
                </button>
              ))}
            </div>
          </section>
        ) : null}
        <form className="composer" onSubmit={(e) => { e.preventDefault(); void handleSend(); }}>
          {composerMenuOpen ? (
            <div className="composerMenu" role="menu">
              <div className="composerMenuRow">
                <label className="composerMenuLabel">
                  Подсказки под композером
                  <span
                    className="hintMark"
                    data-tooltip={
                      "Под полем ввода показываются готовые запросы для текущего источника.\n" +
                      "Клик по чипу сразу отправляет вопрос."
                    }
                    tabIndex={0}
                    aria-label="Подсказка"
                  >
                    <HelpCircle size={12} />
                  </span>
                </label>
                <label className="composerSwitch">
                  <input
                    type="checkbox"
                    checked={suggestionsEnabled}
                    onChange={(e) => setSuggestionsEnabled(e.target.checked)}
                  />
                  <span className="composerSwitch__track" aria-hidden="true" />
                  <span className="composerSwitch__label">{suggestionsEnabled ? "Вкл" : "Выкл"}</span>
                </label>
              </div>

              <div className="composerMenuRow">
                <label className="composerMenuLabel">
                  Формат ответа
                  <span
                    className="hintMark"
                    data-tooltip={
                      "Авто — модель сама выбирает таблицу или график.\n" +
                      "График — всегда строить визуализацию.\n" +
                      "Таблица — только табличный результат."
                    }
                    tabIndex={0}
                    aria-label="Подсказка"
                  >
                    <HelpCircle size={12} />
                  </span>
                </label>
                <div className="segmented" role="radiogroup" aria-label="Формат ответа">
                  {(["auto", "chart", "table"] as const).map((v) => (
                    <button
                      key={v}
                      type="button"
                      role="radio"
                      aria-checked={preferredOutput === v}
                      className={`segmented__btn ${preferredOutput === v ? "segmented__btn--active" : ""}`}
                      onClick={() => setPreferredOutput(v)}
                    >
                      {v === "auto" ? "Авто" : v === "chart" ? "График" : "Таблица"}
                    </button>
                  ))}
                </div>
              </div>

              <div className="composerMenuRow">
                <label className="composerMenuLabel">
                  Стиль ответа
                  <span
                    className="hintMark"
                    data-tooltip={
                      "Бизнес — короткая формулировка для пользователя.\n" +
                      "Технический — показывается SQL, коды ошибок, метаданные колонок."
                    }
                    tabIndex={0}
                    aria-label="Подсказка"
                  >
                    <HelpCircle size={12} />
                  </span>
                </label>
                <div className="segmented" role="radiogroup" aria-label="Стиль ответа">
                  {(["business", "technical"] as const).map((v) => (
                    <button
                      key={v}
                      type="button"
                      role="radio"
                      aria-checked={responseStyle === v}
                      className={`segmented__btn ${responseStyle === v ? "segmented__btn--active" : ""}`}
                      onClick={() => setResponseStyle(v)}
                    >
                      {v === "business" ? "Бизнес" : "Технический"}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          ) : null}
          <div className="composerPill">
            <button
              type="button"
              className="composerMenuToggle"
              onClick={() => setComposerMenuOpen((v) => !v)}
              aria-expanded={composerMenuOpen}
              aria-haspopup="menu"
              title="Настройки ответа"
            >
              <Plus size={18} />
            </button>
            <input
              value={input}
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={handleComposerKeyDown}
              placeholder={`Например: ${dataSource.suggestions[0]} (Ctrl+Enter — отправить)`}
              className="composerInput"
            />
            <button
              type="submit"
              className="composerSend"
              disabled={loading || !input.trim()}
              title="Отправить (Ctrl+Enter)"
              aria-label="Отправить"
            >
              <Send size={16} />
            </button>
          </div>
        </form>
      </section>
      {aboutOpen ? <AboutModal onClose={() => setAboutOpen(false)} /> : null}
    </main>
  );
}
