"use client"

import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Upload, Zap, Download, ArrowRight, Sparkles } from 'lucide-react';

export default function HomePage() {
    return (
        <div className="min-h-screen">
            {/* Hero Section */}
            <section className="relative py-20 px-4 overflow-hidden">
                <div className="absolute inset-0 bg-gradient-to-br from-primary/20 via-background to-background -z-10" />
                <div className="absolute top-20 left-1/4 w-72 h-72 bg-primary/10 rounded-full blur-3xl -z-10" />
                <div className="absolute bottom-10 right-1/4 w-96 h-96 bg-purple-500/10 rounded-full blur-3xl -z-10" />

                <div className="container mx-auto max-w-4xl text-center space-y-8">
                    <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-primary/10 text-primary text-sm font-medium">
                        <Sparkles className="w-4 h-4" />
                        AI-Powered Highlight Detection
                    </div>

                    <h1 className="text-5xl md:text-6xl font-bold tracking-tight bg-gradient-to-r from-foreground to-foreground/70 bg-clip-text">
                        Transform Your Videos Into
                        <span className="block text-primary mt-2">Creator-Ready Highlights</span>
                    </h1>

                    <p className="text-xl text-muted-foreground max-w-2xl mx-auto">
                        Upload your raw footage and let AI detect the best moments.
                        Get export-ready clips with watermarks, captions, and dual aspect ratios.
                    </p>

                    <div className="flex flex-col sm:flex-row gap-4 justify-center pt-4">
                        <Button size="lg" className="text-lg px-8" asChild>
                            <Link href="/generator">
                                Get Started <ArrowRight className="ml-2 w-5 h-5" />
                            </Link>
                        </Button>
                        <Button size="lg" variant="outline" className="text-lg px-8" asChild>
                            <Link href="/history">View History</Link>
                        </Button>
                    </div>
                </div>
            </section>

            {/* Features Section */}
            <section className="py-20 px-4">
                <div className="container mx-auto max-w-5xl">
                    <h2 className="text-3xl font-bold text-center mb-12">How It Works</h2>

                    <div className="grid md:grid-cols-3 gap-6">
                        <Card className="border-2 border-primary/20 bg-gradient-to-b from-primary/5 to-transparent">
                            <CardHeader>
                                <div className="w-12 h-12 rounded-lg bg-primary/10 flex items-center justify-center mb-4">
                                    <Upload className="w-6 h-6 text-primary" />
                                </div>
                                <CardTitle>1. Upload</CardTitle>
                                <CardDescription>
                                    Drop your raw video file. Supports MP4, MOV, MKV and more.
                                </CardDescription>
                            </CardHeader>
                        </Card>

                        <Card className="border-2 border-orange-500/20 bg-gradient-to-b from-orange-500/5 to-transparent">
                            <CardHeader>
                                <div className="w-12 h-12 rounded-lg bg-orange-500/10 flex items-center justify-center mb-4">
                                    <Zap className="w-6 h-6 text-orange-500" />
                                </div>
                                <CardTitle>2. Process</CardTitle>
                                <CardDescription>
                                    AI detects hype moments. Captions and watermarks are burned in.
                                </CardDescription>
                            </CardHeader>
                        </Card>

                        <Card className="border-2 border-green-500/20 bg-gradient-to-b from-green-500/5 to-transparent">
                            <CardHeader>
                                <div className="w-12 h-12 rounded-lg bg-green-500/10 flex items-center justify-center mb-4">
                                    <Download className="w-6 h-6 text-green-500" />
                                </div>
                                <CardTitle>3. Export</CardTitle>
                                <CardDescription>
                                    Download in 16:9 and 9:16. Ready for YouTube, TikTok, and more.
                                </CardDescription>
                            </CardHeader>
                        </Card>
                    </div>
                </div>
            </section>

            {/* CTA Section */}
            <section className="py-16 px-4">
                <div className="container mx-auto max-w-2xl text-center">
                    <Card className="bg-gradient-to-r from-primary/10 to-purple-500/10 border-primary/20">
                        <CardContent className="py-12 space-y-6">
                            <h3 className="text-2xl font-bold">Ready to create?</h3>
                            <p className="text-muted-foreground">
                                Start generating highlights from your videos in seconds.
                            </p>
                            <Button size="lg" asChild>
                                <Link href="/generator">
                                    Launch Generator <ArrowRight className="ml-2 w-4 h-4" />
                                </Link>
                            </Button>
                        </CardContent>
                    </Card>
                </div>
            </section>
        </div>
    );
}
