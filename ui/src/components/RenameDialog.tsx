import * as Dialog from "@radix-ui/react-dialog"
import { useState } from "react"
import { toast } from "sonner"
import type { Hearth } from "../api/types"
import { api } from "../api/client"
import { useInvalidateRun } from "../api/hooks"

export function RenameDialog({ hearth, onClose }: { hearth: Hearth; onClose: () => void }) {
  const [label, setLabel] = useState(hearth.label)
  const [saving, setSaving] = useState(false)
  const invalidate = useInvalidateRun()

  const save = async () => {
    setSaving(true)
    try {
      await api.label(hearth.id, label.trim())
      invalidate(undefined, hearth.id)
      onClose()
    } catch (err) {
      toast.error((err as Error).message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog.Root open onOpenChange={(o) => !o && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/60" />
        <Dialog.Content className="fixed top-1/2 left-1/2 z-50 w-full max-w-sm -translate-x-1/2 -translate-y-1/2 rounded-xl border border-line2 bg-char p-5">
          <Dialog.Title className="font-display text-[16px] font-[650] text-bone">Rename hearth</Dialog.Title>
          <Dialog.Description className="mt-1 text-[12.5px] text-ash">
            {hearth.ember}
          </Dialog.Description>
          <input
            autoFocus
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && save()}
            placeholder={hearth.id}
            className="mt-4 w-full rounded-md border border-line2 bg-soot px-3 py-2 text-[14px] text-bone outline-none focus:border-ember"
          />
          <div className="mt-4 flex justify-end gap-2">
            <Dialog.Close className="rounded-md border border-line2 px-3.5 py-1.5 text-[13px] text-ash hover:text-bone">
              Cancel
            </Dialog.Close>
            <button
              onClick={save}
              disabled={saving}
              className="rounded-md bg-ember px-3.5 py-1.5 text-[13px] font-semibold text-[#1b1009] hover:bg-ember2 disabled:opacity-50"
            >
              Save
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
