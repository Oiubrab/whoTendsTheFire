import { useOutletContext } from "react-router-dom"
import type { HearthContext } from "./HearthLayout"

// Phase 3 ("Seeing inside a run") adds the model-call log this tab is
// meant to show: the exact prompt, the reply, timing and token counts
// per call. That needs server.py to actually record calls, which it
// doesn't yet -- Ollama already returns the numbers, they're just
// discarded today. The torches-lit trail works now, so it's shown below
// as what's available until the call log lands.
export default function Activity() {
  const { state } = useOutletContext<HearthContext>()
  return (
    <div className="mx-auto max-w-3xl px-6 py-6">
      <div className="rounded-xl border border-dashed border-line2 bg-char/50 p-5 text-[13px] text-ash">
        The full Activity view — per-call prompts, replies, timing and token budgets — needs the bridge to start
        recording model calls, which is Phase 3 of the UI plan. Shown below in the meantime: every torch this
        generation has lit, in order.
      </div>
      <div className="mt-5 rounded-xl border border-line bg-char">
        {state.trail.length === 0 ? (
          <div className="p-4 text-[13px] text-dim">nothing lit yet</div>
        ) : (
          [...state.trail].reverse().map((t) => (
            <div key={t.seq} className="flex items-center justify-between border-b border-line px-4 py-2.5 last:border-0">
              <span className="font-mono text-[13px] text-bone">{t.torch}</span>
              <span className={`font-mono text-[12.5px] ${t.option === "fail" ? "text-fail" : "text-ash"}`}>
                {t.option}
              </span>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
