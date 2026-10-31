export function formatDate(value: number | string | null | undefined): string {
  if (value === null || value === undefined || value === "") return "inconnu";
  const date =
    typeof value === "number" ? new Date(value * 1000) : new Date(value);
  if (Number.isNaN(date.getTime())) return "inconnu";
  return new Intl.DateTimeFormat("fr-FR", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(date);
}

export function formatAge(value: number | null | undefined): string {
  if (value === null || value === undefined) return "âge inconnu";
  if (value < 60) return `il y a ${Math.max(0, Math.round(value))} s`;
  if (value < 3600) return `il y a ${Math.round(value / 60)} min`;
  if (value < 86400) return `il y a ${Math.round(value / 3600)} h`;
  return `il y a ${Math.round(value / 86400)} j`;
}

export function formatDuration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return "inconnu";
  const total = Math.max(0, Math.round(seconds));
  if (total < 60) return `${total} s`;
  const minutes = Math.floor(total / 60);
  if (minutes < 60) return `${minutes} min ${total % 60} s`;
  const hours = Math.floor(minutes / 60);
  return `${hours} h ${minutes % 60} min`;
}

export function formatBytes(bytes: number | null | undefined): string {
  if (bytes === null || bytes === undefined) return "inconnu";
  const units = ["o", "Kio", "Mio", "Gio", "Tio"];
  let value = Math.max(0, bytes);
  let index = 0;
  while (value >= 1024 && index < units.length - 1) {
    value /= 1024;
    index += 1;
  }
  return `${value.toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
}

export const MISSION_LABELS: Record<string, string> = {
  pending: "en attente",
  planning: "planification",
  running: "en cours",
  waiting_input: "attente réponse",
  waiting_authorization: "attente autorisation",
  completed: "terminée",
  failed: "échec",
  cancelled: "annulée",
  blocked: "bloquée",
};

export function missionLabel(state: string): string {
  return MISSION_LABELS[state] || state || "inconnu";
}

export function missionTone(state: string): "ok" | "warn" | "error" | "muted" | "accent" {
  if (state === "completed") return "ok";
  if (state === "failed") return "error";
  if (state === "cancelled" || state === "blocked") return "muted";
  if (state.startsWith("waiting")) return "warn";
  return "accent";
}

export const MEMORY_KIND_LABELS: Record<string, string> = {
  fait: "fait",
  hypothese: "hypothèse",
  inconnu: "non qualifié",
};

export function memoryKind(kind: string | undefined): string {
  return MEMORY_KIND_LABELS[kind || "inconnu"] || kind || "non qualifié";
}

export function providerLabel(value: string | null | undefined): string {
  if (!value) return "non configuré";
  const labels: Record<string, string> = {
    groq: "Groq",
    openai: "OpenAI",
    anthropic: "Claude (Anthropic)",
    gemini: "Gemini",
    local: "Ollama (local)",
    remote: "distant",
  };
  return labels[value] || value;
}

export function summarizeResult(result: unknown): string {
  if (result === null || result === undefined) return "Action exécutée.";
  if (typeof result === "string") return result;
  if (typeof result === "object") {
    const record = result as Record<string, unknown>;
    for (const key of ["message", "error", "state", "status", "provider"]) {
      if (typeof record[key] === "string" && record[key]) return String(record[key]);
    }
    if (typeof record["mission_id"] === "string") return `Mission ${record["mission_id"]}.`;
    if (typeof record["available"] === "boolean") {
      return record["available"] ? "Disponible." : "Indisponible.";
    }
  }
  return "Action exécutée.";
}
