import { create } from "zustand"

export type RunMode = "autonomous" | "approve" | "step"

export interface PendingApproval {
  pid: string
  torch: string
  invocation: string
  offerable: string[]
}

export type ApprovalChoice =
  | { action: "accept"; graph: string }
  | { action: "reject" }

// Tracks the ONE lineage this tab is actively auto-driving. Phase 1 keeps
// the walk loop client-side (same as the old UI) -- the server-side
// runner that lets a lineage keep going after the tab closes is Phase 2.
// Until then, this store is what the Run Dock and the "a hearth is
// building in the background" banners read from.
//
// runMode: approve gates runAutoLoop() right after kindle.next proposes
// a sentence -- the loop sets pendingApproval and awaits approvalResolve
// instead of immediately calling choosegraph+kindle, so "approve each
// generation" is real, not just a label, even before the server-side
// runner (Phase 2) exists.
interface RunState {
  pid: string | null
  hearth: string | null
  running: boolean
  stopRequested: boolean
  statusMessage: string
  workingTorch: string | null
  pendingInvocation: string | null
  runMode: RunMode
  pendingApproval: PendingApproval | null
  approvalResolve: ((choice: ApprovalChoice) => void) | null
  start: (pid: string, hearth: string) => void
  stop: () => void
  setRunning: (running: boolean) => void
  setStatus: (msg: string) => void
  setWorking: (torch: string | null) => void
  setPending: (invocation: string | null) => void
  setPid: (pid: string) => void
  setRunMode: (mode: RunMode) => void
  requestApproval: (p: PendingApproval) => Promise<ApprovalChoice>
  resolveApproval: (choice: ApprovalChoice) => void
  clear: () => void
}

export const useRunStore = create<RunState>((set, get) => ({
  pid: null,
  hearth: null,
  running: false,
  stopRequested: false,
  statusMessage: "",
  workingTorch: null,
  pendingInvocation: null,
  runMode: "approve",
  pendingApproval: null,
  approvalResolve: null,
  start: (pid, hearth) => set({ pid, hearth, running: true, stopRequested: false }),
  stop: () => set({ stopRequested: true }),
  setRunning: (running) => set({ running }),
  setStatus: (statusMessage) => set({ statusMessage }),
  setWorking: (workingTorch) => set({ workingTorch }),
  setPending: (pendingInvocation) => set({ pendingInvocation }),
  setPid: (pid) => set({ pid }),
  setRunMode: (runMode) => set({ runMode }),
  requestApproval: (p) =>
    new Promise<ApprovalChoice>((resolve) => {
      set({ pendingApproval: p, approvalResolve: resolve })
    }),
  resolveApproval: (choice) => {
    get().approvalResolve?.(choice)
    set({ pendingApproval: null, approvalResolve: null })
  },
  clear: () =>
    set({
      pid: null,
      hearth: null,
      running: false,
      stopRequested: false,
      statusMessage: "",
      workingTorch: null,
      pendingInvocation: null,
      pendingApproval: null,
      approvalResolve: null,
    }),
}))
