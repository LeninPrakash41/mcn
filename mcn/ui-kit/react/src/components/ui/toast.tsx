import * as React from "react"
import { cn } from "@/lib/utils"
import { Icon } from "./icon"

/* Notifications: toast("Saved") shows a toast and adds it to the history that
   <NotificationBell /> lists. Works from anywhere — components, handlers, services. */

export type NotificationKind = "info" | "success" | "warning" | "error"

export interface Notification {
  id: number
  title: string
  description?: string
  kind: NotificationKind
  time: number
  read: boolean
}

let items: Notification[] = []
let visible: number[] = []
let nextId = 1
const listeners = new Set<() => void>()
const emit = () => listeners.forEach((l) => l())

function push(kind: NotificationKind, title: unknown, opts?: { description?: string; duration?: number }) {
  const n: Notification = { id: nextId++, title: String(title), description: opts?.description, kind, time: Date.now(), read: false }
  items = [n, ...items].slice(0, 50)
  visible = [...visible, n.id]
  emit()
  const duration = opts?.duration ?? (kind === "error" ? 6000 : 3500)
  if (duration > 0) setTimeout(() => dismiss(n.id), duration)
  return n.id
}

export function dismiss(id: number) { visible = visible.filter((v) => v !== id); emit() }

type ToastFn = ((title: unknown, opts?: { description?: string; duration?: number }) => number) & {
  success: ToastFn; error: ToastFn; warning: ToastFn; info: ToastFn
}

export const toast = ((title: unknown, opts?: { description?: string; duration?: number }) => push("info", title, opts)) as ToastFn
toast.success = ((t: unknown, o?: { description?: string }) => push("success", t, o)) as ToastFn
toast.error = ((t: unknown, o?: { description?: string }) => push("error", t, o)) as ToastFn
toast.warning = ((t: unknown, o?: { description?: string }) => push("warning", t, o)) as ToastFn
toast.info = ((t: unknown, o?: { description?: string }) => push("info", t, o)) as ToastFn

/** notify("Saved", "success") — the form MCN's notify() compiles to. */
export function notify(title: unknown, kind: NotificationKind = "info", description?: string) {
  return push(kind, title, { description })
}

export function useNotifications() {
  const [, force] = React.useReducer((x: number) => x + 1, 0)
  React.useEffect(() => { listeners.add(force); return () => { listeners.delete(force) } }, [])
  return {
    items,
    unread: items.filter((n) => !n.read).length,
    markAllRead: () => { items = items.map((n) => ({ ...n, read: true })); emit() },
    clear: () => { items = []; emit() },
  }
}

const STYLE: Record<NotificationKind, { icon: string; color: string }> = {
  info:    { icon: "Info",          color: "text-sky-500" },
  success: { icon: "CheckCircle",   color: "text-emerald-500" },
  warning: { icon: "AlertTriangle", color: "text-amber-500" },
  error:   { icon: "XCircle",       color: "text-red-500" },
}

/** Renders the toast stack. Place once near the root (AppShell already does). */
export function Toaster({ position = "bottom-right" }: { position?: "bottom-right" | "top-right" | "bottom-center" }) {
  const { items: all } = useNotifications()
  const shown = visible.map((id) => all.find((n) => n.id === id)).filter(Boolean) as Notification[]
  const pos = { "bottom-right": "bottom-4 right-4 items-end", "top-right": "top-4 right-4 items-end", "bottom-center": "bottom-4 left-1/2 -translate-x-1/2 items-center" }[position]
  return (
    <div className={cn("pointer-events-none fixed z-[100] flex w-[22rem] max-w-[calc(100vw-2rem)] flex-col gap-2", pos)} aria-live="polite">
      {shown.map((n) => (
        <div key={n.id} role="status"
          className="pointer-events-auto flex w-full items-start gap-3 rounded-lg border bg-popover p-3.5 text-popover-foreground shadow-lg">
          <Icon name={STYLE[n.kind].icon} size={18} className={cn("mt-0.5", STYLE[n.kind].color)} />
          <div className="min-w-0 flex-1">
            <p className="text-sm font-medium">{n.title}</p>
            {n.description && <p className="mt-0.5 text-sm text-muted-foreground">{n.description}</p>}
          </div>
          <button type="button" aria-label="Dismiss" onClick={() => dismiss(n.id)} className="text-muted-foreground hover:text-foreground">
            <Icon name="X" size={14} />
          </button>
        </div>
      ))}
    </div>
  )
}

function ago(t: number) {
  const s = Math.round((Date.now() - t) / 1000)
  return s < 60 ? "just now" : s < 3600 ? `${Math.floor(s / 60)}m ago` : `${Math.floor(s / 3600)}h ago`
}

/** Bell with an unread badge and a panel listing recent notifications. */
export function NotificationBell({ className }: { className?: string }) {
  const { items: all, unread, markAllRead, clear } = useNotifications()
  const [open, setOpen] = React.useState(false)
  const ref = React.useRef<HTMLDivElement>(null)
  React.useEffect(() => {
    if (!open) return
    const close = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false) }
    document.addEventListener("mousedown", close)
    return () => document.removeEventListener("mousedown", close)
  }, [open])
  return (
    <div ref={ref} className={cn("relative", className)}>
      <button type="button" aria-label={`Notifications${unread ? ` (${unread} unread)` : ""}`}
        onClick={() => { setOpen(!open); if (!open) setTimeout(markAllRead, 1200) }}
        className="relative grid h-9 w-9 place-items-center rounded-lg text-muted-foreground hover:bg-accent hover:text-foreground">
        <Icon name="Bell" size={18} />
        {unread > 0 && (
          <span className="absolute right-1 top-1 grid h-4 min-w-4 place-items-center rounded-full bg-red-500 px-1 text-[10px] font-semibold text-white">
            {unread > 9 ? "9+" : unread}
          </span>
        )}
      </button>
      {open && (
        <div className="absolute right-0 z-50 mt-2 w-80 overflow-hidden rounded-xl border bg-popover text-popover-foreground shadow-xl">
          <div className="flex items-center justify-between border-b px-4 py-3">
            <p className="text-sm font-semibold">Notifications</p>
            {all.length > 0 && <button type="button" onClick={clear} className="text-xs text-muted-foreground hover:text-foreground">Clear all</button>}
          </div>
          <ul className="max-h-80 overflow-y-auto">
            {all.length === 0 && <li className="px-4 py-8 text-center text-sm text-muted-foreground">You're all caught up</li>}
            {all.map((n) => (
              <li key={n.id} className={cn("flex gap-3 border-b px-4 py-3 last:border-0", !n.read && "bg-accent/40")}>
                <Icon name={STYLE[n.kind].icon} size={16} className={cn("mt-0.5", STYLE[n.kind].color)} />
                <div className="min-w-0 flex-1">
                  <p className="text-sm">{n.title}</p>
                  {n.description && <p className="text-xs text-muted-foreground">{n.description}</p>}
                  <p className="mt-0.5 text-[11px] text-muted-foreground">{ago(n.time)}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
