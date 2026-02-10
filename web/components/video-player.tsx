"use client";

import React, { useRef, useEffect, useState } from "react";
import { Maximize, Minimize } from "lucide-react";
import { cn } from "@/lib/utils";

interface VideoPlayerProps extends React.VideoHTMLAttributes<HTMLVideoElement> {
    containerClassName?: string;
}

export function VideoPlayer({ className, containerClassName, ...props }: VideoPlayerProps) {
    const videoRef = useRef<HTMLVideoElement>(null);
    const containerRef = useRef<HTMLDivElement>(null);
    const [isFullscreen, setIsFullscreen] = useState(false);

    // ---------------------------------------------------------------------------
    // 1. Frame Drop Instrumentation
    // ---------------------------------------------------------------------------
    useEffect(() => {
        const video = videoRef.current;
        if (!video) return;

        const interval = setInterval(() => {
            // @ts-ignore - getVideoPlaybackQuality might not be in all TS defs yet
            if (video.getVideoPlaybackQuality) {
                // @ts-ignore
                const q = video.getVideoPlaybackQuality();
                const dropped = q.droppedVideoFrames;
                const total = q.totalVideoFrames;

                if (total > 0 && dropped > 0) {
                    console.log(
                        `[VideoStats] Dropped: ${dropped} / ${total} (${((dropped / total) * 100).toFixed(2)}%)`
                    );
                }
            }
        }, 1000);

        return () => clearInterval(interval);
    }, []);

    // ---------------------------------------------------------------------------
    // 2. CSS Debug Utility
    // ---------------------------------------------------------------------------
    const checkExpensiveStyles = () => {
        let el: HTMLElement | null = videoRef.current;
        let depth = 0;
        const maxDepth = 20;

        console.group("[CSS Audit] Checking ancestors for expensive styles...");
        while (el && depth < maxDepth && el !== document.body) {
            const style = window.getComputedStyle(el);
            const expensiveProps = [];

            if (style.filter !== "none") expensiveProps.push(`filter: ${style.filter}`);
            if (style.backdropFilter !== "none") expensiveProps.push(`backdrop-filter: ${style.backdropFilter}`);
            if (style.opacity !== "1") expensiveProps.push(`opacity: ${style.opacity}`);
            if (style.transform !== "none") expensiveProps.push(`transform: ${style.transform}`);
            if (style.willChange !== "auto") expensiveProps.push(`will-change: ${style.willChange}`);

            if (expensiveProps.length > 0) {
                console.warn(`Node <${el.tagName.toLowerCase()} class="${el.className}"> has expensive styles:`, expensiveProps);
            }
            el = el.parentElement;
            depth++;
        }
        console.groupEnd();
    };

    // ---------------------------------------------------------------------------
    // 3. Fullscreen Handling
    // ---------------------------------------------------------------------------
    useEffect(() => {
        const handleFullscreenChange = () => {
            const isFs = document.fullscreenElement === containerRef.current || document.fullscreenElement === videoRef.current;
            setIsFullscreen(isFs);

            if (isFs) {
                document.body.classList.add("fullscreen-video");
                checkExpensiveStyles(); // Run audit on enter
            } else {
                document.body.classList.remove("fullscreen-video");
            }
        };

        document.addEventListener("fullscreenchange", handleFullscreenChange);
        return () => {
            document.removeEventListener("fullscreenchange", handleFullscreenChange);
            document.body.classList.remove("fullscreen-video");
        };
    }, []);

    const toggleFullscreen = () => {
        if (!containerRef.current) return;

        if (!document.fullscreenElement) {
            containerRef.current.requestFullscreen().catch(err => {
                console.error(`Error attempting to enable fullscreen: ${err.message}`);
            });
        } else {
            document.exitFullscreen();
        }
    };

    return (
        <div
            ref={containerRef}
            className={cn("relative group bg-black rounded-lg overflow-hidden", containerClassName)}
        >
            <video
                ref={videoRef}
                className={cn("w-full h-full object-contain", className)}
                {...props}
            />

            {/* Custom Fullscreen Button Overlay */}
            <div className="absolute bottom-4 right-4 opacity-0 group-hover:opacity-100 transition-opacity duration-200">
                <button
                    onClick={toggleFullscreen}
                    className="p-2 rounded-full bg-black/50 hover:bg-black/70 text-white backdrop-blur-sm transition-colors"
                    type="button"
                    aria-label={isFullscreen ? "Exit Fullscreen" : "Enter Fullscreen"}
                >
                    {isFullscreen ? <Minimize className="w-5 h-5" /> : <Maximize className="w-5 h-5" />}
                </button>
            </div>
        </div>
    );
}
