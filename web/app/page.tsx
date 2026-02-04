"use client"

import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Upload, Zap, Download, ArrowRight, Sparkles } from 'lucide-react';
import { AIShell } from '@/components/AIShell';
import { BackgroundMarquee } from '@/components/BackgroundMarquee';

export default function HomePage() {
    return (
        <AIShell showGrid={false}>
            {/* Atmospheric Background Marquee - Home only */}
            <BackgroundMarquee speed="slow" />

            <div className="min-h-screen relative">
                {/* Hero Section */}
                <section className="relative py-20 px-4 overflow-hidden">
                    {/* Subtle gradient orbs */}
                    <div className="absolute top-20 left-1/4 w-72 h-72 bg-neon-blue/15 rounded-full blur-[100px] -z-10" />
                    <div className="absolute bottom-10 right-1/4 w-96 h-96 bg-neon-purple/15 rounded-full blur-[100px] -z-10" />

                    <div className="container mx-auto max-w-4xl text-center space-y-8">
                        {/* Badge */}
                        <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-neon-blue/10 border border-neon-blue/20 text-neon-blue text-sm font-medium shadow-glow-sm">
                            <Sparkles className="w-4 h-4" />
                            AI-Powered Highlight Detection
                        </div>

                        {/* Headline */}
                        <h1 className="text-5xl md:text-6xl font-bold tracking-tight">
                            <span className="bg-gradient-to-r from-foreground via-foreground to-foreground/70 bg-clip-text text-transparent">
                                Transform Your Videos Into
                            </span>
                            <span className="block mt-2 bg-gradient-to-r from-neon-blue via-neon-purple to-neon-cyan bg-clip-text text-transparent pb-4">
                                Creator-Ready Highlights
                            </span>
                        </h1>

                        {/* Subheadline */}
                        <p className="text-xl text-muted-foreground max-w-2xl mx-auto">
                            Upload your raw footage and let AI detect the best moments.
                            Get export-ready clips with watermarks, captions, and dual aspect ratios.
                        </p>

                        {/* CTAs */}
                        <div className="flex flex-col sm:flex-row gap-4 justify-center pt-4">
                            <Button
                                size="lg"
                                className="text-lg px-8 bg-gradient-to-r from-neon-blue to-neon-purple hover:from-neon-blue/90 hover:to-neon-purple/90 shadow-glow-blue transition-all duration-300 hover:shadow-glow-purple border-0"
                                asChild
                            >
                                <Link href="/generator">
                                    Get Started <ArrowRight className="ml-2 w-5 h-5" />
                                </Link>
                            </Button>
                            <Button
                                size="lg"
                                variant="outline"
                                className="text-lg px-8 border-glass-border hover:border-neon-blue/40 hover:bg-neon-blue/5 transition-all duration-300"
                                asChild
                            >
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
                            {/* Upload Card */}
                            <Card className="border border-neon-blue/20 bg-glass/40 backdrop-blur-sm shadow-inner-glow hover:border-neon-blue/40 hover:shadow-glow-sm transition-all duration-300 group">
                                <CardHeader>
                                    <div className="w-12 h-12 rounded-lg bg-neon-blue/10 flex items-center justify-center mb-4 group-hover:shadow-glow-sm transition-all duration-300">
                                        <Upload className="w-6 h-6 text-neon-blue" />
                                    </div>
                                    <CardTitle>1. Upload</CardTitle>
                                    <CardDescription>
                                        Drop your raw video file. Supports MP4, MOV, MKV and more.
                                    </CardDescription>
                                </CardHeader>
                            </Card>

                            {/* Process Card */}
                            <Card className="border border-neon-purple/20 bg-glass/40 backdrop-blur-sm shadow-inner-glow hover:border-neon-purple/40 hover:shadow-glow-purple transition-all duration-300 group">
                                <CardHeader>
                                    <div className="w-12 h-12 rounded-lg bg-neon-purple/10 flex items-center justify-center mb-4 group-hover:shadow-glow-purple transition-all duration-300">
                                        <Zap className="w-6 h-6 text-neon-purple" />
                                    </div>
                                    <CardTitle>2. Process</CardTitle>
                                    <CardDescription>
                                        AI detects hype moments. Captions and watermarks are burned in.
                                    </CardDescription>
                                </CardHeader>
                            </Card>

                            {/* Export Card */}
                            <Card className="border border-neon-cyan/20 bg-glass/40 backdrop-blur-sm shadow-inner-glow hover:border-neon-cyan/40 hover:shadow-glow-cyan transition-all duration-300 group">
                                <CardHeader>
                                    <div className="w-12 h-12 rounded-lg bg-neon-cyan/10 flex items-center justify-center mb-4 group-hover:shadow-glow-cyan transition-all duration-300">
                                        <Download className="w-6 h-6 text-neon-cyan" />
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
                        <Card className="bg-gradient-to-r from-neon-blue/10 via-glass/60 to-neon-purple/10 border border-glass-border backdrop-blur-sm shadow-inner-glow">
                            <CardContent className="py-12 space-y-6">
                                <h3 className="text-2xl font-bold">Ready to create?</h3>
                                <p className="text-muted-foreground">
                                    Start generating highlights from your videos in seconds.
                                </p>
                                <Button
                                    size="lg"
                                    className="bg-gradient-to-r from-neon-blue to-neon-purple hover:from-neon-blue/90 hover:to-neon-purple/90 shadow-glow-sm hover:shadow-glow-blue transition-all duration-300 border-0"
                                    asChild
                                >
                                    <Link href="/generator">
                                        Launch Generator <ArrowRight className="ml-2 w-4 h-4" />
                                    </Link>
                                </Button>
                            </CardContent>
                        </Card>
                    </div>
                </section>
            </div>
        </AIShell>
    );
}
