export type Artifact = {
  artifact_id: string;
  artifact_type: "table" | "chart_spec" | "chart_image" | "warning" | "error" | "debug_sql" | "response";
  title: string;
  uri: string | null;
  payload: Record<string, unknown>;
  metadata: Record<string, unknown>;
};

export type ChatMessage = {
  message_id: string;
  session_id: string;
  role: "user" | "assistant" | "system";
  content: string;
  metadata: Record<string, unknown>;
  artifacts: Artifact[];
  created_at: number;
};

export type ChatSession = {
  session_id: string;
  title: string;
  created_at: number;
  updated_at: number;
  settings: Record<string, unknown>;
};

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/server${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    credentials: "include",
  });
  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      const payload = (await response.json()) as { detail?: string };
      detail = payload.detail ?? detail;
    } catch {
      // Keep safe generic message.
    }
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
}

export function register(username: string, password: string) {
  return api<{ username: string; role: string }>("/auth/register", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
}

export function login(username: string, password: string) {
  return api<{ username: string; role: string }>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
}

export function me() {
  return api<{ authenticated: boolean; username?: string; role?: string }>("/auth/me");
}

export function listChats() {
  return api<{ sessions: ChatSession[] }>("/chats");
}

export function createChat(title?: string) {
  return api<ChatSession>("/chats", {
    method: "POST",
    body: JSON.stringify({ title }),
  });
}

export function listMessages(sessionId: string) {
  return api<{ messages: ChatMessage[] }>(`/chats/${sessionId}/messages`);
}

export function sendMessage(
  sessionId: string,
  content: string,
  options: { preferred_output: "auto" | "chart" | "table"; response_style: "business" | "technical" },
) {
  return api<{ user_message: ChatMessage; assistant_message: ChatMessage }>(`/chats/${sessionId}/messages`, {
    method: "POST",
    body: JSON.stringify({
      content,
      data_source_id: "demo_sales",
      preferred_output: options.preferred_output,
      response_style: options.response_style,
    }),
  });
}
