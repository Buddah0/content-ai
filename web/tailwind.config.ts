import type { Config } from "tailwindcss";

const config: Config = {
    darkMode: ["class"],
    content: [
        "./app/**/*.{js,ts,jsx,tsx,mdx}",
        "./components/**/*.{js,ts,jsx,tsx,mdx}",
    ],
    theme: {
        extend: {
            colors: {
                background: 'hsl(var(--background))',
                foreground: 'hsl(var(--foreground))',
                card: {
                    DEFAULT: 'hsl(var(--card))',
                    foreground: 'hsl(var(--card-foreground))'
                },
                popover: {
                    DEFAULT: 'hsl(var(--popover))',
                    foreground: 'hsl(var(--popover-foreground))'
                },
                primary: {
                    DEFAULT: 'hsl(var(--primary))',
                    foreground: 'hsl(var(--primary-foreground))'
                },
                secondary: {
                    DEFAULT: 'hsl(var(--secondary))',
                    foreground: 'hsl(var(--secondary-foreground))'
                },
                muted: {
                    DEFAULT: 'hsl(var(--muted))',
                    foreground: 'hsl(var(--muted-foreground))'
                },
                accent: {
                    DEFAULT: 'hsl(var(--accent))',
                    foreground: 'hsl(var(--accent-foreground))'
                },
                destructive: {
                    DEFAULT: 'hsl(var(--destructive))',
                    foreground: 'hsl(var(--destructive-foreground))'
                },
                border: 'hsl(var(--border))',
                input: 'hsl(var(--input))',
                ring: 'hsl(var(--ring))',
                chart: {
                    '1': 'hsl(var(--chart-1))',
                    '2': 'hsl(var(--chart-2))',
                    '3': 'hsl(var(--chart-3))',
                    '4': 'hsl(var(--chart-4))',
                    '5': 'hsl(var(--chart-5))'
                },
                // AI Aesthetic - Neon Colors
                neon: {
                    blue: 'hsl(var(--neon-blue))',
                    purple: 'hsl(var(--neon-purple))',
                    cyan: 'hsl(var(--neon-cyan))',
                    pink: 'hsl(var(--neon-pink))'
                },
                glass: {
                    DEFAULT: 'hsl(var(--glass-bg))',
                    border: 'hsl(var(--glass-border))',
                    highlight: 'hsl(var(--glass-highlight))'
                }
            },
            borderRadius: {
                lg: 'var(--radius)',
                md: 'calc(var(--radius) - 2px)',
                sm: 'calc(var(--radius) - 4px)'
            },
            keyframes: {
                'marquee': {
                    '0%': { transform: 'translateX(0)' },
                    '100%': { transform: 'translateX(-50%)' }
                },
                'glow-pulse': {
                    '0%, 100%': { opacity: '0.6' },
                    '50%': { opacity: '1' }
                },
                'border-glow': {
                    '0%, 100%': {
                        backgroundPosition: '0% 50%'
                    },
                    '50%': {
                        backgroundPosition: '100% 50%'
                    }
                }
            },
            animation: {
                'marquee': 'marquee 30s linear infinite',
                'marquee-slow': 'marquee 45s linear infinite',
                'glow-pulse': 'glow-pulse 2s ease-in-out infinite',
                'border-glow': 'border-glow 3s ease infinite'
            },
            boxShadow: {
                'glow-blue': '0 0 20px hsl(var(--neon-blue) / 0.4), 0 0 40px hsl(var(--neon-blue) / 0.2)',
                'glow-purple': '0 0 20px hsl(var(--neon-purple) / 0.4), 0 0 40px hsl(var(--neon-purple) / 0.2)',
                'glow-cyan': '0 0 20px hsl(var(--neon-cyan) / 0.4), 0 0 40px hsl(var(--neon-cyan) / 0.2)',
                'glow-sm': '0 0 10px hsl(var(--neon-blue) / 0.3)',
                'glow-md': '0 0 20px hsl(var(--neon-blue) / 0.4)',
                'glow-lg': '0 0 40px hsl(var(--neon-blue) / 0.5)',
                'inner-glow': 'inset 0 1px 1px hsl(var(--glass-highlight) / 0.1)'
            },
            backdropBlur: {
                'glass': '12px'
            }
        }
    },
    plugins: [require("tailwindcss-animate")],
};
export default config;
