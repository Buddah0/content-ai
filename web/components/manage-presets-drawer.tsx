"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { type PresetResponse } from "@/lib/presets-api";
import {
  X,
  Search,
  Play,
  Pencil,
  Download,
  Trash2,
  Check,
  Upload,
  FileJson,
  Loader2,
  AlertCircle,
} from "lucide-react";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface ManagePresetsDrawerProps {
  open: boolean;
  onClose: () => void;
  presets: PresetResponse[];
  selectedPresetId: string | null;
  onApplyPreset: (id: string) => void;
  onRenamePreset: (id: string, newName: string) => Promise<{ error?: string }>;
  onDeletePreset: (id: string) => Promise<void>;
  onExportPreset: (preset: PresetResponse) => void;
  onImportPreset: (data: Record<string, unknown>) => Promise<{ preset?: PresetResponse; error?: string }>;
}

// ---------------------------------------------------------------------------
// Download helper
// ---------------------------------------------------------------------------

export function downloadPresetJson(preset: PresetResponse) {
  const exportData = {
    id: preset.id,
    name: preset.name,
    description: preset.description,
    overrides: preset.overrides,
    schema_version: preset.schema_version,
    createdAt: preset.createdAt,
    updatedAt: preset.updatedAt,
  };
  const json = JSON.stringify(exportData, null, 2);
  const blob = new Blob([json], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `preset-${preset.name.toLowerCase().replace(/\s+/g, "-")}.json`;
  a.click();
  URL.revokeObjectURL(url);
}

// ---------------------------------------------------------------------------
// Preset Row (with inline rename + delete confirm)
// ---------------------------------------------------------------------------

function PresetRow({
  preset,
  isSelected,
  onApply,
  onRename,
  onExport,
  onDelete,
}: {
  preset: PresetResponse;
  isSelected: boolean;
  onApply: () => void;
  onRename: (newName: string) => Promise<{ error?: string }>;
  onExport: () => void;
  onDelete: () => Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  const [editName, setEditName] = useState(preset.name);
  const [renameError, setRenameError] = useState<string | null>(null);
  const [renaming, setRenaming] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const editRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editing) {
      setEditName(preset.name);
      setRenameError(null);
      setTimeout(() => editRef.current?.focus(), 50);
    }
  }, [editing, preset.name]);

  const handleRename = async () => {
    const trimmed = editName.trim();
    if (!trimmed) {
      setRenameError("Name is required");
      return;
    }
    if (trimmed === preset.name) {
      setEditing(false);
      return;
    }
    setRenaming(true);
    const result = await onRename(trimmed);
    setRenaming(false);
    if (result.error) {
      setRenameError(result.error);
      editRef.current?.focus();
    } else {
      setEditing(false);
    }
  };

  const handleDelete = async () => {
    setDeleting(true);
    await onDelete();
    setDeleting(false);
    setConfirmDelete(false);
  };

  return (
    <div
      className={`p-3 rounded-md border transition-colors ${
        isSelected
          ? "border-l-2 border-l-neon-blue border-glass-border bg-neon-blue/5"
          : "border-glass-border bg-glass/20 hover:bg-glass/30"
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        {/* Name + description */}
        <div className="flex-1 min-w-0">
          {editing ? (
            <div className="space-y-1">
              <div className="flex items-center gap-1">
                <input
                  ref={editRef}
                  type="text"
                  value={editName}
                  onChange={(e) => { setEditName(e.target.value); setRenameError(null); }}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") handleRename();
                    if (e.key === "Escape") setEditing(false);
                  }}
                  className={`flex-1 bg-glass/60 border rounded px-2 py-1 text-sm focus:outline-none ${
                    renameError ? "border-red-500/50" : "border-glass-border focus:border-neon-blue"
                  }`}
                  disabled={renaming}
                />
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleRename}
                  disabled={renaming}
                  className="h-7 w-7 p-0"
                >
                  {renaming ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <Check className="w-3.5 h-3.5 text-green-400" />
                  )}
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setEditing(false)}
                  disabled={renaming}
                  className="h-7 w-7 p-0"
                >
                  <X className="w-3.5 h-3.5" />
                </Button>
              </div>
              {renameError && (
                <p className="text-red-400 text-xs">{renameError}</p>
              )}
            </div>
          ) : (
            <>
              <p className="font-medium text-sm truncate">{preset.name}</p>
              {preset.description && (
                <p className="text-xs text-muted-foreground truncate">
                  {preset.description}
                </p>
              )}
            </>
          )}
        </div>

        {/* Row actions */}
        {!editing && (
          <div className="flex items-center gap-1 shrink-0">
            <Button
              variant="ghost"
              size="sm"
              onClick={onApply}
              className="h-7 w-7 p-0"
              title="Apply"
            >
              <Play className="w-3.5 h-3.5" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setEditing(true)}
              className="h-7 w-7 p-0"
              title="Rename"
            >
              <Pencil className="w-3.5 h-3.5" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={onExport}
              className="h-7 w-7 p-0"
              title="Export"
            >
              <Download className="w-3.5 h-3.5" />
            </Button>
            {confirmDelete ? (
              <div className="flex items-center gap-1">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleDelete}
                  disabled={deleting}
                  className="h-7 px-2 text-xs text-red-400 hover:text-red-300 hover:bg-red-500/10"
                >
                  {deleting ? <Loader2 className="w-3 h-3 animate-spin" /> : "Yes"}
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setConfirmDelete(false)}
                  disabled={deleting}
                  className="h-7 px-2 text-xs"
                >
                  No
                </Button>
              </div>
            ) : (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setConfirmDelete(true)}
                className="h-7 w-7 p-0 hover:text-red-400"
                title="Delete"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </Button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Import Section
// ---------------------------------------------------------------------------

function ImportSection({
  onImport,
}: {
  onImport: (data: Record<string, unknown>) => Promise<{ preset?: PresetResponse; error?: string }>;
}) {
  const [pasteJson, setPasteJson] = useState("");
  const [importError, setImportError] = useState<string | null>(null);
  const [importName, setImportName] = useState<string | null>(null);
  const [importing, setImporting] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const doImport = async (raw: unknown) => {
    if (!raw || typeof raw !== "object" || Array.isArray(raw)) {
      setImportError("Invalid JSON: expected an object with name and overrides");
      return;
    }

    const data = raw as Record<string, unknown>;
    if (!data.name || typeof data.name !== "string") {
      setImportError("Invalid preset: missing 'name' field");
      return;
    }

    // If we have a rename override from a previous 409
    if (importName !== null) {
      data.name = importName;
    }

    setImporting(true);
    setImportError(null);

    const result = await onImport(data);

    setImporting(false);

    if (result.error) {
      setImportError(result.error);
      // Pre-fill rename field with the conflicting name
      setImportName(data.name as string);
    } else {
      // Success — clear everything
      setPasteJson("");
      setImportError(null);
      setImportName(null);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    try {
      const text = await file.text();
      const parsed = JSON.parse(text);
      setPasteJson(text);
      setImportName(null);
      setImportError(null);
      await doImport(parsed);
    } catch {
      setImportError("Failed to parse JSON file");
    }
  };

  const handlePasteImport = async () => {
    if (!pasteJson.trim()) {
      setImportError("Paste JSON content first");
      return;
    }

    try {
      const parsed = JSON.parse(pasteJson);
      await doImport(parsed);
    } catch {
      setImportError("Invalid JSON syntax");
    }
  };

  return (
    <div className="space-y-3">
      <Label className="text-xs text-muted-foreground uppercase tracking-wider">
        Import Preset
      </Label>

      {/* File upload */}
      <div className="flex items-center gap-2">
        <input
          ref={fileRef}
          type="file"
          accept=".json"
          onChange={handleFileUpload}
          className="hidden"
          id="preset-file-import"
        />
        <Button
          variant="outline"
          size="sm"
          onClick={() => fileRef.current?.click()}
          className="border-glass-border hover:bg-glass/40"
          disabled={importing}
        >
          <Upload className="w-3.5 h-3.5 mr-1.5" />
          Upload .json
        </Button>
      </div>

      {/* Paste JSON */}
      <textarea
        value={pasteJson}
        onChange={(e) => { setPasteJson(e.target.value); setImportError(null); setImportName(null); }}
        placeholder='{"name": "...", "overrides": {...}}'
        rows={4}
        className="w-full bg-glass/60 border border-glass-border rounded-md px-3 py-2 text-xs font-mono focus:border-neon-blue focus:outline-none resize-none"
      />

      {/* Rename on 409 */}
      {importName !== null && importError && (
        <div className="space-y-1">
          <Label className="text-xs">Rename before retry:</Label>
          <input
            type="text"
            value={importName}
            onChange={(e) => { setImportName(e.target.value); setImportError(null); }}
            className="w-full bg-glass/60 border border-amber-500/30 rounded-md px-3 py-1.5 text-sm focus:border-neon-blue focus:outline-none"
          />
        </div>
      )}

      {/* Error */}
      {importError && (
        <div className="flex items-center gap-2 text-red-400 text-xs">
          <AlertCircle className="w-3.5 h-3.5 shrink-0" />
          {importError}
        </div>
      )}

      <Button
        variant="outline"
        size="sm"
        onClick={handlePasteImport}
        disabled={importing || !pasteJson.trim()}
        className="w-full border-neon-blue/30 hover:bg-neon-blue/10"
      >
        {importing ? (
          <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
        ) : (
          <FileJson className="w-3.5 h-3.5 mr-1.5" />
        )}
        Import
      </Button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Drawer
// ---------------------------------------------------------------------------

export function ManagePresetsDrawer({
  open,
  onClose,
  presets,
  selectedPresetId,
  onApplyPreset,
  onRenamePreset,
  onDeletePreset,
  onExportPreset,
  onImportPreset,
}: ManagePresetsDrawerProps) {
  const [search, setSearch] = useState("");

  // Reset search when drawer opens
  useEffect(() => {
    if (open) setSearch("");
  }, [open]);

  // Handle escape key
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, onClose]);

  const filtered = presets.filter((p) => {
    if (!search.trim()) return true;
    const q = search.toLowerCase();
    return (
      p.name.toLowerCase().includes(q) ||
      (p.description?.toLowerCase().includes(q) ?? false)
    );
  });

  return (
    <>
      {/* Overlay */}
      {open && (
        <div
          className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50"
          onClick={onClose}
        />
      )}

      {/* Panel */}
      <div
        className={`fixed top-0 right-0 h-full w-full max-w-md bg-glass/95 backdrop-blur-md border-l border-glass-border shadow-2xl z-50 transition-transform duration-300 ease-in-out ${
          open ? "translate-x-0" : "translate-x-full"
        }`}
      >
        <div className="flex flex-col h-full">
          {/* Header */}
          <div className="flex items-center justify-between p-4 border-b border-glass-border">
            <h2 className="text-lg font-semibold text-neon-blue">
              Manage Presets
            </h2>
            <Button
              variant="ghost"
              size="sm"
              onClick={onClose}
              className="h-8 w-8 p-0"
            >
              <X className="w-4 h-4" />
            </Button>
          </div>

          {/* Search */}
          <div className="p-4 pb-2">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search presets..."
                className="w-full bg-glass/60 border border-glass-border rounded-md pl-9 pr-3 py-2 text-sm focus:border-neon-blue focus:outline-none"
              />
            </div>
          </div>

          {/* Preset list */}
          <div className="flex-1 overflow-y-auto px-4 pb-2 space-y-2">
            {filtered.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-8">
                {presets.length === 0
                  ? "No presets yet. Save one from the generator."
                  : "No presets match your search."}
              </p>
            ) : (
              filtered.map((preset) => (
                <PresetRow
                  key={preset.id}
                  preset={preset}
                  isSelected={preset.id === selectedPresetId}
                  onApply={() => {
                    onApplyPreset(preset.id);
                    onClose();
                  }}
                  onRename={(newName) => onRenamePreset(preset.id, newName)}
                  onExport={() => onExportPreset(preset)}
                  onDelete={() => onDeletePreset(preset.id)}
                />
              ))
            )}
          </div>

          {/* Divider + Import */}
          <div className="border-t border-glass-border p-4">
            <ImportSection onImport={onImportPreset} />
          </div>
        </div>
      </div>
    </>
  );
}
