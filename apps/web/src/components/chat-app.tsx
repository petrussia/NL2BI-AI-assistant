"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { Loader2, LogIn, MessageSquarePlus, Send } from "lucide-react";
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

type User = {
  username: string;
  role: string;
};

export function ChatApp() {
  const [user, setUser] = useState<User | null>(null);
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
  const [username, setUsername] = useState("analyst");
  const [password, setPassword] = useState("demo123");
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSession, setActiveSession] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("Покажи динамику продаж по месяцам");
  const [preferredOutput, setPreferredOutput] = useState<"auto" | "chart" | "table">("auto");
  const [responseStyle, setResponseStyle] = useState<"business" | "technical">("business");
  const [loading, setLoading] = useState(false);
  const [statusText, setStatusText] = useState("");
  const [error, setError] = useState("");

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

  async function handleSend(event: FormEvent) {
    event.preventDefault();
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

  const activeTitle = useMemo(() => {
    return sessions.find((session) => session.session_id === activeSession)?.title ?? "Чат";
  }, [activeSession, sessions]);

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
          <div>
            <h1>{activeTitle}</h1>
            <p>Demo data source: demo_concert_singer</p>
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
        <div className="messages">
          {messages.length === 0 ? (
            <div className="emptyState">Введите бизнес-вопрос, чтобы получить таблицу или график.</div>
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
        <form className="composer" onSubmit={handleSend}>
          <input value={input} onChange={(event) => setInput(event.target.value)} placeholder="Например: Покажи топ клиентов по выручке" />
          <button type="submit" disabled={loading || !input.trim()}>
            <Send size={16} />
            Send
          </button>
        </form>
      </section>
    </main>
  );
}
