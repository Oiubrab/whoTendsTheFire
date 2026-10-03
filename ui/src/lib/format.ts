export function fmtBytes(n: number): string {
  if (n < 1e6) return `${(n / 1e3).toFixed(0)} KB`
  if (n < 1e9) return `${(n / 1e6).toFixed(1)} MB`
  return `${(n / 1e9).toFixed(1)} GB`
}

export function fmtDate(iso: string): string {
  if (!iso) return ""
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso.slice(0, 16)
  return d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })
}

export function fmtDateShort(iso: string): string {
  if (!iso) return ""
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso.slice(0, 10)
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" })
}
