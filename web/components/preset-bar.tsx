"use client";

import React from "react";
import { Button } from "@/components/ui/button";
import { type PresetResponse } from "@/lib/presets-api";
import { RotateCcw, Save, RefreshCw, Settings2 } from "lucide-react";

interface PresetBarProps {
  presets: PresetResponse[];
  selectedPreset: PresetResponse | null;
  isDirty: boolean;
  onSelectPreset: (id: string | null) => void;
  onSaveAs: () => void;
  onUpdate: () => void;
  onManage: () => void;
  onResetToDefaults: () => void;
}

export function PresetBar({
  presets,
  selectedPreset,
  isDirty,
  onSelectPreset,
  onSaveAs,
  onUpdate,
  onManage,
  onResetToDefaults,
}: PresetBarProps) {
  return (
    <div className="flex flex-wrap items-center gap-3 p-3 rounded-lg border border-glass-border bg-glass/30 backdrop-blur-sm">
      {/* Dropdown */}
      <select
        value={selectedPreset?.id ?? ""}
        onChange={(e) => onSelectPreset(e.target.value || null)}
        className="bg-glass/60 border border-glass-border rounded-md px-3 py-1.5 text-sm focus:border-neon-blue focus:outline-none min-w-[160px]"
      >
        <option value="">No preset</option>
        {presets.map((p) => (
          <option key={p.id} value={p.id}>
            {p.name}
          </option>
        ))}
      </select>

      {/* Status badges */}
      <div className="flex items-center gap-2 flex-1 min-w-0">
        {selectedPreset ? (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-neon-blue/10 text-neon-blue border border-neon-blue/30 truncate max-w-[200px]">
            Preset: {selectedPreset.name}
          </span>
        ) : (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-muted/30 text-muted-foreground border border-glass-border">
            Custom
          </span>
        )}

        {isDirty && (
          <>
            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-500/10 text-amber-400 border border-amber-500/30 whitespace-nowrap">
              Unsaved changes
            </span>
            <Button
              variant="ghost"
              size="sm"
              onClick={onResetToDefaults}
              className="h-7 px-2 text-xs text-muted-foreground hover:text-foreground"
            >
              <RotateCcw className="w-3 h-3 mr-1" />
              Reset
            </Button>
          </>
        )}
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2">
        <Button
          variant="outline"
          size="sm"
          onClick={onSaveAs}
          className="border-neon-blue/30 hover:bg-neon-blue/10"
        >
          <Save className="w-3.5 h-3.5 mr-1.5" />
          Save As...
        </Button>

        {selectedPreset && isDirty && (
          <Button
            variant="outline"
            size="sm"
            onClick={onUpdate}
            className="border-neon-purple/30 hover:bg-neon-purple/10"
          >
            <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
            Update
          </Button>
        )}

        <Button
          variant="ghost"
          size="sm"
          onClick={onManage}
          className="hover:bg-glass/60"
          title="Manage Presets"
        >
          <Settings2 className="w-4 h-4" />
        </Button>
      </div>
    </div>
  );
}
