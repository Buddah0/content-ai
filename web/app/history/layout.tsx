import { AIShell } from "@/components/AIShell"

export default function HistoryLayout({
    children,
}: {
    children: React.ReactNode
}) {
    return (
        <AIShell showGrid={true}>
            {children}
        </AIShell>
    )
}
