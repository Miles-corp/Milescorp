export type Role = "admin" | "user";

export interface Account {
  id: string;
  username: string;
  display_name: string;
  role: Role;
  disabled: boolean;
  created_at: number;
  last_login_at: number | null;
}

export interface Preferences {
  account_id: string;
  dev_mode: boolean;
  locale: string;
  theme: string;
}

export interface Me {
  account: Account;
  preferences: Preferences;
  csrf_token: string;
  miles_configured: boolean;
  device: Device | null;
  box_name: string;
}

export interface Metric {
  id: string;
  label: string;
  value: string | number | null;
  unit: string;
  available: boolean;
  reason: string | null;
  source: string;
  measured_at: string;
}

export interface BoxTelemetry {
  available: boolean;
  reason?: string;
  source?: string;
  horodatage?: string;
  cpu?: { charge?: number[] | null; uptime_s?: number | null };
  temperatures?: Array<{ capteur?: string; libelle?: string; celsius?: number; etat?: string }>;
  ventilos?: Array<{ capteur?: string; tr_min?: number; etat?: string }>;
  injection_esp32?: { etat?: string; age_s?: number; temperature?: number; humidite?: number };
  received_at?: string;
}

export interface SensorSnapshot {
  measured_at: string;
  mode: "normal" | "developpeur";
  host: {
    name: string;
    system: string;
    release: string;
    machine: string;
    cpu_count: number;
    python: string;
    pid: number;
  };
  process_uptime_s: number;
  values: Metric[];
  storage: {
    path: string;
    total_bytes: number;
    used_bytes: number;
    free_bytes: number;
    used_percent: number;
  } | null;
  box: BoxTelemetry;
  dev?: Record<string, unknown>;
}

export type AppletType = "system" | "render" | "action";

export interface Applet {
  id: string;
  title: string;
  description: string;
  type: AppletType;
  role: Role;
  dev_only: boolean;
  confirmation: string | null;
  creates_mission: boolean;
}

export interface MissionStep {
  step_id: string;
  objective: string;
  tool: string;
  status: string;
  attempts: number;
  error: string | null;
  note: string | null;
}

export interface MissionPending {
  kind: string;
  question: string;
  tool_ids: string[];
  allowed_roots: string[];
  approval_token: string;
  expires_at: number;
}

export interface Mission {
  mission_id: string;
  objective: string;
  state: string;
  planner: string;
  planner_note: string;
  steps: MissionStep[];
  facts: string[];
  errors: string[];
  unfinished: string[];
  budget: {
    executed_seconds: number;
    steps_executed: number;
    tool_calls: number;
    interactions: number;
    stop_reason: string;
    stop_detail: string;
  };
  pending: MissionPending | null;
  report: string;
  created_at: number;
  updated_at: number;
}

export interface Routine {
  id: string;
  name: string;
  objective: string;
  created_by: string | null;
  created_at: number;
  last_run_at: number | null;
  enabled: number;
}

export interface Device {
  id: string;
  label: string;
  paired_at: number;
  last_seen_at: number;
}

export interface ProviderInfo {
  id: string;
  label: string;
  requires_key: boolean;
  configured: boolean;
  active: boolean;
  model: string;
  key_state: string;
  mode: "local" | "distant";
}

export interface ProviderStatus {
  mode: string;
  provider: string | null;
  provider_label: string;
  model: string;
  configured: boolean;
  keyless: boolean;
  restart_required: boolean;
}

export interface AuditEvent {
  id: number;
  at: number;
  account: string | null;
  event: string;
  target: string;
  outcome: string;
  detail: Record<string, unknown>;
}

export interface AccessEntry {
  at: number;
  method: string;
  path: string;
  status: number;
  account: string;
  duration_ms: number;
  client: string;
}

export interface MemoryItem {
  id: number;
  content: string;
  kind?: string;
  created_at?: string | number;
  owner_user_id?: string;
  links?: Array<{ id?: number; kind?: string; target_id?: number; confirmed?: boolean }>;
  [key: string]: unknown;
}
