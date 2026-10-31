import type {
  AccessEntry,
  Account,
  Applet,
  AuditEvent,
  Device,
  Me,
  MemoryItem,
  Mission,
  ProviderInfo,
  ProviderStatus,
  Routine,
  SensorSnapshot,
} from "./types";

const BASE = "/api/companion";
const CSRF_KEY = "miles_companion_csrf";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

export function setCsrf(token: string): void {
  if (token) sessionStorage.setItem(CSRF_KEY, token);
}

export function clearCsrf(): void {
  sessionStorage.removeItem(CSRF_KEY);
}

function csrf(): string {
  return sessionStorage.getItem(CSRF_KEY) || "";
}

async function request<T>(
  path: string,
  options: { method?: string; body?: unknown; csrf?: boolean } = {},
): Promise<T> {
  const method = options.method || "GET";
  const headers: Record<string, string> = { Accept: "application/json" };
  if (options.body !== undefined) headers["Content-Type"] = "application/json";
  if (options.csrf !== false && method !== "GET") headers["X-CSRF-Token"] = csrf();

  let response: Response;
  try {
    response = await fetch(BASE + path, {
      method,
      credentials: "same-origin",
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
    });
  } catch {
    throw new ApiError(0, "Serveur local injoignable.");
  }

  let payload: unknown = null;
  const text = await response.text();
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = { error: "Réponse illisible du serveur." };
    }
  }
  if (!response.ok) {
    const message =
      payload && typeof payload === "object" && "error" in payload
        ? String((payload as { error?: unknown }).error || `HTTP ${response.status}`)
        : `HTTP ${response.status}`;
    throw new ApiError(response.status, message);
  }
  return payload as T;
}

export const api = {
  me: () => request<Me>("/me"),
  login: async (username: string, password: string) => {
    const result = await request<{ account: Account; csrf_token: string }>("/auth/login", {
      method: "POST",
      body: { username, password },
      csrf: false,
    });
    setCsrf(result.csrf_token);
    return result;
  },
  logout: async () => {
    await request<{ ok: boolean }>("/auth/logout", { method: "POST", body: {} });
    clearCsrf();
  },
  changePassword: (current_password: string, new_password: string) =>
    request<{ ok: boolean }>("/password", {
      method: "POST",
      body: { current_password, new_password },
    }),
  setDevMode: (enabled: boolean) =>
    request<{ ok: boolean; preferences: { dev_mode: boolean } }>("/dev-mode", {
      method: "POST",
      body: { enabled },
    }),
  sensors: () => request<SensorSnapshot>("/sensors"),
  applets: () => request<{ applets: Applet[] }>("/applets"),
  status: () =>
    request<{
      provider: ProviderStatus;
      miles: Record<string, unknown> | null;
      box: { available: boolean; reason?: string };
    }>("/status"),
  // MILES absent n'est pas une panne du site : le serveur répond 503 avec
  // `available: false`, et les pages affichent alors l'explication prévue
  // plutôt qu'une erreur avec un « Réessayer » qui ne peut pas aboutir.
  missions: async () => {
    try {
      return await request<{ available: boolean; missions?: Mission[]; error?: string }>(
        "/missions",
      );
    } catch (exc) {
      if (exc instanceof ApiError && exc.status === 503) {
        return { available: false, missions: [], error: exc.message };
      }
      throw exc;
    }
  },
  mission: (id: string) =>
    request<{ available: boolean; mission?: Mission; error?: string }>(`/missions/${id}`),
  memory: async () => {
    try {
      return await request<{ available: boolean; memories?: MemoryItem[]; error?: string }>(
        "/memory",
      );
    } catch (exc) {
      if (exc instanceof ApiError && exc.status === 503) {
        return { available: false, memories: [], error: exc.message };
      }
      throw exc;
    }
  },
  routines: () => request<{ routines: Routine[] }>("/routines"),
  pair: (token: string, label: string) =>
    request<{ ok: boolean; box: { id: string; name: string }; device: Device }>("/pair", {
      method: "POST",
      body: { token, label },
      csrf: false,
    }),
  devices: () => request<{ devices: Device[] }>("/devices"),
  revokeDevice: (id: string) =>
    request<{ ok: boolean }>(`/devices/${id}`, { method: "DELETE" }),
  createRoutine: (name: string, objective: string) =>
    request<{ id: string }>("/routines", { method: "POST", body: { name, objective } }),
  deleteRoutine: (id: string) =>
    request<{ ok: boolean }>(`/routines/${id}`, { method: "DELETE" }),
  providers: () =>
    request<{ providers: ProviderInfo[]; status: ProviderStatus }>("/providers"),
  message: (message: string) =>
    request<{ response?: string; error?: string }>("/message", {
      method: "POST",
      body: { message },
    }),
  journal: () => request<{ events: AuditEvent[] }>("/journal"),
  accessLog: () => request<{ entries: AccessEntry[] }>("/access-log"),
  accounts: () => request<{ accounts: Account[] }>("/accounts"),
  createAccount: (data: {
    username: string;
    password: string;
    role: string;
    display_name: string;
  }) => request<{ account: Account }>("/accounts", { method: "POST", body: data }),
  updateAccount: (id: string, data: Record<string, unknown>) =>
    request<{ account: Account }>(`/accounts/${id}`, { method: "PATCH", body: data }),
  deleteAccount: (id: string) =>
    request<{ ok: boolean }>(`/accounts/${id}`, { method: "DELETE" }),
  prepare: (action: string, payload: Record<string, unknown>) =>
    request<{ token: string; expires_at: number; confirmation: string }>("/actions/prepare", {
      method: "POST",
      body: { action, payload },
    }),
  execute: (token: string, payload: Record<string, unknown>) =>
    request<{ ok: boolean; result: unknown }>("/actions/execute", {
      method: "POST",
      body: { token, payload },
    }),
};

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "Erreur inconnue.";
}
