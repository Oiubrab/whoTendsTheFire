import * as Dialog from "@radix-ui/react-dialog"
import { useState } from "react"
import { toast } from "sonner"
import { api } from "../api/client"
import type { GraphNode } from "../api/types"
import { useInvalidateRun } from "../api/hooks"
import { GraphChip } from "./Badges"

// Clicking a kindling torch's "Propose the next generation" action
// outside autoRun -- this is the step-by-step path's equivalent of
// ApprovalDialog, with a free-text invocation instead of one the model
// already wrote. Replaces the old UI's window.prompt() pair entirely.
export function ManualKindleDialog({
  pid,
  hearth,
  node,
  offerable,
  onClose,
}: {
  pid: string
  hearth: string
  node: GraphNode
  offerable: string[]
  onClose: () => void
}) {
  const [invocation, setInvocation] = useState("")
  const [graph, setGraph] = useState(offerable[0] ?? "")
  const [busy, setBusy] = useState(false)
  const invalidate = useInvalidateRun()

  const submit = async () => {
    const trimmed = invocation.trim()
    setBusy(true)
    try {
      if (!trimmed) {
        await api.light(pid, node.id, "decline")
      } else {
        await api.light(pid, node.id, "written")
        const spawned = await api.kindle(pid, trimmed, graph)
        await api.light(pid, "choose.graph", graph)
        invalidate(spawned.pid, hearth)
        toast.success(`generation ${spawned.state.generation} kindled: ${graph}`)
      }
      invalidate(pid, hearth)
      onClose()
    } catch (e) {
      toast.error((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog.Root open onOpenChange={(o) => !o && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/60" />
        <Dialog.Content className="fixed top-1/2 left-1/2 z-50 w-full max-w-lg -translate-x-1/2 -translate-y-1/2 rounded-xl border border-line2 bg-char p-5">
          <Dialog.Title className="font-display text-[17px] font-[650] text-bone">
            What should the next generation build?
          </Dialog.Title>
          <Dialog.Description className="mt-1 text-[12.5px] text-ash">{node.rite}</Dialog.Description>
          <textarea
            autoFocus
            value={invocation}
            onChange={(e) => setInvocation(e.target.value)}
            rows={2}
            placeholder="Leave blank to decline and end this lineage"
            className="mt-3.5 w-full resize-none rounded-md border border-line2 bg-soot px-3 py-2 text-[14px] text-bone outline-none placeholder:text-dim focus:border-ember"
          />
          {invocation.trim() && (
            <>
              <div className="mt-3 text-[11px] tracking-wide text-dim uppercase">Arrangement</div>
              <div className="mt-1.5 flex flex-wrap gap-1.5">
                {offerable.map((g) => (
                  <button
                    key={g}
                    onClick={() => setGraph(g)}
                    className={`rounded-md border px-2.5 py-1 font-mono text-[12px] ${
                      graph === g ? "border-ember bg-emberbg text-ember2" : "border-line2 text-ash hover:text-bone"
                    }`}
                  >
                    {g}
                  </button>
                ))}
              </div>
              {graph && <div className="mt-2"><GraphChip id={graph} /></div>}
            </>
          )}
          <div className="mt-4.5 flex justify-end gap-2">
            <Dialog.Close className="rounded-md border border-line2 px-3.5 py-1.5 text-[13px] text-ash hover:text-bone">
              Cancel
            </Dialog.Close>
            <button
              onClick={submit}
              disabled={busy || (!!invocation.trim() && !graph)}
              className="rounded-md bg-ember px-3.5 py-1.5 text-[13px] font-semibold text-[#1b1009] hover:bg-ember2 disabled:opacity-50"
            >
              {invocation.trim() ? "Kindle" : "Decline"}
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
