/**
 * PRESET_KEYS: single source of truth for the mapping between flat UI state
 * keys and nested backend config keys. Presets only control these 4 values.
 */

// ---------------------------------------------------------------------------
// Constants & Types
// ---------------------------------------------------------------------------

export const PRESET_KEYS = [
  {
    uiKey: "rmsThreshold" as const,
    backendPath: ["detection", "rms_threshold"] as const,
    label: "Sensitivity (RMS Threshold)",
    slider: { min: 0.01, max: 0.5, step: 0.01 },
    format: (v: number) => v.toFixed(2),
    helperText: "Lower = more events, Higher = only loud peaks.",
  },
  {
    uiKey: "maxSegmentDuration" as const,
    backendPath: ["processing", "max_segment_duration_s"] as const,
    label: "Max Clip Duration (s)",
    slider: { min: 2, max: 30, step: 1 },
    format: (v: number) => `${v}s`,
    helperText: "Maximum duration for any single merged segment.",
  },
  {
    uiKey: "contextPadding" as const,
    backendPath: ["processing", "context_padding_s"] as const,
    label: "Context Padding (s)",
    slider: { min: 0, max: 5, step: 0.1 },
    format: (v: number) => `${v.toFixed(1)}s`,
    helperText: "Extra padding before and after each detected event.",
  },
  {
    uiKey: "mergeGap" as const,
    backendPath: ["processing", "merge_gap_s"] as const,
    label: "Merge Gap (s)",
    slider: { min: 0, max: 10, step: 0.5 },
    format: (v: number) => `${v.toFixed(1)}s`,
    helperText: "Segments closer than this gap are merged together.",
  },
] as const;

/** The flat-key names used in UI state. */
export type PresetKeyId = (typeof PRESET_KEYS)[number]["uiKey"];

/** Flat shape containing only the 4 preset-controlled values. */
export interface PresetSettings {
  rmsThreshold: number;
  maxSegmentDuration: number;
  contextPadding: number;
  mergeGap: number;
}

/** Full generator settings including frontend-only toggles. */
export interface GeneratorSettings extends PresetSettings {
  showCaptions: boolean;
  showWatermark: boolean;
}

// ---------------------------------------------------------------------------
// Helpers: navigate nested backend dicts by path
// ---------------------------------------------------------------------------

function getByPath(obj: Record<string, unknown>, path: readonly string[]): unknown {
  let cur: unknown = obj;
  for (const key of path) {
    if (cur == null || typeof cur !== "object") return undefined;
    cur = (cur as Record<string, unknown>)[key];
  }
  return cur;
}

function setByPath(obj: Record<string, unknown>, path: readonly string[], value: unknown) {
  let cur = obj;
  for (let i = 0; i < path.length - 1; i++) {
    const key = path[i];
    if (!(key in cur) || typeof cur[key] !== "object" || cur[key] == null) {
      cur[key] = {};
    }
    cur = cur[key] as Record<string, unknown>;
  }
  cur[path[path.length - 1]] = value;
}

// ---------------------------------------------------------------------------
// Public utilities
// ---------------------------------------------------------------------------

/** Extract the 4 preset values from a full defaults dict into flat UI shape. */
export function extractPresetValues(defaults: Record<string, unknown>): PresetSettings {
  return {
    rmsThreshold: (getByPath(defaults, PRESET_KEYS[0].backendPath) as number) ?? 0.1,
    maxSegmentDuration: (getByPath(defaults, PRESET_KEYS[1].backendPath) as number) ?? 10,
    contextPadding: (getByPath(defaults, PRESET_KEYS[2].backendPath) as number) ?? 1.0,
    mergeGap: (getByPath(defaults, PRESET_KEYS[3].backendPath) as number) ?? 2.0,
  };
}

/**
 * Apply preset overrides (nested backend format) on top of defaults,
 * then extract the 4 preset values into flat UI shape.
 * This produces the "baseline" for dirty comparison.
 */
export function resolveBaseline(
  defaults: Record<string, unknown>,
  overrides: Record<string, unknown>,
): PresetSettings {
  // Simple RFC-7396-style merge for the keys we care about
  const result = extractPresetValues(defaults);

  for (const key of PRESET_KEYS) {
    const overrideVal = getByPath(overrides, key.backendPath);
    if (overrideVal !== undefined) {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (result as any)[key.uiKey] = overrideVal as number;
    }
  }

  return result;
}

/**
 * Compute overrides-only (diff vs defaults) restricted to PRESET_KEYS.
 * Returns a nested dict suitable for POST/PATCH to the backend.
 * Keys matching defaults are omitted.
 */
export function computeOverridesOnly(
  current: PresetSettings,
  defaults: Record<string, unknown>,
): Record<string, unknown> {
  const overrides: Record<string, unknown> = {};
  const defaultVals = extractPresetValues(defaults);

  for (const key of PRESET_KEYS) {
    const curVal = current[key.uiKey];
    const defVal = defaultVals[key.uiKey];
    if (curVal !== defVal) {
      setByPath(overrides, key.backendPath, curVal);
    }
  }

  return overrides;
}

/** Strict equality check across all 4 preset keys. */
export function isPresetDirty(baseline: PresetSettings, current: PresetSettings): boolean {
  return PRESET_KEYS.some((key) => baseline[key.uiKey] !== current[key.uiKey]);
}

/** Convert flat GeneratorSettings to the nested backend format for job creation. */
export function settingsToBackendFormat(settings: GeneratorSettings): Record<string, unknown> {
  return {
    detection: { rms_threshold: settings.rmsThreshold },
    processing: {
      max_segment_duration_s: settings.maxSegmentDuration,
      context_padding_s: settings.contextPadding,
      merge_gap_s: settings.mergeGap,
    },
    showCaptions: settings.showCaptions,
    showWatermark: settings.showWatermark,
  };
}
