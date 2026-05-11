"use client";

import { FormEvent, KeyboardEvent, useEffect, useMemo, useState } from "react";
import { ChevronDown, ChevronRight, Database, Loader2, LogIn, MessageSquarePlus, Send, Sparkles } from "lucide-react";
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
import {
  DEMO_DATA_SOURCE_ID,
  DEMO_DATA_SOURCE_LABEL,
  DEMO_TABLES,
  SUGGESTED_QUERIES,
} from "@/lib/demo-schema";

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

export function ChatApp() {
  const [user, setUser] = useState<User | null>(null);
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
  const [username, setUsername] = useState("analyst");
  const [password, setPassword] = useState("demo123");
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSession, setActiveSession] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState(SUGGESTED_QUERIES[0]);
  const [preferredOutput, setPreferredOutput] = useState<"auto" | "chart" | "table">("auto");
  const [responseStyle, setResponseStyle] = useState<"business" | "technical">("business");
  const [loading, setLoading] = useState(false);
  const [statusText, setStatusText] = useState("");
  const [error, setError] = useState("");
  const [schemaOpen, setSchemaOpen] = useState(false);

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
    refreshChats();
  }, [user]);

  useEffect(() => {
    if (!activeSession) {
      return;
    }
    listMessages(activeSession)
      .then((payload) => setMessages(payload.messages))
      .catch((err: Error) => setError(err.message));
  }, [activeSession]);

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

  async function handleSend(event?: FormEvent) {
    event?.preventDefault();
    if (!activeSession || !input.trim()) {
      return;
    }
    setError("");
    setLoading(true);
    setStatusText("Обрабатываю запрос...");
    const optimistic: ChatMessage = {
      message_id: `local-${Date.now()}`,
      session_id: activeSession,
      role: "user",
      content: input,
      metadata: {},
      artifacts: [],
      created_at: Math.floor(Date.now() / 1000),
    };
    setMessages((current) => [...current, optimistic]);
    try {
      setStatusText("Получаю данные...");
      const result = await sendMessage(activeSession, input, {
        preferred_output: preferredOutput,
        response_style: responseStyle,
      });
      setStatusText("Строю визуализацию...");
      setMessages((current) => [
        ...current.filter((message) => message.message_id !== optimistic.message_id),
        result.user_message,
        result.assistant_message,
      ]);
      setInput("");
      await refreshChats();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Request failed";
      setError(message.includes("colab") ? "Модель извлечения данных временно недоступна. Можно попробовать mock/demo режим." : message);
    } finally {
      setStatusText("");
      setLoading(false);
    }
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
          <div>
            <h1>NL2BI AI Assistant</h1>
            <p>Server-only MVP: FastAPI, mock/Colab extraction, CPU visualization, local artifacts.</p>
          </div>
          <form onSubmit={handleAuth} className="authForm">
            <label>
              Login
              <input value={username} onChange={(event) => setUsername(event.target.value)} />
            </label>
            <label>
              Password
              <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} />
            </label>
            {error ? <p className="formError">{error}</p> : null}
            <button type="submit" disabled={loading}>
              {loading ? <Loader2 className="spin" size={16} /> : <LogIn size={16} />}
              {authMode === "login" ? "Sign in" : "Register"}
            </button>
            <button type="button" className="linkButton" onClick={() => setAuthMode(authMode === "login" ? "register" : "login")}>
              {authMode === "login" ? "Create account" : "Use existing account"}
            </button>
          </form>
        </section>
      </main>
    );
  }

  return (
    <main className="appShell">
      <aside className="sidebar">
        <div className="brand">
          <strong>NL2BI</strong>
          <span>{user.username}</span>
        </div>
        <button
          className="newChat"
          onClick={async () => {
            const created = await createChat("Новый анализ");
            setSessions((current) => [created, ...current]);
            setActiveSession(created.session_id);
            setMessages([]);
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
              onClick={() => setActiveSession(session.session_id)}
            >
              {session.title}
            </button>
          ))}
        </nav>
      </aside>
      <section className="chatPane">
        <header className="chatHeader">
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
                Источник: <code>{DEMO_DATA_SOURCE_ID}</code> ({DEMO_DATA_SOURCE_LABEL})
              </span>
            </button>
          </div>
          <div className="toggles">
            <select value={preferredOutput} onChange={(event) => setPreferredOutput(event.target.value as "auto" | "chart" | "table")}>
              <option value="auto">Auto</option>
              <option value="chart">Chart</option>
              <option value="table">Table</option>
            </select>
            <select value={responseStyle} onChange={(event) => setResponseStyle(event.target.value as "business" | "technical")}>
              <option value="business">Business</option>
              <option value="technical">Technical</option>
            </select>
          </div>
        </header>
        {schemaOpen ? (
          <section className="schemaPanel" aria-label="Схема демонстрационной БД">
            <p className="schemaHint">
              В этом источнике четыре таблицы Spider <code>concert_singer</code>. Запросы про продажи/клиентов/выручку
              работать не будут — таких сущностей здесь нет.
            </p>
            <ul>
              {DEMO_TABLES.map((table) => (
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
          {messages.length === 0 ? (
            <div className="emptyState">
              <Sparkles size={18} />
              <p>Введите бизнес-вопрос — получите таблицу и график. Подсказки ниже работают на этой БД:</p>
            </div>
          ) : (
            messages.map((message) => (
              <article key={message.message_id} className={`message ${message.role}`}>
                <p>{message.content}</p>
                {message.artifacts?.map((artifact) => (
                  <ArtifactRenderer key={artifact.artifact_id} artifact={artifact} />
                ))}
              </article>
            ))
          )}
          {statusText ? <div className="statusLine"><Loader2 className="spin" size={16} />{statusText}</div> : null}
          {error ? <div className="notice error">{error}</div> : null}
        </div>
        {showSuggestions ? (
          <section className="suggestions" aria-label="Готовые запросы">
            {lastAssistantHasSqlExecutionError(messages) ? (
              <p className="suggestionsLead">
                Похоже, запрос не подходит под схему <code>{DEMO_DATA_SOURCE_ID}</code>. Попробуйте один из этих:
              </p>
            ) : (
              <p className="suggestionsLead">Готовые запросы:</p>
            )}
            <div className="chipRow">
              {SUGGESTED_QUERIES.map((q) => (
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
        <form className="composer" onSubmit={handleSend}>
          <input
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={handleComposerKeyDown}
            placeholder="Например: Сравни количество певцов по странам (Ctrl+Enter — отправить)"
          />
          <button type="submit" disabled={loading || !input.trim()} title="Send (Ctrl+Enter)">
            <Send size={16} />
            Send
          </button>
        </form>
      </section>
    </main>
  );
}
