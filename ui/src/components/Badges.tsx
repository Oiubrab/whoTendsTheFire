import type { ReactNode } from "react"
import type { TorchKind } from "../api/types"

const statusStyles = {
  pass: "text-pass bg-passbg",
  fail: "text-fail bg-failbg",
  warn: "text-warn bg-warnbg",
  live: "text-ember2 bg-emberbg",
  idle: "text-ash bg-coal",
} as const

export function StatusPill({
  kind,
  children,
  pulse,
}: {
  kind: keyof typeof statusStyles
  children: ReactNode
  pulse?: boolean
}) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 font-mono text-[10.5px] uppercase tracking-wider whitespace-nowrap ${statusStyles[kind]}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full bg-current ${pulse ? "animate-pulse" : ""}`} />
      {children}
    </span>
  )
}

const kindStyles: Record<TorchKind, string> = {
  decision: "text-k-decision border-[#284660]",
  action: "text-k-action border-[#2D4A30]",
  validation: "text-k-validation border-[#4D3352]",
  kindling: "text-k-kindling border-[#54481F]",
  authoring: "text-k-authoring border-[#2A4D47]",
}

export function KindBadge({ kind }: { kind: TorchKind }) {
  return (
    <span
      className={`rounded border px-2 py-0.5 font-mono text-[10.5px] uppercase tracking-wider whitespace-nowrap ${kindStyles[kind]}`}
    >
      {kind}
    </span>
  )
}

export function GraphChip({ id }: { id: string }) {
  return (
    <span className="rounded bg-emberbg px-1.5 py-px font-mono text-[11px] whitespace-nowrap text-ember2">
      {id}
    </span>
  )
}

export function hearthStatus(halted: boolean): keyof typeof statusStyles {
  return halted ? "warn" : "live"
}
