"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  type PresetSettings,
  extractPresetValues,
  resolveBaseline,
  computeOverridesOnly,
  isPresetDirty,
} from "@/lib/preset-keys";
import {
  type PresetResponse,
  PresetConflictError,
  fetchDefaults,
  fetchPresets as apiFetchPresets,
  createPreset,
  updatePreset as apiUpdatePreset,
  deletePreset as apiDeletePreset,
  importPreset as apiImportPreset,
} from "@/lib/presets-api";

// ---------------------------------------------------------------------------
// Return type
// ---------------------------------------------------------------------------

export interface UsePresetsReturn {
  defaults: Record<string, unknown>;
  presets: PresetResponse[];
  selectedPreset: PresetResponse | null;
  selectedPresetId: string | null;
  baseline: PresetSettings;
  loading: boolean;

  isDirty: (current: PresetSettings) => boolean;
  selectPreset: (id: string | null) => PresetSettings;
  saveAs: (
    name: string,
    description: string,
    currentSettings: PresetSettings,
  ) => Promise<{ preset?: PresetResponse; error?: string }>;
  updatePreset: (
    currentSettings: PresetSettings,
  ) => Promise<{ error?: string }>;
  deletePreset: (id: string) => Promise<void>;
  renamePreset: (id: string, newName: string) => Promise<{ error?: string }>;
  importPreset: (jsonData: Record<string, unknown>) => Promise<{ preset?: PresetResponse; error?: string }>;
  getExportData: (id: string) => PresetResponse | null;
  refreshPresets: () => Promise<void>;
  resetBaseline: (settings: PresetSettings) => void;
}

// ---------------------------------------------------------------------------
// Default PresetSettings (fallback before backend loads)
// ---------------------------------------------------------------------------

