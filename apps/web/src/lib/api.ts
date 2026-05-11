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

export type RuntimeStatus = {
  server_runtime: boolean;
  extraction_mode: "mock" | "colab" | "disabled" | string;
  visualization_mode: string;
  colab_service_url_configured: boolean;
  colab_auth_token_configured: boolean;
  colab_available: boolean;
  colab_health: {
    model_loaded: boolean | null;
    gpu_name: string | null;
    mock_model: boolean | null;
  };
  debug_sql_visible: boolean;
};

export type ModelDescriptor = {
  id: string;
  label: string;
  approx_vram_gb: number;
  family: string;
  default?: boolean;
};

export type ModelCatalog = {
  current: string;
  loaded: boolean;
  load_error: string | null;
  models: ModelDescriptor[];
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
    let detail: unknown = `HTTP ${response.status}`;
    try {
      const payload = (await response.json()) as { detail?: unknown };
      if (payload.detail !== undefined) detail = payload.detail;
    } catch {
      // keep safe generic
    }
    const message =
      typeof detail === "string"
        ? detail
        : (() => {
            try {
              return JSON.stringify(detail);
            } catch {
              return `HTTP ${response.status}`;
            }
          })();
    throw new Error(message);
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

export function logout() {
  return api<{ message: string }>("/auth/logout", { method: "POST" });
}

export function getRuntime() {
  return api<RuntimeStatus>("/runtime");
}

export function listModels() {
  return api<ModelCatalog>("/admin/models");
}

export function loadModel(modelId: string) {
  return api<{
    status: string;
    model_loaded: boolean;
    model_id: string | null;
    mock_model: boolean;
    load_error: string | null;
    load_latency_ms: number | null;
  }>("/admin/load_model", {
    method: "POST",
    body: JSON.stringify({ model_id: modelId }),
  });
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
  options: {
    preferred_output: "auto" | "chart" | "table";
    response_style: "business" | "technical";
    data_source_id: string;
  },
) {
  return api<{ user_message: ChatMessage; assistant_message: ChatMessage }>(`/chats/${sessionId}/messages`, {
    method: "POST",
    body: JSON.stringify({
      content,
      data_source_id: options.data_source_id,
      preferred_output: options.preferred_output,
      response_style: options.response_style,
    }),
  });
}
