"use client"

import React, { useState, useEffect } from 'react';
import { useSearchParams } from 'next/navigation';
import { UploadZone } from '@/components/upload-zone';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { Slider } from '@/components/ui/slider';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { Download, ArrowRight, Loader2 } from 'lucide-react';

import { usePresets } from '@/hooks/use-presets';
import { PresetBar } from '@/components/preset-bar';
import { SavePresetDialog } from '@/components/save-preset-dialog';
import { ManagePresetsDrawer, downloadPresetJson } from '@/components/manage-presets-drawer';
import { type GeneratorSettings, type PresetSettings, extractPresetValues, settingsToBackendFormat } from '@/lib/preset-keys';

const API_BASE = "http://localhost:8000";

type Step = 'upload' | 'settings' | 'processing' | 'result';

export default function GeneratorPage() {
    const searchParams = useSearchParams();
    const [step, setStep] = useState<Step>('upload');
    const [file, setFile] = useState<File | null>(null);
    const [assetId, setAssetId] = useState<string | null>(null);
    const [jobId, setJobId] = useState<string | null>(searchParams.get('jobId'));
    const [progress, setProgress] = useState(0);
    const [status, setStatus] = useState("PENDING");
    const [outputs, setOutputs] = useState<{ type: string, path: string }[]>([]);
    const [segments, setSegments] = useState<{ startTime: number, endTime: number }[]>([]);

    // Settings state (flat UI shape)
    const [settings, setSettings] = useState<GeneratorSettings>({
        rmsThreshold: 0.1,
        maxSegmentDuration: 10,
        contextPadding: 1.0,
        mergeGap: 2.0,
        showCaptions: true,
        showWatermark: true,
    });

    // Preset hook
    const presetHook = usePresets();

    // Dialog/drawer state
    const [showSaveDialog, setShowSaveDialog] = useState(false);
    const [showManageDrawer, setShowManageDrawer] = useState(false);

    // Sync defaults into settings when loaded
    useEffect(() => {
        if (!presetHook.loading && Object.keys(presetHook.defaults).length > 0) {
            const defaultVals = extractPresetValues(presetHook.defaults);
            setSettings(prev => ({ ...prev, ...defaultVals }));
        }
    }, [presetHook.loading, presetHook.defaults]);

    // If jobId is in URL, fetch results immediately
    useEffect(() => {
        const id = searchParams.get('jobId');
        if (id) {
            setJobId(id);
            fetchResultsInternal(id);
        }
    }, [searchParams]);

    // -----------------------------------------------------------------------
    // Preset helpers
    // -----------------------------------------------------------------------

    const currentPresetSettings: PresetSettings = {
        rmsThreshold: settings.rmsThreshold,
        maxSegmentDuration: settings.maxSegmentDuration,
        contextPadding: settings.contextPadding,
        mergeGap: settings.mergeGap,
    };

    const dirty = presetHook.isDirty(currentPresetSettings);

    const handlePresetSelect = (id: string | null) => {
        const newVals = presetHook.selectPreset(id);
        setSettings(prev => ({ ...prev, ...newVals }));
    };

    const handleResetToBaseline = () => {
        setSettings(prev => ({ ...prev, ...presetHook.baseline }));
    };

    const handleUpdate = async () => {
        await presetHook.updatePreset(currentPresetSettings);
    };

    // -----------------------------------------------------------------------
    // Upload & Job
    // -----------------------------------------------------------------------

    const handleUpload = async () => {
        if (!file) return;
        try {
            setStep('settings');
            const formData = new FormData();
            formData.append('file', file);

            const res = await fetch(`${API_BASE}/upload`, {
                method: 'POST',
                body: formData
            });

            if (!res.ok) throw new Error("Upload failed");

            const data = await res.json();
            setAssetId(data.assetId);
        } catch (e) {
            console.error(e);
            alert("Upload failed");
            setStep('upload');
        }
    };

    const handleStartJob = async () => {
        if (!assetId) return;
        try {
            const backendSettings = settingsToBackendFormat(settings);
            const res = await fetch(`${API_BASE}/jobs`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    assetId,
                    settings: backendSettings,
                    presetId: presetHook.selectedPresetId
                })
            });
            const data = await res.json();
            setJobId(data.id);
            setStep('processing');
        } catch (e) {
            console.error(e);
            alert("Failed to start job");
        }
    };

    // -----------------------------------------------------------------------
    // SSE + Results
    // -----------------------------------------------------------------------

    useEffect(() => {
        if (step === 'processing' && jobId) {
            const evtSource = new EventSource(`${API_BASE}/jobs/${jobId}/events`);

            evtSource.onmessage = (e) => {
                const data = JSON.parse(e.data);
                setStatus(data.status);
                setProgress(data.progress);

                if (data.status === 'COMPLETED') {
                    evtSource.close();
                    fetchResults();
                }
                if (data.status === 'FAILED') {
                    evtSource.close();
                }
            };

            return () => {
                evtSource.close();
            }
        }
    }, [step, jobId]);

    const fetchResults = async () => {
        if (!jobId) return;
        fetchResultsInternal(jobId);
    };

    const fetchResultsInternal = async (id: string) => {
        const res = await fetch(`${API_BASE}/jobs/${id}`);
        if (!res.ok) return;
        const data = await res.json();
        setOutputs(data.outputs);
        setSegments(data.segments);
        setStep('result');
    };

    // -----------------------------------------------------------------------
    // Render
    // -----------------------------------------------------------------------

    return (
        <>
            <div className="container mx-auto max-w-4xl py-12 px-4 space-y-8">
                <div className="flex items-center justify-between">
                    <div>
                        <h1 className="text-3xl font-bold tracking-tight bg-gradient-to-r from-foreground to-foreground/70 bg-clip-text text-transparent">Mission Control</h1>
                        <p className="text-muted-foreground">Generate creator-ready highlights.</p>
                    </div>
                </div>

                {/* STEPS */}
                {step === 'upload' && (
                    <div className="space-y-6">
                        <UploadZone
                            onFileSelect={setFile}
                            selectedFile={file}
                            onClear={() => setFile(null)}
                        />
                        <div className="flex justify-end">
                            <Button size="lg" disabled={!file} onClick={handleUpload}>
                                Continue <ArrowRight className="ml-2 w-4 h-4" />
                            </Button>
                        </div>
                    </div>
                )}

                {step === 'settings' && (
                    <Card className="border-glass-border bg-glass/40 backdrop-blur-sm shadow-inner-glow">
                        <CardHeader>
                            <CardTitle className="text-neon-blue">Configuration</CardTitle>
                            <CardDescription>Customize your output generation.</CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-6">
                            {/* Preset Bar */}
                            <PresetBar
                                presets={presetHook.presets}
                                selectedPreset={presetHook.selectedPreset}
                                isDirty={dirty}
                                onSelectPreset={handlePresetSelect}
                                onSaveAs={() => setShowSaveDialog(true)}
                                onUpdate={handleUpdate}
                                onManage={() => setShowManageDrawer(true)}
                                onResetToDefaults={handleResetToBaseline}
                            />

                            {/* Controls Grid */}
                            <div className="grid gap-8 md:grid-cols-2">
                                {/* Left: Sliders */}
                                <div className="space-y-4">
                                    <div className="space-y-2">
                                        <div className="flex justify-between">
                                            <Label>Sensitivity (RMS Threshold)</Label>
                                            <span className="text-xs text-muted-foreground">{settings.rmsThreshold.toFixed(2)}</span>
                                        </div>
                                        <Slider
                                            value={[settings.rmsThreshold]}
                                            min={0.01}
                                            max={0.5}
                                            step={0.01}
                                            onValueChange={([val]) => setSettings({ ...settings, rmsThreshold: val })}
                                        />
                                        <p className="text-[10px] text-muted-foreground">Lower = more events, Higher = only loud peaks.</p>
                                    </div>

                                    <div className="space-y-2">
                                        <div className="flex justify-between">
                                            <Label>Max Clip Duration (s)</Label>
                                            <span className="text-xs text-muted-foreground">{settings.maxSegmentDuration}s</span>
                                        </div>
                                        <Slider
                                            value={[settings.maxSegmentDuration]}
                                            min={2}
                                            max={30}
                                            step={1}
                                            onValueChange={([val]) => setSettings({ ...settings, maxSegmentDuration: val })}
                                        />
                                        <p className="text-[10px] text-muted-foreground">Maximum duration for any single merged segment.</p>
                                    </div>

                                    <div className="space-y-2">
                                        <div className="flex justify-between">
                                            <Label>Context Padding (s)</Label>
                                            <span className="text-xs text-muted-foreground">{settings.contextPadding.toFixed(1)}s</span>
                                        </div>
                                        <Slider
                                            value={[settings.contextPadding]}
                                            min={0}
                                            max={5}
                                            step={0.1}
                                            onValueChange={([val]) => setSettings({ ...settings, contextPadding: val })}
                                        />
                                        <p className="text-[10px] text-muted-foreground">Extra padding before and after each detected event.</p>
                                    </div>

                                    <div className="space-y-2">
                                        <div className="flex justify-between">
                                            <Label>Merge Gap (s)</Label>
                                            <span className="text-xs text-muted-foreground">{settings.mergeGap.toFixed(1)}s</span>
                                        </div>
                                        <Slider
                                            value={[settings.mergeGap]}
                                            min={0}
                                            max={10}
                                            step={0.5}
                                            onValueChange={([val]) => setSettings({ ...settings, mergeGap: val })}
                                        />
                                        <p className="text-[10px] text-muted-foreground">Segments closer than this gap are merged together.</p>
                                    </div>
                                </div>

                                {/* Right: Switches */}
                                <div className="space-y-6">
                                    <div className="flex items-center justify-between p-4 border border-glass-border rounded-lg bg-glass/30 hover:border-neon-blue/30 transition-colors">
                                        <div className="space-y-0.5">
                                            <Label>Burn-in Captions</Label>
                                            <p className="text-[10px] text-muted-foreground">Add &quot;HYPE!&quot; labels to recognized events.</p>
                                        </div>
                                        <Switch
                                            checked={settings.showCaptions}
                                            onCheckedChange={(checked) => setSettings({ ...settings, showCaptions: checked })}
                                        />
                                    </div>

                                    <div className="flex items-center justify-between p-4 border border-glass-border rounded-lg bg-glass/30 hover:border-neon-blue/30 transition-colors">
                                        <div className="space-y-0.5">
                                            <Label>Watermark</Label>
                                            <p className="text-[10px] text-muted-foreground">Apply the &quot;LOUD&quot; branding overlay.</p>
                                        </div>
                                        <Switch
                                            checked={settings.showWatermark}
                                            onCheckedChange={(checked) => setSettings({ ...settings, showWatermark: checked })}
                                        />
                                    </div>
                                </div>
                            </div>
                        </CardContent>
                        <div className="p-6 pt-0 flex justify-between">
                            <Button variant="ghost" onClick={() => setStep('upload')}>Back</Button>
                            <Button
                                size="lg"
                                onClick={handleStartJob}
                                disabled={!assetId}
                                className="bg-gradient-to-r from-neon-blue to-neon-purple hover:from-neon-blue/90 hover:to-neon-purple/90 shadow-glow-sm hover:shadow-glow-blue transition-all duration-300 border-0"
                            >
                                Generate Highlights
                            </Button>
                        </div>
                    </Card>
                )}

                {step === 'processing' && (
                    <Card className="py-12 border-glass-border bg-glass/40 backdrop-blur-sm shadow-inner-glow">
                        <CardContent className="flex flex-col items-center justify-center space-y-6">
                            <div className="relative">
                                <Loader2 className="w-16 h-16 animate-spin text-neon-blue drop-shadow-[0_0_10px_hsl(var(--neon-blue)/0.5)]" />
                                <div className="absolute inset-0 flex items-center justify-center text-xs font-bold">
                                    {progress}%
                                </div>
                            </div>
                            <div className="text-center space-y-2">
                                <h3 className="text-2xl font-semibold text-neon-blue">{status}</h3>
                                <p className="text-muted-foreground max-w-md mx-auto">
                                    Running AI detection, segmenting timeline, and rendering final outputs...
                                </p>
                            </div>
                            <Progress value={progress} className="w-full max-w-md [&>div]:bg-gradient-to-r [&>div]:from-neon-blue [&>div]:to-neon-purple" />
                        </CardContent>
                    </Card>
                )}

                {step === 'result' && (
                    <div className="space-y-8">
                        <div className="grid gap-6 md:grid-cols-2">
                            {outputs.map((out) => (
                                <Card key={out.path} className="border-glass-border bg-glass/40 backdrop-blur-sm shadow-inner-glow hover:border-neon-cyan/30 transition-colors">
                                    <CardHeader>
                                        <CardTitle className="text-neon-cyan">{out.type} Output</CardTitle>
                                    </CardHeader>
                                    <CardContent className="space-y-4">
                                        <video
                                            src={`${API_BASE}/${out.path}`}
                                            controls
                                            className="w-full rounded-lg border border-glass-border bg-black aspect-video"
                                            style={{ aspectRatio: out.type === '9:16' ? '9/16' : '16/9' }}
                                        />
                                        <Button className="w-full border-neon-cyan/30 hover:border-neon-cyan/50 hover:bg-neon-cyan/5 transition-all" variant="outline" asChild>
                                            <a href={`${API_BASE}/${out.path}`} download>
                                                <Download className="mr-2 w-4 h-4" /> Download {out.type}
                                            </a>
                                        </Button>
                                    </CardContent>
                                </Card>
                            ))}
                        </div>

                        <Card className="border-glass-border bg-glass/40 backdrop-blur-sm shadow-inner-glow">
                            <CardHeader>
                                <CardTitle className="text-neon-purple">Detected Segments ({segments.length})</CardTitle>
                            </CardHeader>
                            <CardContent>
                                <div className="space-y-2">
                                    {segments.map((seg, i) => (
                                        <div key={i} className="flex justify-between items-center p-3 rounded-md bg-glass/30 border border-glass-border hover:border-neon-purple/30 transition-colors">
                                            <span className="font-mono text-sm">Segment {i + 1}</span>
                                            <span className="text-muted-foreground text-sm">
                                                {seg.startTime.toFixed(1)}s - {seg.endTime.toFixed(1)}s
                                            </span>
                                        </div>
                                    ))}
                                </div>
                            </CardContent>
                            <div className="p-6 pt-0">
                                <Button
                                    onClick={() => window.location.reload()}
                                    className="bg-gradient-to-r from-neon-blue to-neon-purple hover:from-neon-blue/90 hover:to-neon-purple/90 shadow-glow-sm transition-all duration-300 border-0"
                                >
                                    Start New Job
                                </Button>
                            </div>
                        </Card>
                    </div>
                )}
            </div>

            {/* Save Preset Dialog */}
            <SavePresetDialog
                open={showSaveDialog}
                onClose={() => setShowSaveDialog(false)}
                onSave={async (name, description) => {
                    return presetHook.saveAs(name, description, currentPresetSettings);
                }}
            />

            {/* Manage Presets Drawer */}
            <ManagePresetsDrawer
                open={showManageDrawer}
                onClose={() => setShowManageDrawer(false)}
                presets={presetHook.presets}
                selectedPresetId={presetHook.selectedPresetId}
                onApplyPreset={handlePresetSelect}
                onRenamePreset={presetHook.renamePreset}
                onDeletePreset={async (id) => {
                    await presetHook.deletePreset(id);
                    if (presetHook.selectedPresetId === id) {
                        handlePresetSelect(null);
                    }
                }}
                onExportPreset={downloadPresetJson}
                onImportPreset={presetHook.importPreset}
            />
        </>
    );
}
