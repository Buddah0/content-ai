"use client"

import * as React from "react"
import { cn } from "@/lib/utils"
// import Image from "next/image" // Keeping it simple with img tags for marquee as they can sometimes behave better with pure CSS scrolling, but Next Image is fine too. Let's start with standard img for simplicity in marquee containers unless optimization is strictly needed.

const GAME_IMAGES = [
    { src: "/assets/games/for-honor.jpg", alt: "For Honor", width: 300, height: 169 },
    { src: "/assets/games/valorant.png", alt: "Valorant", width: 300, height: 169 },
    { src: "/assets/games/csgo2.jpg", alt: "CSGO 2", width: 300, height: 169 },
    { src: "/assets/games/sf6.jpg", alt: "Street Fighter 6", width: 300, height: 169 },
]

interface BackgroundMarqueeProps extends React.HTMLAttributes<HTMLDivElement> {
    /** Animation speed: 'slow' = 45s, 'normal' = 30s */
    speed?: "slow" | "normal"
}

/**
 * BackgroundMarquee - Infinite scrolling game images for Home page background.
 */
export function BackgroundMarquee({
    className,
    speed = "normal",
    ...props
}: BackgroundMarqueeProps) {
    // Duplicate images for seamless loop (multiple times to fill screen)
    const images = [...GAME_IMAGES, ...GAME_IMAGES, ...GAME_IMAGES]

    return (
        <div
            className={cn(
                "absolute inset-0 overflow-hidden pointer-events-none select-none -z-10",
                className
            )}
            aria-hidden="true"
            {...props}
        >
            {/* Edge fade masks */}
            <div className="absolute inset-y-0 left-0 w-32 bg-gradient-to-r from-background to-transparent z-10" />
            <div className="absolute inset-y-0 right-0 w-32 bg-gradient-to-l from-background to-transparent z-10" />

            {/* Marquee track - vertically centered */}
            <div className="absolute inset-0 flex items-center">
                <div
                    className={cn(
                        "flex items-center gap-8 will-change-transform",
                        speed === "slow" ? "animate-marquee-slow" : "animate-marquee",
                        "motion-reduce:animate-none motion-reduce:opacity-30"
                    )}
                    style={{
                        transform: 'translate3d(0, 0, 0)' // Force GPU acceleration
                    }}
                >
                    {images.map((game, i) => (
                        <div
                            key={`${game.alt}-${i}`}
                            className="relative flex-shrink-0"
                            style={{
                                width: '400px',
                                opacity: 0.3, // Increased slightly since multiply darkens things
                                mixBlendMode: 'multiply', // Hides white/light backgrounds (checkerboards) on dark themes
                                filter: 'contrast(1.2)' // Helps pop the logo from the grey
                            }}
                        >
                            <img
                                src={game.src}
                                alt={game.alt}
                                className="w-full h-auto object-cover rounded-lg grayscale hover:grayscale-0 transition-all duration-500"
                            />
                        </div>
                    ))}
                </div>
            </div>

            {/* Second row (offset) - optional, maybe remove for cleaner look or keep with different direction?
                The user asked for "nice and clean", so one row might be enough, OR two rows moving in opposite directions.
                Let's stick to one main row for now as replacing text with images makes them bigger and "busier".
                Actually, let's add a second row but much slower and more transparent for depth,
                or just one row to be safe. "Everything looks nice and clean".
                Let's do two rows to match the previous density but make them very subtle.
            */}
            <div className="absolute inset-0 flex items-center translate-y-48 opacity-30 scale-110 blur-[1px]">
                <div
                    className={cn(
                        "flex items-center gap-8 will-change-transform",
                        speed === "slow" ? "animate-marquee" : "animate-marquee-slow",
                    )}
                    style={{
                        transform: 'translate3d(0, 0, 0)',
                        animationDirection: 'reverse'
                    }}
                >
                    {images.map((game, i) => (
                        <div
                            key={`${game.alt}-row2-${i}`}
                            className="relative flex-shrink-0"
                            style={{
                                width: '500px',
                                opacity: 0.2,
                                mixBlendMode: 'multiply'
                            }}
                        >
                            <img
                                src={game.src}
                                alt={game.alt}
                                className="w-full h-auto object-cover rounded-xl grayscale opacity-50"
                            />
                        </div>
                    ))}
                </div>
            </div>
        </div>
    )
}
