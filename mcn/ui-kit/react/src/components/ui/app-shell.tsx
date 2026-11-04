import * as React from "react"
import { cn } from "@/lib/utils"
import { Icon } from "./icon"
import { Breadcrumb } from "./breadcrumb"
import { NotificationBell, Toaster } from "./toast"

/* The frame every MCN app renders in: navigation (collapsible sidebar, tabs or
   top bar), a header with breadcrumb, search, notifications, theme toggle and
   user menu, a footer, and the toast stack. The active section is kept in the
   URL hash, so links and the back button work. */

export interface NavItem {
  label: string
  icon?: string
  element?: React.ReactNode
  /** Small count shown next to the label */
  badge?: string | number
  /** Group heading this item appears under in the sidebar */
  group?: string
}

export interface AppShellProps {
  title: string
  nav: NavItem[]
  /** "sidebar" (default), "tabs" or "top" */
  layout?: "sidebar" | "tabs" | "top"
  /** Text in the footer; omit for the default */
  footer?: React.ReactNode
  user?: { name: string; email?: string }
  logo?: string
  /** Show the header search (default true) */
  search?: boolean
  children?: React.ReactNode
}

const slug = (s: string) => s.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "")
const read = (k: string) => { try { return localStorage.getItem(k) } catch { return null } }
const write = (k: string, v: string) => { try { localStorage.setItem(k, v) } catch { /* private mode */ } }

