/**
 * Typed API client for all preset and config endpoints.
 * Centralizes fetch calls and 409-conflict error handling.
 */

const API_BASE = "http://localhost:8000";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface PresetResponse {
  id: string;
  name: string;
  description: string | null;
  overrides: Record<string, unknown>;
  schema_version: number;
  createdAt: string;
  updatedAt: string;
}

export interface PresetCreatePayload {
  name: string;
  description?: string | null;
  overrides: Record<string, unknown>;
}

export interface PresetUpdatePayload {
  name?: string;
  description?: string | null;
  overrides?: Record<string, unknown>;
}

export class PresetConflictError extends Error {
  code = "PRESET_NAME_TAKEN" as const;
  presetName: string;

  constructor(name: string, message?: string) {
    super(message ?? "Preset name already exists");
    this.presetName = name;
  }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function handleResponse<T>(res: Response): Promise<T> {
  if (res.status === 409) {
    const body = await res.json();
    throw new PresetConflictError(
      body.detail?.name ?? "",
      body.detail?.message ?? "Preset name already exists",
    );
  }
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API error ${res.status}: ${text}`);
  }
  return res.json();
}

// ---------------------------------------------------------------------------
// API functions
// ---------------------------------------------------------------------------

export async function fetchDefaults(): Promise<Record<string, unknown>> {
  const res = await fetch(`${API_BASE}/config/defaults`);
  if (!res.ok) throw new Error("Failed to fetch defaults");
  return res.json();
}

export async function fetchPresets(): Promise<PresetResponse[]> {
  const res = await fetch(`${API_BASE}/presets`);
  if (!res.ok) throw new Error("Failed to fetch presets");
  return res.json();
}

export async function createPreset(data: PresetCreatePayload): Promise<PresetResponse> {
  const res = await fetch(`${API_BASE}/presets`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  return handleResponse<PresetResponse>(res);
}

export async function updatePreset(
  id: string,
  data: PresetUpdatePayload,
): Promise<PresetResponse> {
  const res = await fetch(`${API_BASE}/presets/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  return handleResponse<PresetResponse>(res);
}

export async function deletePreset(id: string): Promise<void> {
  const res = await fetch(`${API_BASE}/presets/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error("Failed to delete preset");
}

export async function importPreset(
  data: Record<string, unknown>,
): Promise<PresetResponse> {
  // Strip fields the import endpoint doesn't accept
  const { id: _id, createdAt: _c, updatedAt: _u, ...payload } = data as Record<string, unknown> & {
    id?: unknown;
    createdAt?: unknown;
    updatedAt?: unknown;
  };

  const res = await fetch(`${API_BASE}/presets/import`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handleResponse<PresetResponse>(res);
}
