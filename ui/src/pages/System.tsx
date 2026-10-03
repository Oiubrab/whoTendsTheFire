import { useHealth } from "../api/health"
import { useHearths } from "../api/hooks"
import { fmtBytes } from "../lib/format"

export default function System() {
  const { data: health } = useHealth()
  const { data: hearths } = useHearths()
  const totalDisk = (hearths ?? []).reduce((sum, h) => sum + h.diskused, 0)

  return (
    <div className="mx-auto max-w-2xl px-6 py-7">
      <h1 className="font-display text-[22px] font-[650]">System</h1>

      <div className="mt-5 rounded-xl border border-line bg-char p-5">
        <h2 className="text-[12px] font-semibold tracking-wide text-ash uppercase">Bridge</h2>
        <dl className="mt-3 grid grid-cols-2 gap-y-2.5 text-[13.5px]">
          <dt className="text-ash">Status</dt>
          <dd className={health?.bridge ? "text-pass" : "text-fail"}>{health?.bridge ? "up" : "unreachable"}</dd>
          <dt className="text-ash">Port</dt>
          <dd className="font-mono">{health?.port ?? "—"}</dd>
        </dl>
      </div>

      <div className="mt-4 rounded-xl border border-line bg-char p-5">
        <h2 className="text-[12px] font-semibold tracking-wide text-ash uppercase">Model</h2>
        <dl className="mt-3 grid grid-cols-2 gap-y-2.5 text-[13.5px]">
          <dt className="text-ash">Ollama</dt>
          <dd className={health?.ollama ? "text-pass" : "text-fail"}>{health?.ollama ? "reachable" : "unreachable"}</dd>
          <dt className="text-ash">Active model</dt>
          <dd className="font-mono">{health?.model ?? "—"}</dd>
        </dl>
        <p className="mt-3 text-[12px] text-dim">
          A per-hearth model picker, and switching models without editing server.py, is Phase 4 work.
        </p>
      </div>

      <div className="mt-4 rounded-xl border border-line bg-char p-5">
        <h2 className="text-[12px] font-semibold tracking-wide text-ash uppercase">Disk</h2>
        <dl className="mt-3 grid grid-cols-2 gap-y-2.5 text-[13.5px]">
          <dt className="text-ash">Across all hearths</dt>
          <dd className="font-mono">{fmtBytes(totalDisk)}</dd>
          <dt className="text-ash">Hearths</dt>
          <dd className="font-mono">{hearths?.length ?? 0}</dd>
        </dl>
      </div>
    </div>
  )
}