function useActive(nav: NavItem[]) {
  const fromHash = () => {
    const h = decodeURIComponent(window.location.hash.replace(/^#\/?/, ""))
    return nav.find((n) => slug(n.label) === h)?.label || nav[0]?.label || ""
  }
  const [active, setActive] = React.useState(fromHash)
  React.useEffect(() => {
    const on = () => setActive(fromHash())
    window.addEventListener("hashchange", on)
    return () => window.removeEventListener("hashchange", on)
  })
  const go = (label: string) => { window.location.hash = "/" + slug(label); setActive(label) }
  return [active, go] as const
}

function useTheme() {
  const [dark, setDark] = React.useState(() => read("mcn-theme") === "dark" ||
    (read("mcn-theme") === null && typeof matchMedia !== "undefined" && matchMedia("(prefers-color-scheme: dark)").matches))
  React.useEffect(() => { document.documentElement.classList.toggle("dark", dark) }, [dark])
  return [dark, () => { write("mcn-theme", dark ? "light" : "dark"); setDark(!dark) }] as const
}

function CommandPalette({ nav, onPick, onClose }: { nav: NavItem[]; onPick: (l: string) => void; onClose: () => void }) {
  const [q, setQ] = React.useState("")
  const [sel, setSel] = React.useState(0)
  const hits = nav.filter((n) => n.label.toLowerCase().includes(q.toLowerCase()))
  return (
    <div className="fixed inset-0 z-[90] flex items-start justify-center bg-black/40 p-4 pt-[12vh]" onMouseDown={onClose}>
      <div className="w-full max-w-lg overflow-hidden rounded-xl border bg-popover text-popover-foreground shadow-2xl" onMouseDown={(e) => e.stopPropagation()}>
        <div className="flex items-center gap-2 border-b px-4">
          <Icon name="Search" size={16} className="text-muted-foreground" />
          <input autoFocus value={q} placeholder="Go to…" aria-label="Search sections"
            onChange={(e) => { setQ(e.target.value); setSel(0) }}
            onKeyDown={(e) => {
              if (e.key === "ArrowDown") { setSel(Math.min(sel + 1, hits.length - 1)); e.preventDefault() }
              if (e.key === "ArrowUp") { setSel(Math.max(sel - 1, 0)); e.preventDefault() }
              if (e.key === "Enter" && hits[sel]) onPick(hits[sel].label)
              if (e.key === "Escape") onClose()
            }}
            className="h-12 flex-1 bg-transparent text-sm outline-none" />
          <kbd className="rounded border px-1.5 py-0.5 text-[10px] text-muted-foreground">Esc</kbd>
        </div>
        <ul className="max-h-72 overflow-y-auto p-2">
          {hits.length === 0 && <li className="px-3 py-6 text-center text-sm text-muted-foreground">No matches</li>}
          {hits.map((n, i) => (
            <li key={n.label}>
              <button type="button" onMouseEnter={() => setSel(i)} onClick={() => onPick(n.label)}
                className={cn("flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left text-sm", i === sel && "bg-accent")}>
                <Icon name={n.icon || "Circle"} size={16} className="text-muted-foreground" />{n.label}
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}

function UserMenu({ user }: { user: { name: string; email?: string } }) {
  const [open, setOpen] = React.useState(false)
  const initials = user.name.split(/\s+/).map((w) => w[0]).join("").slice(0, 2).toUpperCase()
  return (
    <div className="relative">
      <button type="button" onClick={() => setOpen(!open)} aria-label="Account"
        className="grid h-8 w-8 place-items-center rounded-full bg-primary text-xs font-semibold text-primary-foreground">{initials}</button>
      {open && (
        <div className="absolute right-0 z-50 mt-2 w-56 rounded-xl border bg-popover p-1 text-popover-foreground shadow-xl" onMouseLeave={() => setOpen(false)}>
          <div className="px-3 py-2"><p className="text-sm font-medium">{user.name}</p>{user.email && <p className="truncate text-xs text-muted-foreground">{user.email}</p>}</div>
          <div className="my-1 h-px bg-border" />
          <button type="button" className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm hover:bg-accent"><Icon name="Settings" size={15} />Settings</button>
          <button type="button" className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm hover:bg-accent"><Icon name="LogOut" size={15} />Sign out</button>
        </div>
      )}
    </div>
  )
}

export function AppShell({ title, nav, layout = "sidebar", footer, user, logo, search = true, children }: AppShellProps) {
  const [active, go] = useActive(nav)
  const [dark, toggleTheme] = useTheme()
  const [collapsed, setCollapsed] = React.useState(() => read("mcn-sidebar") === "collapsed")
  const [mobileOpen, setMobileOpen] = React.useState(false)
  const [palette, setPalette] = React.useState(false)
  const current = nav.find((n) => n.label === active)

  React.useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setPalette((p) => !p) }
      if ((e.metaKey || e.ctrlKey) && e.key === "\\") { e.preventDefault(); toggleCollapse() }
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  })
  React.useEffect(() => { document.title = current ? `${current.label} · ${title}` : title }, [current, title])
  const toggleCollapse = () => setCollapsed((c) => { write("mcn-sidebar", c ? "expanded" : "collapsed"); return !c })
  const pick = (label: string) => { go(label); setMobileOpen(false); setPalette(false) }

  const brand = (compact: boolean) => (
    <div className="flex min-w-0 items-center gap-2.5">
      <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-primary text-primary-foreground"><Icon name={logo || "Sparkles"} size={16} /></span>
      {!compact && <span className="truncate font-semibold tracking-tight">{title}</span>}
    </div>
  )

  const groups: [string, NavItem[]][] = []
  nav.forEach((n) => {
    const g = groups.find(([name]) => name === (n.group || ""))
    if (g) g[1].push(n); else groups.push([n.group || "", [n]])
  })

  const sideNav = (compact: boolean) => (
    <nav className="flex-1 space-y-4 overflow-y-auto px-3 py-2" aria-label="Main">
      {groups.map(([group, items]) => (
        <div key={group} className="space-y-0.5">
          {group && !compact && <p className="px-3 pb-1 pt-2 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">{group}</p>}
          {items.map((n) => {
            const on = n.label === active
            return (
              <button key={n.label} type="button" onClick={() => pick(n.label)} title={compact ? n.label : undefined}
                aria-current={on ? "page" : undefined}
                className={cn("group flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                  compact && "justify-center px-0",
                  on ? "bg-primary/10 text-primary" : "text-muted-foreground hover:bg-accent hover:text-foreground")}>
                <Icon name={n.icon || "Circle"} size={18} />
                {!compact && <span className="flex-1 truncate text-left">{n.label}</span>}
                {!compact && n.badge !== undefined && (
                  <span className="rounded-full bg-muted px-2 py-0.5 text-[11px] text-muted-foreground">{n.badge}</span>
                )}
              </button>
            )
          })}
        </div>
      ))}
    </nav>
  )

  const content = children ?? current?.element
  const footerEl = (
    <footer className="border-t px-6 py-4 text-xs text-muted-foreground">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span>{footer ?? `© ${new Date().getFullYear()} ${title}`}</span>
        <span>Built with MCN</span>
      </div>
    </footer>
  )

  const headerTools = (
    <div className="ml-auto flex items-center gap-1">
      {search && (
        <button type="button" onClick={() => setPalette(true)}
          className="mr-1 hidden h-9 w-56 items-center gap-2 rounded-lg border border-input bg-background px-3 text-sm text-muted-foreground hover:border-ring sm:flex">
          <Icon name="Search" size={15} /><span className="flex-1 text-left">Search…</span>
          <kbd className="rounded border px-1.5 text-[10px]">⌘K</kbd>
        </button>
      )}
      {search && (
        <button type="button" onClick={() => setPalette(true)} aria-label="Search"
          className="grid h-9 w-9 place-items-center rounded-lg text-muted-foreground hover:bg-accent sm:hidden"><Icon name="Search" size={18} /></button>
      )}
      <NotificationBell />
      <button type="button" onClick={toggleTheme} aria-label={dark ? "Light mode" : "Dark mode"}
        className="grid h-9 w-9 place-items-center rounded-lg text-muted-foreground hover:bg-accent hover:text-foreground">
        <Icon name={dark ? "Sun" : "Moon"} size={18} />
      </button>
      {user && <div className="ml-1"><UserMenu user={user} /></div>}
    </div>
  )

  if (layout !== "sidebar") {
    return (
      <div className="flex min-h-screen flex-col bg-background text-foreground">
        <header className="sticky top-0 z-30 border-b bg-background/85 backdrop-blur">
          <div className="mx-auto flex h-14 max-w-7xl items-center gap-4 px-4 sm:px-6">
            {brand(false)}
            {layout === "top" && (
              <nav className="ml-4 hidden gap-1 md:flex" aria-label="Main">
                {nav.map((n) => (
                  <button key={n.label} type="button" onClick={() => pick(n.label)} aria-current={n.label === active ? "page" : undefined}
                    className={cn("rounded-lg px-3 py-1.5 text-sm font-medium", n.label === active ? "bg-accent text-foreground" : "text-muted-foreground hover:text-foreground")}>
                    {n.label}
                  </button>
                ))}
              </nav>
            )}
            {headerTools}
          </div>
          {(layout === "tabs" || nav.length > 1) && (
            <div className={cn("mx-auto max-w-7xl px-4 sm:px-6", layout === "top" && "md:hidden")}>
              <div className="-mb-px flex gap-1 overflow-x-auto" role="tablist">
                {nav.map((n) => (
                  <button key={n.label} type="button" role="tab" aria-selected={n.label === active} onClick={() => pick(n.label)}
                    className={cn("flex shrink-0 items-center gap-2 border-b-2 px-3 py-2.5 text-sm font-medium",
                      n.label === active ? "border-primary text-foreground" : "border-transparent text-muted-foreground hover:text-foreground")}>
                    <Icon name={n.icon || "Circle"} size={15} />{n.label}
                  </button>
                ))}
              </div>
            </div>
          )}
        </header>
        <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:px-6">{content}</main>
        {footerEl}
        {palette && <CommandPalette nav={nav} onPick={pick} onClose={() => setPalette(false)} />}
        <Toaster />
      </div>
    )
  }

  return (
    <div className="flex min-h-screen bg-background text-foreground">
      <aside className={cn("sticky top-0 hidden h-screen shrink-0 flex-col border-r bg-card transition-[width] duration-200 md:flex",
        collapsed ? "w-[68px]" : "w-64")}>
        <div className={cn("flex h-14 items-center border-b px-4", collapsed && "justify-center px-0")}>{brand(collapsed)}</div>
        {sideNav(collapsed)}
        <div className="border-t p-3">
          <button type="button" onClick={toggleCollapse} aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"} title="Toggle sidebar (Ctrl+\)"
            className={cn("flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm text-muted-foreground hover:bg-accent hover:text-foreground", collapsed && "justify-center px-0")}>
            <Icon name={collapsed ? "PanelLeftOpen" : "PanelLeftClose"} size={18} />{!collapsed && "Collapse"}
          </button>
        </div>
      </aside>

      {mobileOpen && (
        <div className="fixed inset-0 z-50 md:hidden">
          <div className="absolute inset-0 bg-black/40" onClick={() => setMobileOpen(false)} />
          <aside className="absolute inset-y-0 left-0 flex w-72 max-w-[85vw] flex-col bg-card shadow-xl">
            <div className="flex h-14 items-center justify-between border-b px-4">
              {brand(false)}
              <button type="button" onClick={() => setMobileOpen(false)} aria-label="Close menu" className="grid h-8 w-8 place-items-center rounded-lg hover:bg-accent"><Icon name="X" /></button>
            </div>
            {sideNav(false)}
          </aside>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b bg-background/85 px-4 backdrop-blur sm:px-6">
          <button type="button" onClick={() => setMobileOpen(true)} aria-label="Open menu"
            className="grid h-9 w-9 place-items-center rounded-lg text-muted-foreground hover:bg-accent md:hidden"><Icon name="Menu" size={18} /></button>
          <Breadcrumb items={[title, active].filter(Boolean)} />
          {headerTools}
        </header>
        <main className="flex-1 px-4 py-6 sm:px-6">{content}</main>
        {footerEl}
      </div>
      {palette && <CommandPalette nav={nav} onPick={pick} onClose={() => setPalette(false)} />}
      <Toaster />
    </div>
  )
}