const DEFAULT_PRESET_SETTINGS: PresetSettings = {
  rmsThreshold: 0.1,
  maxSegmentDuration: 10,
  contextPadding: 1.0,
  mergeGap: 2.0,
};

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function usePresets(): UsePresetsReturn {
  const [defaults, setDefaults] = useState<Record<string, unknown>>({});
  const [presets, setPresets] = useState<PresetResponse[]>([]);
  const [selectedPresetId, setSelectedPresetId] = useState<string | null>(null);
  const [baseline, setBaseline] = useState<PresetSettings>(DEFAULT_PRESET_SETTINGS);
  const [loading, setLoading] = useState(true);

  // Keep a ref to defaults so callbacks don't go stale
  const defaultsRef = useRef(defaults);
  defaultsRef.current = defaults;

  const presetsRef = useRef(presets);
  presetsRef.current = presets;

  // -----------------------------------------------------------------------
  // Init: fetch defaults + presets on mount
  // -----------------------------------------------------------------------

  useEffect(() => {
    let cancelled = false;

    async function init() {
      try {
        const [defs, presetList] = await Promise.all([
          fetchDefaults(),
          apiFetchPresets(),
        ]);

        if (cancelled) return;

        setDefaults(defs);
        setPresets(presetList);
        setBaseline(extractPresetValues(defs));
      } catch (e) {
        console.error("Failed to initialize presets:", e);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    init();
    return () => { cancelled = true; };
  }, []);

  // -----------------------------------------------------------------------
  // Derived
  // -----------------------------------------------------------------------

  const selectedPreset = presets.find((p) => p.id === selectedPresetId) ?? null;

  // -----------------------------------------------------------------------
  // Actions
  // -----------------------------------------------------------------------

  const isDirty = useCallback(
    (current: PresetSettings) => isPresetDirty(baseline, current),
    [baseline],
  );

  const selectPreset = useCallback(
    (id: string | null): PresetSettings => {
      setSelectedPresetId(id);

      if (!id) {
        const vals = extractPresetValues(defaultsRef.current);
        setBaseline(vals);
        return vals;
      }

      const preset = presetsRef.current.find((p) => p.id === id);
      if (!preset) {
        const vals = extractPresetValues(defaultsRef.current);
        setBaseline(vals);
        return vals;
      }

      const vals = resolveBaseline(defaultsRef.current, preset.overrides);
      setBaseline(vals);
      return vals;
    },
    [],
  );

  const saveAs = useCallback(
    async (
      name: string,
      description: string,
      currentSettings: PresetSettings,
    ): Promise<{ preset?: PresetResponse; error?: string }> => {
      const overrides = computeOverridesOnly(currentSettings, defaultsRef.current);

      try {
        const preset = await createPreset({
          name: name.trim(),
          description: description.trim() || null,
          overrides,
        });

        setPresets((prev) => [...prev, preset]);
        setSelectedPresetId(preset.id);
        setBaseline(currentSettings);

        return { preset };
      } catch (e) {
        if (e instanceof PresetConflictError) {
          return { error: e.message };
        }
        console.error("Failed to save preset:", e);
        return { error: "Failed to save preset" };
      }
    },
    [],
  );

  const updatePresetAction = useCallback(
    async (currentSettings: PresetSettings): Promise<{ error?: string }> => {
      const id = selectedPresetId;
      if (!id) return { error: "No preset selected" };

      const overrides = computeOverridesOnly(currentSettings, defaultsRef.current);

      try {
        const updated = await apiUpdatePreset(id, { overrides });

        setPresets((prev) =>
          prev.map((p) => (p.id === id ? updated : p)),
        );
        setBaseline(currentSettings);

        return {};
      } catch (e) {
        if (e instanceof PresetConflictError) {
          return { error: e.message };
        }
        console.error("Failed to update preset:", e);
        return { error: "Failed to update preset" };
      }
    },
    [selectedPresetId],
  );

  const deletePresetAction = useCallback(async (id: string) => {
    await apiDeletePreset(id);
    setPresets((prev) => prev.filter((p) => p.id !== id));
    setSelectedPresetId((prev) => (prev === id ? null : prev));
    // If the deleted preset was selected, reset baseline to defaults
    if (selectedPresetId === id) {
      setBaseline(extractPresetValues(defaultsRef.current));
    }
  }, [selectedPresetId]);

  const renamePreset = useCallback(
    async (id: string, newName: string): Promise<{ error?: string }> => {
      try {
        const updated = await apiUpdatePreset(id, { name: newName.trim() });
        setPresets((prev) =>
          prev.map((p) => (p.id === id ? updated : p)),
        );
        return {};
      } catch (e) {
        if (e instanceof PresetConflictError) {
          return { error: e.message };
        }
        console.error("Failed to rename preset:", e);
        return { error: "Failed to rename preset" };
      }
    },
    [],
  );

  const importPresetAction = useCallback(
    async (jsonData: Record<string, unknown>): Promise<{ preset?: PresetResponse; error?: string }> => {
      try {
        const preset = await apiImportPreset(jsonData);
        setPresets((prev) => [...prev, preset]);
        return { preset };
      } catch (e) {
        if (e instanceof PresetConflictError) {
          return { error: e.message };
        }
        console.error("Failed to import preset:", e);
        return { error: "Failed to import preset" };
      }
    },
    [],
  );

  const getExportData = useCallback(
    (id: string): PresetResponse | null => {
      return presetsRef.current.find((p) => p.id === id) ?? null;
    },
    [],
  );

  const refreshPresets = useCallback(async () => {
    try {
      const list = await apiFetchPresets();
      setPresets(list);
    } catch (e) {
      console.error("Failed to refresh presets:", e);
    }
  }, []);

  const resetBaseline = useCallback((settings: PresetSettings) => {
    setBaseline(settings);
  }, []);

  return {
    defaults,
    presets,
    selectedPreset,
    selectedPresetId,
    baseline,
    loading,
    isDirty,
    selectPreset,
    saveAs,
    updatePreset: updatePresetAction,
    deletePreset: deletePresetAction,
    renamePreset,
    importPreset: importPresetAction,
    getExportData,
    refreshPresets,
    resetBaseline,
  };
}
