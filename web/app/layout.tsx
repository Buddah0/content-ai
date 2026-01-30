
import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
    title: "Content AI Mission Control",
    description: "Generate creator-ready highlights",
};

function Nav() {
    return (
        <header className="border-b border-border/40 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
            <nav className="container mx-auto flex h-14 items-center px-4 gap-6">
                <Link href="/" className="font-bold text-lg">
                    Mission Control
                </Link>
                <div className="flex gap-4 text-sm">
                    <Link href="/generator" className="text-muted-foreground hover:text-foreground transition-colors">
                        Generator
                    </Link>
                    <Link href="/history" className="text-muted-foreground hover:text-foreground transition-colors">
                        History
                    </Link>
                </div>
            </nav>
        </header>
    );
}

export default function RootLayout({
    children,
}: Readonly<{
    children: React.ReactNode;
}>) {
    return (
        <html lang="en">
            <body className="antialiased dark min-h-screen bg-background text-foreground">
                <Nav />
                <main>{children}</main>
            </body>
        </html>
    );
}

