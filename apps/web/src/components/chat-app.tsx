"use client";

import { FormEvent, KeyboardEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  BarChart3,
  ChevronDown,
  ChevronRight,
  Database,
  Info,
  Loader2,
  LogIn,
  Menu,
  MessageSquarePlus,
  Send,
  Sparkles,
  Table2,
  X,
} from "lucide-react";
import {
  ChatMessage,
  ChatSession,
  createChat,
  listChats,
  listMessages,
  login,
  me,
  register,
  sendMessage,
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

function lastAssistantHasSqlExecutionError(messages: ChatMessage[]): boolean {
  for (let i = messages.length - 1; i >= 0; i -= 1) {
    const m = messages[i];
    if (m.role !== "assistant") {
      continue;
    }
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
  if (ms < 1000) return `${ms} ms`;
  return `${(ms / 1000).toFixed(1)} s`;
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
  const [aboutOpen, setAboutOpen] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  const dataSource = useMemo(() => findDataSource(dataSourceId), [dataSourceId]);

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
    if (!user) {
      return;
    }
    void refreshChats();
  }, [user]);

  useEffect(() => {
    if (!activeSession) {
      return;
    }
    listMessages(activeSession)
      .then((payload) => setMessages(payload.messages))
      .catch((err: Error) => setError(err.message));
  }, [activeSession]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length, loading]);

  async function refreshChats() {
    const payload = await listChats();
    if (payload.sessions.length === 0) {
      const created = await createChat("Demo NL2BI");
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
      setError(err instanceof Error ? err.message : "Auth failed");
    } finally {
      setLoading(false);
    }
  }

  const handleSend = useCallback(
    async (rawContent?: string, opts?: { dropOptimistic?: boolean }) => {
      const content = (rawContent ?? input).trim();
      if (!activeSession || !content) return;
      setError("");
      setLoading(true);
      const optimistic: ChatMessage = {
        message_id: `local-${Date.now()}`,
        session_id: activeSession,
        role: "user",
        content,
        metadata: {},
        artifacts: [],
        created_at: Math.floor(Date.now() / 1000),
      };
      if (!opts?.dropOptimistic) {
        setMessages((current) => [...current, optimistic]);
      }
      try {
        const result = await sendMessage(activeSession, content, {
          preferred_output: preferredOutput,
          response_style: responseStyle,
          data_source_id: dataSourceId,
        });
        setMessages((current) => [
          ...current.filter((m) => m.message_id !== optimistic.message_id),
          result.user_message,
          result.assistant_message,
        ]);
        setInput("");
        await refreshChats();
      } catch (err) {
        const message = err instanceof Error ? err.message : "Request failed";
        setError(
          message.includes("colab")
            ? "Модель извлечения данных временно недоступна."
            : message,
        );
      } finally {
        setLoading(false);
      }
    },
    [activeSession, input, preferredOutput, responseStyle, dataSourceId],
  );

  function regenerate(messageId: string) {
    const idx = messages.findIndex((m) => m.message_id === messageId);
    if (idx < 1) return;
    const userMsg = messages[idx - 1];
    if (!userMsg || userMsg.role !== "user") return;
    void handleSend(userMsg.content);
  }

  function fillSuggestion(query: string) {
    setInput(query);
  }

  function handleComposerKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
      event.preventDefault();
      void handleSend();
    }
  }

  const activeTitle = useMemo(() => {
    return sessions.find((session) => session.session_id === activeSession)?.title ?? "Чат";
  }, [activeSession, sessions]);

  const showSuggestions = useMemo(() => {
    return messages.length === 0 || lastAssistantHasSqlExecutionError(messages);
  }, [messages]);

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
            <p className="authHint">Demo-доступ: <code>analyst</code> / <code>demo123</code>.</p>
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
    <main className={`appShell ${sidebarOpen ? "appShell--sidebarOpen" : ""}`}>
      {sidebarOpen ? (
        <div className="sidebarBackdrop" onClick={() => setSidebarOpen(false)} aria-hidden="true" />
      ) : null}
      <aside className="sidebar">
        <div className="brand">
          <div className="brandMark brandMark--sm" aria-hidden="true">
            <BarChart3 size={16} />
          </div>
          <strong>NL2BI</strong>
          <span className="brandUser">{user.username}</span>
        </div>
        <button
          className="newChat"
          onClick={async () => {
            const created = await createChat("Новый анализ");
            setSessions((current) => [created, ...current]);
            setActiveSession(created.session_id);
            setMessages([]);
            setSidebarOpen(false);
          }}
        >
          <MessageSquarePlus size={16} />
          New chat
        </button>
        <nav>
          {sessions.map((session) => (
            <button
              key={session.session_id}
              className={session.session_id === activeSession ? "session active" : "session"}
              onClick={() => {
                setActiveSession(session.session_id);
                setSidebarOpen(false);
              }}
            >
              {session.title}
            </button>
          ))}
        </nav>
        <button type="button" className="sidebarFooter" onClick={() => setAboutOpen(true)}>
          <Info size={14} />
          О проекте
        </button>
      </aside>
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
            <StatusPill />
            <ModelPicker />
            <select
              value={dataSourceId}
              onChange={(event) => setDataSourceId(event.target.value)}
              title="Выбрать демо-источник данных"
            >
              {DEMO_DATA_SOURCES.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.label}
                </option>
              ))}
            </select>
            <select
              value={preferredOutput}
              onChange={(event) => setPreferredOutput(event.target.value as "auto" | "chart" | "table")}
            >
              <option value="auto">Auto</option>
              <option value="chart">Chart</option>
              <option value="table">Table</option>
            </select>
            <select
              value={responseStyle}
              onChange={(event) => setResponseStyle(event.target.value as "business" | "technical")}
              title="Technical: показывать SQL и тех. детали"
            >
              <option value="business">Business</option>
              <option value="technical">Technical</option>
            </select>
          </div>
        </header>
        {schemaOpen ? (
          <section className="schemaPanel" aria-label="Схема демонстрационной БД">
            <p className="schemaHint">
              <strong>{dataSource.label}</strong> — {dataSource.blurb} Запросы про сущности, которых нет
              в таблицах, упрутся в <code>sql_execution_failed</code>.
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
              const technicalArtifacts = message.artifacts ?? [];
              return (
                <article key={message.message_id} className={`message ${message.role}`}>
                  <p>{message.content}</p>
                  {technicalArtifacts.map((artifact) => (
                    <ArtifactRenderer key={artifact.artifact_id} artifact={artifact} />
                  ))}
                  {message.role === "assistant" ? (
                    <div className="messageFooter">
                      {t ? (
                        <div className="timingStrip" title="Время компонентов пайплайна">
                          {t.extraction !== undefined ? <span>~SQL {fmtMs(t.extraction)}</span> : null}
                          {t.visualization !== undefined ? <span>· viz {fmtMs(t.visualization)}</span> : null}
                          {t.total !== undefined ? <span>· total {fmtMs(t.total)}</span> : null}
                        </div>
                      ) : null}
                      <MessageActions
                        artifacts={technicalArtifacts}
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
          <input
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={handleComposerKeyDown}
            placeholder={`Например: ${dataSource.suggestions[0]} (Ctrl+Enter — отправить)`}
          />
          <button type="submit" disabled={loading || !input.trim()} title="Send (Ctrl+Enter)">
            <Send size={16} />
            Send
          </button>
        </form>
      </section>
      {aboutOpen ? <AboutModal onClose={() => setAboutOpen(false)} /> : null}
    </main>
  );
}
