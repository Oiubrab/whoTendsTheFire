import { useMemo, useState } from "react"
import { useOutletContext } from "react-router-dom"
import type { HearthContext } from "./HearthLayout"
import { useCalls } from "../../api/hooks"
import { useRunStore } from "../../lib/runStore"
import type { CallLogEntry } from "../../api/types"

const SECTION_COLORS = [
  "var(--color-k-kindling)",
  "var(--color-k-decision)",
  "var(--color-k-action)",
  "var(--color-k-validation)",
  "var(--color-k-authoring)",
  "var(--color-ember)",
  "var(--color-ash)",
]

// Every prompt built in this codebase (server.py, agent.py, briefText in
// q/torches.q) writes its own sections as a short ALL-CAPS line ending in
// a colon, with nothing else on that line -- "INVOCATION:", "RITE:",
// "CURRENT CODEBASE:" and so on. Splitting on that is enough to get a
// real (if approximate) token-budget bar without hand-maintaining a list
// of section names that would drift from the actual prompt-building code.
function splitSections(prompt: string): { label: string; text: string }[] {
  const headerRe = /^[A-Z][A-Z0-9 ()'/-]*:$/
  const lines = prompt.split("\n")
  const sections: { label: string; text: string }[] = []
  let current = { label: "preamble", text: "" }
  for (const line of lines) {
    const trimmed = line.trim()
    if (trimmed.length < 60 && headerRe.test(trimmed)) {
      if (current.text.trim()) sections.push(current)
      current = { label: trimmed.replace(/:$/, "").toLowerCase(), text: "" }
    } else {
      current.text += line + "\n"
    }
  }
  if (current.text.trim()) sections.push(current)
  return sections
}

function fmtMs(ms: number) {
  if (ms < 1000) return `${ms} ms`
  return `${(ms / 1000).toFixed(1)} s`
}

export default function Activity() {
  const { pid, hearth } = useOutletContext<HearthContext>()
  const running = useRunStore((s) => !!s.runs[hearth.id])
  const { data: calls } = useCalls(pid, { poll: running })
  const [selected, setSelected] = useState<number | null>(null)

  const sorted = useMemo(() => [...(calls ?? [])].sort((a, b) => b.ts - a.ts), [calls])
  const picked: CallLogEntry | undefined = selected !== null ? sorted[selected] : sorted[0]
  const sections = useMemo(() => (picked ? splitSections(picked.prompt) : []), [picked])
  const totalChars = sections.reduce((n, s) => n + s.text.length, 0) || 1

  if (!calls) return <div className="p-7 text-[13px] text-dim">Loading…</div>

  return (
    <div className="grid h-full grid-cols-[1fr_1.15fr]">
      <div className="overflow-y-auto border-r border-line">
        {sorted.length === 0 ? (
          <div className="p-5 text-[13px] text-dim">No model calls yet for this generation.</div>
        ) : (
          sorted.map((c, i) => (
            <button
              key={i}
              onClick={() => setSelected(i)}
              className={`block w-full border-b border-line px-4 py-2.5 text-left ${
                (selected ?? 0) === i ? "bg-coal shadow-[inset_2px_0_0_var(--color-ember)]" : "hover:bg-coal/50"
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="truncate font-mono text-[12px] text-bone">{c.torch ?? "(unknown torch)"}</span>
                <span className={`font-mono text-[11px] ${c.fake ? "text-dim" : "text-ash"}`}>
                  {c.fake ? "fake" : fmtMs(c.durationMs)}
                </span>
              </div>
              <div className="mt-0.5 truncate text-[12px] text-ash">{c.reply || "(no usable reply)"}</div>
            </button>
          ))
        )}
      </div>

      <div className="overflow-y-auto p-4">
        {!picked ? (
          <div className="text-[13px] text-dim">Select a call to inspect it.</div>
        ) : (
          <div className="grid gap-4">
            <div className="flex items-center justify-between">
              <h3 className="font-mono text-[14px] text-bone">{picked.torch ?? "(unknown torch)"}</h3>
              {picked.fake && (
                <span className="rounded bg-coal px-1.5 py-0.5 font-mono text-[10px] text-dim uppercase">
                  fake model
                </span>
              )}
            </div>

            <div className="flex flex-wrap gap-5">
              <Metric label="wall time" value={fmtMs(picked.durationMs)} />
              <Metric label="prompt tokens" value={picked.promptTokens?.toLocaleString() ?? "—"} />
              <Metric label="reply tokens" value={picked.replyTokens?.toLocaleString() ?? "—"} />
              <Metric label="model" value={picked.model} mono />
            </div>

            {sections.length > 1 && (
              <div>
                <div className="flex h-2 gap-px overflow-hidden rounded-full">
                  {sections.map((s, i) => (
                    <div
                      key={i}
                      title={`${s.label}: ${s.text.length} chars`}
                      style={{ width: `${(s.text.length / totalChars) * 100}%`, background: SECTION_COLORS[i % SECTION_COLORS.length] }}
                    />
                  ))}
                </div>
                <div className="mt-1.5 flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-ash">
                  {sections.map((s, i) => (
                    <span key={i} className="flex items-center gap-1">
                      <span className="h-1.5 w-1.5 rounded-sm" style={{ background: SECTION_COLORS[i % SECTION_COLORS.length] }} />
                      {s.label} ({s.text.length})
                    </span>
                  ))}
                </div>
              </div>
            )}

            <details className="rounded-md border border-line bg-soot" open={sections.length <= 1}>
              <summary className="cursor-pointer px-3 py-2 font-mono text-[11px] text-ash">full prompt</summary>
              <pre className="max-h-[40vh] overflow-auto border-t border-line p-3 font-mono text-[11.5px] whitespace-pre-wrap text-bone">
                {picked.prompt}
              </pre>
            </details>

            <div>
              <div className="mb-1.5 text-[11px] tracking-wide text-dim uppercase">Reply</div>
              <pre className="max-h-[30vh] overflow-auto rounded-md border border-[#4a2e15] bg-emberbg p-3 font-mono text-[12px] whitespace-pre-wrap text-ember2">
                {picked.reply || "(no usable reply)"}
              </pre>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function Metric({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div>
      <div className={`tabular-nums text-[13px] ${mono ? "font-mono" : "font-display font-[500]"} text-bone`}>
        {value}
      </div>
      <div className="text-[11px] text-dim">{label}</div>
    </div>
  )
}
