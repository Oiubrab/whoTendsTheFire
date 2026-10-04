import * as Dialog from "@radix-ui/react-dialog"
import { useEffect, useState } from "react"
import { toast } from "sonner"
import { useRunStore, firstPendingApproval, type PendingApproval } from "../lib/runStore"
import { api } from "../api/client"
import type { BlockedRow } from "../api/types"
import { GraphChip } from "./Badges"

// The "approve each generation" run mode's gate -- now server-driven
// (Phase 2): kindle.next proposed a sentence inside runner.py's
// background thread, which is blocked waiting on POST /api/runs/approve
// for as long as this stays open, from ANY tab, even one that reloaded
// after the run started. The dialog itself still asks the bridge for the
// model's suggested arrangement and which graphs are blocked (and why),
// same as Phase 1 -- that part didn't need the server-side runner to work.
//
// Just a store-reading wrapper: the real component below is remounted
// (via `key`) for every new approval rather than resetting its own state
// in an effect, so there is no synchronous setState-in-effect on open.
export function ApprovalDialog() {
  const pending = useRunStore((s) => firstPendingApproval(s.runs))
  if (!pending) return null
  return <ApprovalDialogInner key={`${pending.hearth}:${pending.pid}:${pending.invocation}`} pending={pending} />
}

function ApprovalDialogInner({ pending }: { pending: PendingApproval }) {
  const upsert = useRunStore((s) => s.upsert)
  const [blocked, setBlocked] = useState<BlockedRow[] | null>(null)
  const [graph, setGraph] = useState<string | null>(null)
  const [suggesting, setSuggesting] = useState(true)
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      const [b, c] = await Promise.all([
        api.blocked(pending.pid),
        // "choose.graph" literally -- the torch that proposed the
        // invocation was kindle.next, not the one that classifies it.
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

  const resolve = async (action: "accept" | "reject", chosenGraph?: string) => {
    setSubmitting(true)
    try {
      await api.runsApprove(pending.hearth, action, chosenGraph)
      // optimistic -- the matching SSE event (kindled/generation_end)
      // will arrive and settle everything properly, but clearing this
      // now means the dialog closes the instant the click is honored
      // instead of waiting on a round trip through the event stream.
      upsert(pending.hearth, { pendingApproval: null })
    } catch (e) {
      toast.error((e as Error).message)
      setSubmitting(false)
    }
  }

  return (
    <Dialog.Root open onOpenChange={(o) => !o && resolve("reject")}>
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
              onClick={() => resolve("reject")}
              disabled={submitting}
              className="rounded-md border border-line2 px-3.5 py-1.5 text-[13px] text-ash hover:text-bone disabled:opacity-50"
            >
              Reject, end lineage
            </button>
            <button
              onClick={() => graph && resolve("accept", graph)}
              disabled={!graph || submitting}
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
