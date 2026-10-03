import { Toaster as Sonner } from "sonner"

export function Toaster() {
  return (
    <Sonner
      theme="dark"
      position="bottom-left"
      toastOptions={{
        style: {
          background: "var(--color-char)",
          border: "1px solid var(--color-line2)",
          color: "var(--color-bone)",
          fontSize: "13px",
        },
      }}
    />
  )
}
