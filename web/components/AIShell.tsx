"use client"

import * as React from "react"
import { cn } from "@/lib/utils"

interface AIShellProps extends React.HTMLAttributes<HTMLDivElement> {
    children: React.ReactNode
    /** Show animated gradient border */
    glowBorder?: boolean
    /** Add subtle grid pattern overlay */
    showGrid?: boolean
}

/**
 * AIShell - Glass-panel wrapper with AI aesthetic styling.
 * Use this to wrap content in generator/history layouts for consistent look.
 */
export function AIShell({
    children,
    className,
    glowBorder = false,
    showGrid = true,
    ...props
}: AIShellProps) {
    return (
        <div
            className={cn(
                "relative min-h-[calc(100vh-3.5rem)]",
                className
            )}
            {...props}
        >
            {/* Gradient background layer */}
            <div className="fixed inset-0 -z-20 bg-background">
                <div className="absolute inset-0 bg-gradient-to-br from-neon-blue/5 via-background to-neon-purple/5" />
                <div className="absolute top-0 left-1/4 w-[500px] h-[500px] bg-neon-blue/10 rounded-full blur-[120px]" />
                <div className="absolute bottom-0 right-1/4 w-[600px] h-[600px] bg-neon-purple/10 rounded-full blur-[120px]" />
            </div>

            {/* Optional grid overlay */}
            {showGrid && (
                <div
                    className="fixed inset-0 -z-10 opacity-[0.02]"
                    style={{
                        backgroundImage: `linear-gradient(hsl(var(--foreground)) 1px, transparent 1px),
                                          linear-gradient(90deg, hsl(var(--foreground)) 1px, transparent 1px)`,
                        backgroundSize: '60px 60px'
                    }}
                />
            )}

            {/* Glow border wrapper (optional) */}
            {glowBorder ? (
                <div className="relative">
                    <div
                        className="absolute -inset-[1px] rounded-xl bg-gradient-to-r from-neon-blue via-neon-purple to-neon-cyan opacity-20 blur-sm animate-border-glow"
                        style={{ backgroundSize: '200% 200%' }}
                    />
                    <div className="relative bg-glass/80 backdrop-blur-glass rounded-xl border border-glass-border">
                        {children}
                    </div>
                </div>
            ) : (
                <>{children}</>
            )}
        </div>
    )
}

/**
 * GlassCard - A card variant with glassmorphism styling.
 * Drop-in enhancement for existing Card components.
 */
export function GlassCard({
    children,
    className,
    neonAccent = "blue",
    ...props
}: React.HTMLAttributes<HTMLDivElement> & {
    neonAccent?: "blue" | "purple" | "cyan" | "none"
}) {
    const accentClasses = {
        blue: "border-neon-blue/20 shadow-glow-sm hover:border-neon-blue/40 hover:shadow-glow-blue",
        purple: "border-neon-purple/20 hover:border-neon-purple/40 hover:shadow-glow-purple",
        cyan: "border-neon-cyan/20 hover:border-neon-cyan/40 hover:shadow-glow-cyan",
        none: "border-glass-border"
    }

    return (
        <div
            className={cn(
                "rounded-xl bg-glass/60 backdrop-blur-glass border shadow-inner-glow transition-all duration-300",
                accentClasses[neonAccent],
                className
            )}
            {...props}
        >
            {children}
        </div>
    )
}
