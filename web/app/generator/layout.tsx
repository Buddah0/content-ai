import { Suspense } from "react"
import { AIShell } from "@/components/AIShell"
import { Loader2 } from "lucide-react"

function GeneratorLoading() {
    return (
        <div className="container mx-auto max-w-4xl py-12 px-4 flex items-center justify-center min-h-[50vh]">
            <Loader2 className="w-8 h-8 animate-spin text-neon-blue drop-shadow-[0_0_10px_hsl(var(--neon-blue)/0.5)]" />
        </div>
    )
}

export default function GeneratorLayout({
    children,
}: {
    children: React.ReactNode
}) {
    return (
        <AIShell showGrid={true}>
            <Suspense fallback={<GeneratorLoading />}>
                {children}
            </Suspense>
        </AIShell>
    )
}
