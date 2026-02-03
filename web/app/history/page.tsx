"use client"

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { CheckCircle2, Clock, Loader2, XCircle, ArrowRight, RefreshCw, Trash2 } from 'lucide-react';

const API_BASE = "http://localhost:8000";

interface Job {
    id: string;
    status: string;
    progress: number;
    createdAt: string | null;
    assetId: string;
}

const statusIcons: Record<string, React.ReactNode> = {
    COMPLETED: <CheckCircle2 className="w-5 h-5 text-green-500" />,
    FAILED: <XCircle className="w-5 h-5 text-red-500" />,
    PROCESSING: <Loader2 className="w-5 h-5 text-blue-500 animate-spin" />,
    PENDING: <Clock className="w-5 h-5 text-muted-foreground" />,
};

const statusColors: Record<string, string> = {
    COMPLETED: "bg-green-500/10 text-green-500",
    FAILED: "bg-red-500/10 text-red-500",
    PROCESSING: "bg-blue-500/10 text-blue-500",
    PENDING: "bg-muted text-muted-foreground",
};

export default function HistoryPage() {
    const [jobs, setJobs] = useState<Job[]>([]);
    const [loading, setLoading] = useState(true);

    const fetchJobs = async () => {
        setLoading(true);
        try {
            const res = await fetch(`${API_BASE}/jobs`);
            const data = await res.json();
            setJobs(data);
        } catch (e) {
            console.error("Failed to fetch jobs", e);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchJobs();
    }, []);

    const formatDate = (isoString: string | null) => {
        if (!isoString) return "—";
        return new Date(isoString).toLocaleString(undefined, {
            month: 'numeric',
            day: 'numeric',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
            hour12: false
        });
    };

    return (
        <div className="container mx-auto max-w-4xl py-12 px-4 space-y-8">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight">Job History</h1>
                    <p className="text-muted-foreground">View all your past generation jobs.</p>
                </div>
                <Button variant="outline" onClick={fetchJobs} disabled={loading}>
                    <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
                    Refresh
                </Button>
            </div>

            {loading && jobs.length === 0 ? (
                <div className="flex items-center justify-center py-20">
                    <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
                </div>
            ) : jobs.length === 0 ? (
                <Card className="py-12">
                    <CardContent className="flex flex-col items-center justify-center text-center space-y-4">
                        <Clock className="w-12 h-12 text-muted-foreground" />
                        <h3 className="text-xl font-semibold">No jobs yet</h3>
                        <p className="text-muted-foreground">Start by generating your first highlight reel.</p>
                        <Button asChild>
                            <Link href="/generator">
                                Go to Generator <ArrowRight className="ml-2 w-4 h-4" />
                            </Link>
                        </Button>
                    </CardContent>
                </Card>
            ) : (
                <div className="space-y-4">
                    {jobs.map((job) => (
                        <Card key={job.id} className="hover:border-primary/40 transition-colors">
                            <CardContent className="flex items-center justify-between py-4">
                                <div className="flex items-center gap-4">
                                    {statusIcons[job.status] || <Clock className="w-5 h-5" />}
                                    <div>
                                        <p className="font-mono text-sm">{job.id}</p>
                                        <p className="text-xs text-muted-foreground">{formatDate(job.createdAt)}</p>
                                    </div>
                                </div>
                                <div className="flex items-center gap-4">
                                    <span className={`px-3 py-1 rounded-full text-xs font-medium ${statusColors[job.status] || 'bg-muted'}`}>
                                        {job.status}
                                    </span>
                                    {job.status === 'COMPLETED' && (
                                        <Button size="sm" variant="outline" asChild>
                                            <Link href={`/generator?jobId=${job.id}`}>
                                                View Results
                                            </Link>
                                        </Button>
                                    )}
                                    <Button
                                        size="icon"
                                        variant="ghost"
                                        className="text-muted-foreground hover:text-red-500 hover:bg-red-50"
                                        onClick={async (e) => {
                                            e.stopPropagation();
                                            if (!confirm('Are you sure you want to delete this job?')) return;
                                            try {
                                                await fetch(`${API_BASE}/jobs/${job.id}`, { method: 'DELETE' });
                                                setJobs(jobs.filter(j => j.id !== job.id));
                                            } catch (err) {
                                                console.error("Failed to delete", err);
                                            }
                                        }}
                                    >
                                        <Trash2 className="w-4 h-4" />
                                    </Button>
                                </div>
                            </CardContent>
                        </Card>
                    ))}
                </div>
            )}
        </div>
    );
}
