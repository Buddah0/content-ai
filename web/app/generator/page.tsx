"use client"

import React, { useState, useEffect } from 'react';
import { UploadZone } from '@/components/upload-zone';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { CheckCircle2, Play, Download, ArrowRight, Loader2, AlertCircle } from 'lucide-react';

const API_BASE = "http://localhost:8000";

type Step = 'upload' | 'settings' | 'processing' | 'result';

export default function GeneratorPage() {
    const [step, setStep] = useState<Step>('upload');
    const [file, setFile] = useState<File | null>(null);
    const [assetId, setAssetId] = useState<string | null>(null);
    const [jobId, setJobId] = useState<string | null>(null);
    const [progress, setProgress] = useState(0);
    const [status, setStatus] = useState("PENDING");
    const [outputs, setOutputs] = useState<{ type: string, path: string }[]>([]);
    const [segments, setSegments] = useState<{ startTime: number, endTime: number }[]>([]);

    // 1. Upload
    const handleUpload = async () => {
        if (!file) return;
        try {
            setStep('settings'); // Optimistic, ideally show upload progress
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

    // 2. Start Job
    const handleStartJob = async () => {
        if (!assetId) return;
        try {
            const res = await fetch(`${API_BASE}/jobs`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ assetId })
            });
            const data = await res.json();
            setJobId(data.id);
            setStep('processing');
        } catch (e) {
            console.error(e);
            alert("Failed to start job");
        }
    };

    // 3. SSE
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
        const res = await fetch(`${API_BASE}/jobs/${jobId}`);
        const data = await res.json();
        setOutputs(data.outputs);
        setSegments(data.segments);
        setStep('result');
    };

    return (
        <div className="container mx-auto max-w-4xl py-12 px-4 space-y-8">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight">Mission Control</h1>
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
                <Card>
                    <CardHeader>
                        <CardTitle>Configuration</CardTitle>
                        <CardDescription>Customize your output generation.</CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <div className="grid gap-4 md:grid-cols-2">
                            <div className="p-4 border rounded-lg bg-secondary/50">
                                <h4 className="font-semibold mb-2">Captions</h4>
                                <p className="text-sm text-muted-foreground">Burned-in mock captions enabled (Fixed)</p>
                            </div>
                            <div className="p-4 border rounded-lg bg-secondary/50">
                                <h4 className="font-semibold mb-2">Watermark</h4>
                                <p className="text-sm text-muted-foreground">LOUD watermark (Top-Left) enabled (Fixed)</p>
                            </div>
                            <div className="p-4 border rounded-lg bg-secondary/50">
                                <h4 className="font-semibold mb-2">Output Formats</h4>
                                <p className="text-sm text-muted-foreground">Generating BOTH 9:16 and 16:9</p>
                            </div>
                            <div className="p-4 border rounded-lg bg-secondary/50">
                                <h4 className="font-semibold mb-2">Framing</h4>
                                <p className="text-sm text-muted-foreground">9:16 uses Blur + Pad (Creator-Ready)</p>
                            </div>
                        </div>
                    </CardContent>
                    <div className="p-6 pt-0 flex justify-between">
                        <Button variant="ghost" onClick={() => setStep('upload')}>Back</Button>
                        <Button size="lg" onClick={handleStartJob} disabled={!assetId}>
                            {assetId ? "Generate Highlights" : "Uploading..."}
                        </Button>
                    </div>
                </Card>
            )}

            {step === 'processing' && (
                <Card className="py-12">
                    <CardContent className="flex flex-col items-center justify-center space-y-6">
                        <div className="relative">
                            <Loader2 className="w-16 h-16 animate-spin text-primary" />
                            <div className="absolute inset-0 flex items-center justify-center text-xs font-bold">
                                {progress}%
                            </div>
                        </div>
                        <div className="text-center space-y-2">
                            <h3 className="text-2xl font-semibold">{status}</h3>
                            <p className="text-muted-foreground max-w-md mx-auto">
                                Running AI detection, segmenting timeline, and rendering final outputs...
                            </p>
                        </div>
                        <Progress value={progress} className="w-full max-w-md" />
                    </CardContent>
                </Card>
            )}

            {step === 'result' && (
                <div className="space-y-8">
                    <div className="grid gap-6 md:grid-cols-2">
                        {outputs.map((out) => (
                            <Card key={out.path}>
                                <CardHeader>
                                    <CardTitle>{out.type} Output</CardTitle>
                                </CardHeader>
                                <CardContent className="space-y-4">
                                    <video
                                        src={`${API_BASE}/${out.path}`}
                                        controls
                                        className="w-full rounded-lg border bg-black aspect-video"
                                        style={{ aspectRatio: out.type === '9:16' ? '9/16' : '16/9' }}
                                    />
                                    <Button className="w-full" variant="outline" asChild>
                                        <a href={`${API_BASE}/${out.path}`} download>
                                            <Download className="mr-2 w-4 h-4" /> Download {out.type}
                                        </a>
                                    </Button>
                                </CardContent>
                            </Card>
                        ))}
                    </div>

                    <Card>
                        <CardHeader>
                            <CardTitle>Detected Segments ({segments.length})</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="space-y-2">
                                {segments.map((seg, i) => (
                                    <div key={i} className="flex justify-between items-center p-3 rounded-md bg-secondary/20">
                                        <span className="font-mono text-sm">Segment {i + 1}</span>
                                        <span className="text-muted-foreground text-sm">
                                            {seg.startTime.toFixed(1)}s - {seg.endTime.toFixed(1)}s
                                        </span>
                                    </div>
                                ))}
                            </div>
                        </CardContent>
                        <div className="p-6 pt-0">
                            <Button onClick={() => window.location.reload()}>Start New Job</Button>
                        </div>
                    </Card>
                </div>
            )}
        </div>
    );
}
