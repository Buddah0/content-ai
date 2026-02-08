"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Loader2 } from "lucide-react";

interface SavePresetDialogProps {
  open: boolean;
  onClose: () => void;
  onSave: (name: string, description: string) => Promise<{ error?: string }>;
  initialName?: string;
}

export function SavePresetDialog({
  open,
  onClose,
  onSave,
  initialName = "",
}: SavePresetDialogProps) {
  const [name, setName] = useState(initialName);
  const [description, setDescription] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const nameRef = useRef<HTMLInputElement>(null);

  // Reset state when dialog opens
  useEffect(() => {
    if (open) {
      setName(initialName);
      setDescription("");
      setError(null);
      setSaving(false);
      // Focus name input after mount
      setTimeout(() => nameRef.current?.focus(), 50);
    }
  }, [open, initialName]);

  const handleSave = useCallback(async () => {
    const trimmed = name.trim();
    if (!trimmed) {
      setError("Preset name is required");
      nameRef.current?.focus();
      return;
    }

    setSaving(true);
    setError(null);

    const result = await onSave(trimmed, description);

    setSaving(false);

    if (result.error) {
      setError(result.error);
      nameRef.current?.focus();
    } else {
      onClose();
    }
  }, [name, description, onSave, onClose]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      } else if (e.key === "Enter" && !saving) {
        e.preventDefault();
        handleSave();
      }
    },
    [onClose, handleSave, saving],
  );

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
      onKeyDown={handleKeyDown}
    >
      <Card className="w-full max-w-md border-glass-border bg-glass/90 backdrop-blur-md shadow-2xl">
        <CardHeader>
          <CardTitle className="text-neon-blue">Save Preset</CardTitle>
          <CardDescription>Save your current settings as a reusable preset.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label>Preset Name *</Label>
            <input
              ref={nameRef}
              type="text"
              value={name}
              onChange={(e) => { setName(e.target.value); setError(null); }}
              placeholder="e.g., High Energy Clips"
              className={`w-full bg-glass/60 border rounded-md px-3 py-2 text-sm focus:outline-none transition-colors ${
                error
                  ? "border-red-500/50 focus:border-red-500"
                  : "border-glass-border focus:border-neon-blue"
              }`}
            />
            {error && (
              <p className="text-red-400 text-xs">{error}</p>
            )}
          </div>
          <div className="space-y-2">
            <Label>Description (optional)</Label>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="e.g., Optimized for action-packed content"
              className="w-full bg-glass/60 border border-glass-border rounded-md px-3 py-2 text-sm focus:border-neon-blue focus:outline-none"
            />
          </div>
        </CardContent>
        <div className="p-6 pt-0 flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button
            onClick={handleSave}
            disabled={saving}
            className="bg-gradient-to-r from-neon-blue to-neon-purple"
          >
            {saving && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
            Save
          </Button>
        </div>
      </Card>
    </div>
  );
}
