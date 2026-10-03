import * as Dialog from "@radix-ui/react-dialog"
import { useEffect, useState } from "react"
import { useRunStore, type PendingApproval } from "../lib/runStore"
import { api } from "../api/client"
import type { BlockedRow } from "../api/types"
import { GraphChip } from "./Badges"

// The "approve each generation" run mode's gate: kindle.next has already
// proposed a sentence, and this is the one moment before a daughter
// prophecy actually spawns. Reject ends the lineage cleanly (the same
// `decline` path a model-declined generation takes); accept requires
// picking which arrangement fits, defaulted to the model's own
// classification so accepting needs no typing in the common case.
//
// Just a store-reading wrapper: the real component below is remounted
// (via `key`) for every new approval rather than resetting its own state
// in an effect, so there is no synchronous setState-in-effect on open.
export function ApprovalDialog() {
  const pending = useRunStore((s) => s.pendingApproval)
  if (!pending) return null
  return <ApprovalDialogInner key={`${pending.pid}:${pending.torch}:${pending.invocation}`} pending={pending} />
}

function ApprovalDialogInner({ pending }: { pending: PendingApproval }) {
  const resolve = useRunStore((s) => s.resolveApproval)
  const [blocked, setBlocked] = useState<BlockedRow[] | null>(null)
  const [graph, setGraph] = useState<string | null>(null)
  const [suggesting, setSuggesting] = useState(true)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      const [b, c] = await Promise.all([
        api.blocked(pending.pid),
        // "choose.graph" literally -- pending.torch is kindle.next's id
        // (the torch that proposed the invocation), not the decision
        // torch that classifies it. See autorun.ts's matching fix.
        api.choosegraph(pending.pid, "choose.graph", pending.invocation),
      ])
      if (cancelled) return
      setBlocked(b)
      setGraph(c.option)
      setSuggesting(false)
    })()
    return () => {
      cancelled = true
    }
  }, [pending])

  const offerableSet = new Set(pending.offerable)

  return (
    <Dialog.Root open onOpenChange={(o) => !o && resolve({ action: "reject" })}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/60" />
        <Dialog.Content className="fixed top-1/2 left-1/2 z-50 w-full max-w-lg -translate-x-1/2 -translate-y-1/2 rounded-xl border border-line2 bg-char p-5">
          <Dialog.Title className="font-display text-[17px] font-[650] text-bone">
            Approve the next generation?
          </Dialog.Title>
          <Dialog.Description asChild>
            <div className="mt-3 rounded-lg border border-line bg-soot px-3.5 py-3 text-[14px] text-bone italic">
              {pending.invocation}
            </div>
          </Dialog.Description>

          <div className="mt-4 text-[11px] font-medium tracking-wide text-dim uppercase">
            Arrangement {suggesting && <span className="normal-case text-dim/80">— asking the model…</span>}
          </div>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {(blocked ?? pending.offerable.map((g) => ({ graph: g, missing: [] }))).map((row) => {
              const available = blocked ? offerableSet.has(row.graph) : true
              const selected = graph === row.graph
              return (
                <button
                  key={row.graph}
                  disabled={!available}
                  onClick={() => setGraph(row.graph)}
                  title={!available ? `needs ${row.missing.join(", ") || "an earlier choice"}` : undefined}
                  className={`rounded-md border px-2.5 py-1 font-mono text-[12px] transition-colors ${
                    selected
                      ? "border-ember bg-emberbg text-ember2"
                      : available
                        ? "border-line2 text-ash hover:text-bone"
                        : "cursor-not-allowed border-line text-dim/50 line-through"
                  }`}
                >
                  {row.graph}
                </button>
              )
            })}
          </div>
          {graph && <GraphChip id={graph} />}

          <div className="mt-5 flex justify-end gap-2">
            <button
              onClick={() => resolve({ action: "reject" })}
              className="rounded-md border border-line2 px-3.5 py-1.5 text-[13px] text-ash hover:text-bone"
            >
              Reject, end lineage
            </button>
            <button
              onClick={() => graph && resolve({ action: "accept", graph })}
              disabled={!graph}
              className="rounded-md bg-ember px-3.5 py-1.5 text-[13px] font-semibold text-[#1b1009] hover:bg-ember2 disabled:opacity-50"
            >
              Accept &amp; kindle
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
