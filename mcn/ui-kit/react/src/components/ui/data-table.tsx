import * as React from "react"
import { cn, formatValue, humanize, PALETTE } from "@/lib/utils"
import { Icon } from "./icon"

type Row = Record<string, any>

export interface Column {
  key: string
  label?: string
  /** "text" | "number" | "badge" | "date" | "boolean" | "currency" — inferred when omitted */
  type?: string
}

export interface DataTableProps {
  data?: Row[]
  /** Column keys, or column objects; defaults to the keys of the first row */
  columns?: (string | Column)[]
  title?: string
  description?: string
  /** Show the search box (default true) */
  searchable?: boolean
  /** Columns that get a filter dropdown, e.g. ["status", "owner"] */
  filters?: string[]
  page_size?: number
  pageSize?: number
  /** Views to offer: "table", "grid", "list" (default table and grid) */
  views?: string[]
  /** Show an "Export CSV" button (default true) */
  exportable?: boolean
  /** Column used as the card title in grid/list views (default: first column) */
  title_key?: string
  loading?: boolean
  empty?: string
  onRowClick?: (row: Row) => void
  onEdit?: (row: Row) => void
  onDelete?: (row: Row) => void
  /** Label for a primary button in the toolbar, e.g. "New deal" */
  add_label?: string
  onAdd?: () => void
  className?: string
}

const BADGE_KEYS = /^(status|stage|state|priority|type|category|role|level|tier|plan)$/i
const DATE_KEYS = /(date|_at|time|created|updated|due)$/i
const MONEY_KEYS = /(amount|price|value|revenue|cost|total|salary|budget)$/i

function columnType(key: string, rows: Row[]): string {
  const sample = rows.find((r) => r[key] !== null && r[key] !== undefined)?.[key]
  if (BADGE_KEYS.test(key)) return "badge"
  if (typeof sample === "boolean") return "boolean"
  if (typeof sample === "number") return MONEY_KEYS.test(key) ? "currency" : "number"
  if (DATE_KEYS.test(key) && typeof sample === "string" && !isNaN(Date.parse(sample))) return "date"
  return "text"
}

const BADGE_TONES: Record<string, string> = {
  active: "emerald", done: "emerald", completed: "emerald", won: "emerald", paid: "emerald", approved: "emerald", success: "emerald", open: "sky",
  pending: "amber", review: "amber", draft: "slate", "in progress": "sky", in_progress: "sky", new: "sky", proposal: "violet", qualification: "violet",
  lost: "red", failed: "red", rejected: "red", overdue: "red", cancelled: "red", high: "red", urgent: "red", medium: "amber", low: "slate",
}
const TONE_CLASS: Record<string, string> = {
  emerald: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400", sky: "bg-sky-500/10 text-sky-700 dark:text-sky-400",
  amber: "bg-amber-500/10 text-amber-700 dark:text-amber-400", red: "bg-red-500/10 text-red-700 dark:text-red-400",
  violet: "bg-violet-500/10 text-violet-700 dark:text-violet-400", slate: "bg-slate-500/10 text-slate-700 dark:text-slate-300",
}

/** Colored pill for a status-like value; the color comes from the word. */
export function StatusBadge({ value }: { value: unknown }) {
  const text = String(value ?? "")
  const tones = Object.keys(TONE_CLASS)
  const tone = BADGE_TONES[text.toLowerCase()] || tones[[...text].reduce((s, c) => s + c.charCodeAt(0), 0) % tones.length]
  return <span className={cn("inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium", TONE_CLASS[tone])}>{text || "—"}</span>
}

function Cell({ value, type }: { value: any; type: string }) {
  if (type === "badge") return <StatusBadge value={value} />
  if (type === "boolean") return value ? <Icon name="CheckCircle" className="text-emerald-500" /> : <span className="text-muted-foreground">—</span>
  if (type === "currency" && typeof value === "number") return <span className="tabular-nums">{value.toLocaleString(undefined, { maximumFractionDigits: 2 })}</span>
  if (type === "date" && value) return <span className="whitespace-nowrap">{new Date(value).toLocaleDateString()}</span>
  return <span className={cn(type === "number" && "tabular-nums")}>{formatValue(value)}</span>
}

function Avatar({ text }: { text: string }) {
  const initials = text.split(/\s+/).map((w) => w[0]).join("").slice(0, 2).toUpperCase() || "?"
  const color = PALETTE[[...text].reduce((s, c) => s + c.charCodeAt(0), 0) % PALETTE.length]
  return <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full text-xs font-semibold text-white" style={{ background: color }}>{initials}</span>
}

function toCSV(rows: Row[], cols: Column[]): string {
  const esc = (v: unknown) => { const s = v === null || v === undefined ? "" : typeof v === "object" ? JSON.stringify(v) : String(v); return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s }
  return [cols.map((c) => esc(c.label || humanize(c.key))).join(","), ...rows.map((r) => cols.map((c) => esc(r[c.key])).join(","))].join("\n")
}

export interface PaginationProps {
  page: number
  total: number
  pageSize?: number
  page_size?: number
  onPageChange: (page: number) => void
  className?: string
}

/** Page controls: "Showing 11–20 of 84", previous/next and numbered pages. */
export function Pagination({ page, total, pageSize, page_size, onPageChange, className }: PaginationProps) {
  const size = pageSize || page_size || 10
  const pages = Math.max(1, Math.ceil(total / size))
  const p = Math.min(Math.max(1, page), pages)
  const nums: (number | "…")[] = []
  for (let i = 1; i <= pages; i++) {
    if (i === 1 || i === pages || Math.abs(i - p) <= 1) nums.push(i)
    else if (nums[nums.length - 1] !== "…") nums.push("…")
  }
  const btn = "grid h-8 min-w-8 place-items-center rounded-md px-2 text-sm disabled:pointer-events-none disabled:opacity-40"
  return (
    <div className={cn("flex flex-wrap items-center justify-between gap-3 text-sm", className)}>
      <p className="text-muted-foreground">
        {total === 0 ? "No results" : `Showing ${(p - 1) * size + 1}–${Math.min(p * size, total)} of ${total}`}
      </p>
      <nav className="flex items-center gap-1" aria-label="Pagination">
        <button type="button" className={cn(btn, "hover:bg-accent")} disabled={p <= 1} onClick={() => onPageChange(p - 1)} aria-label="Previous page">
          <Icon name="ChevronLeft" />
        </button>
        {nums.map((n, i) => n === "…"
          ? <span key={`e${i}`} className="px-1 text-muted-foreground">…</span>
          : <button key={n} type="button" onClick={() => onPageChange(n)} aria-current={n === p ? "page" : undefined}
              className={cn(btn, n === p ? "bg-primary text-primary-foreground" : "hover:bg-accent")}>{n}</button>)}
        <button type="button" className={cn(btn, "hover:bg-accent")} disabled={p >= pages} onClick={() => onPageChange(p + 1)} aria-label="Next page">
          <Icon name="ChevronRight" />
        </button>
      </nav>
    </div>
  )
}

/**
 * A complete data grid: search, column filters, sorting, pagination,
 * table / grid / list views, CSV export and row actions.
 */
export function DataTable(props: DataTableProps) {
  const rows = Array.isArray(props.data) ? props.data : []
  const size = Number(props.page_size || props.pageSize) || 10
  const views = props.views?.length ? props.views : ["table", "grid"]
  const cols: Column[] = React.useMemo(() => {
    const spec = props.columns?.length ? props.columns : Object.keys(rows[0] || {}).filter((k) => k !== "id").slice(0, 7)
    return spec.map((c) => (typeof c === "string" ? { key: c } : c)).map((c) => ({ ...c, type: c.type || columnType(c.key, rows) }))
  }, [props.columns, rows])
  const titleKey = props.title_key || cols[0]?.key

  const [query, setQuery] = React.useState("")
  const [filterVals, setFilterVals] = React.useState<Record<string, string>>({})
  const [sort, setSort] = React.useState<{ key: string; dir: 1 | -1 } | null>(null)
  const [page, setPage] = React.useState(1)
  const [view, setView] = React.useState(views[0])

  const filtered = React.useMemo(() => {
    const q = query.trim().toLowerCase()
    let out = rows.filter((r) =>
      (!q || cols.some((c) => String(r[c.key] ?? "").toLowerCase().includes(q))) &&
      Object.entries(filterVals).every(([k, v]) => !v || String(r[k] ?? "") === v))
    if (sort) {
      out = [...out].sort((a, b) => {
        const x = a[sort.key], y = b[sort.key]
        if (x === y) return 0
        if (x === null || x === undefined) return 1
        if (y === null || y === undefined) return -1
        return (typeof x === "number" && typeof y === "number" ? x - y : String(x).localeCompare(String(y))) * sort.dir
      })
    }
    return out
  }, [rows, cols, query, filterVals, sort])

  React.useEffect(() => { setPage(1) }, [query, filterVals, rows.length])
  const pageRows = filtered.slice((page - 1) * size, page * size)
  const hasActions = !!(props.onEdit || props.onDelete)
  const filterKeys = props.filters || []

  const exportCSV = () => {
    const blob = new Blob([toCSV(filtered, cols)], { type: "text/csv" })
    const a = document.createElement("a")
    a.href = URL.createObjectURL(blob); a.download = `${(props.title || "data").toLowerCase().replace(/\s+/g, "-")}.csv`; a.click()
    URL.revokeObjectURL(a.href)
  }

  const actions = (r: Row) => hasActions && (
    <div className="flex justify-end gap-1">
      {props.onEdit && <button type="button" aria-label="Edit" onClick={(e) => { e.stopPropagation(); props.onEdit!(r) }}
        className="grid h-7 w-7 place-items-center rounded-md text-muted-foreground hover:bg-accent hover:text-foreground"><Icon name="Pencil" size={14} /></button>}
      {props.onDelete && <button type="button" aria-label="Delete" onClick={(e) => { e.stopPropagation(); props.onDelete!(r) }}
        className="grid h-7 w-7 place-items-center rounded-md text-muted-foreground hover:bg-red-500/10 hover:text-red-600"><Icon name="Trash2" size={14} /></button>}
    </div>
  )

  return (
    <div className={cn("rounded-xl border bg-card text-card-foreground shadow-sm", props.className)}>
      {(props.title || props.description) && (
        <div className="flex flex-wrap items-start justify-between gap-3 px-5 pt-5">
          <div>
            {props.title && <h3 className="font-semibold tracking-tight">{props.title}</h3>}
            {props.description && <p className="mt-0.5 text-sm text-muted-foreground">{props.description}</p>}
          </div>
          {props.add_label && props.onAdd && (
            <button type="button" onClick={props.onAdd}
              className="inline-flex h-9 items-center gap-1.5 rounded-lg bg-primary px-3 text-sm font-medium text-primary-foreground hover:bg-primary/90">
              <Icon name="Plus" size={15} />{props.add_label}
            </button>
          )}
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2 px-5 py-4">
        {props.searchable !== false && (
          <label className="relative min-w-[12rem] flex-1">
            <Icon name="Search" size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <input type="search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search…" aria-label="Search"
              className="h-9 w-full rounded-lg border border-input bg-background pl-9 pr-3 text-sm outline-none focus:ring-2 focus:ring-ring" />
          </label>
        )}
        {filterKeys.map((k) => {
          const options = [...new Set(rows.map((r) => r[k]).filter((v) => v !== null && v !== undefined && v !== ""))].map(String).sort()
          return (
            <select key={k} value={filterVals[k] || ""} onChange={(e) => setFilterVals({ ...filterVals, [k]: e.target.value })}
              aria-label={`Filter by ${humanize(k)}`}
              className="h-9 rounded-lg border border-input bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring">
              <option value="">All {humanize(k).toLowerCase()}</option>
              {options.map((o) => <option key={o} value={o}>{o}</option>)}
            </select>
          )
        })}
        {Object.values(filterVals).some(Boolean) && (
          <button type="button" onClick={() => setFilterVals({})} className="h-9 rounded-lg px-2 text-sm text-muted-foreground hover:text-foreground">Clear</button>
        )}
        <div className="ml-auto flex items-center gap-2">
          {props.exportable !== false && (
            <button type="button" onClick={exportCSV} disabled={!filtered.length}
              className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-input px-3 text-sm hover:bg-accent disabled:opacity-40">
              <Icon name="Download" size={15} />Export
            </button>
          )}
          {views.length > 1 && (
            <div className="flex rounded-lg border border-input p-0.5" role="group" aria-label="View">
              {views.map((v) => (
                <button key={v} type="button" onClick={() => setView(v)} aria-pressed={view === v} aria-label={`${v} view`}
                  className={cn("grid h-7 w-8 place-items-center rounded-md", view === v ? "bg-accent text-foreground" : "text-muted-foreground hover:text-foreground")}>
                  <Icon name={v === "grid" ? "LayoutGrid" : v === "list" ? "LayoutList" : "Table"} size={15} />
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {props.loading ? (
        <div className="space-y-2 px-5 pb-5">{Array.from({ length: 5 }).map((_, i) => <div key={i} className="h-10 animate-pulse rounded-md bg-muted" />)}</div>
      ) : filtered.length === 0 ? (
        <div className="flex flex-col items-center gap-2 px-5 pb-10 pt-6 text-center">
          <span className="grid h-11 w-11 place-items-center rounded-full bg-muted"><Icon name={rows.length ? "Search" : "Inbox"} size={20} className="text-muted-foreground" /></span>
          <p className="text-sm font-medium">{rows.length ? "No matches" : props.empty || "Nothing here yet"}</p>
          {rows.length > 0 && <p className="text-sm text-muted-foreground">Try a different search or clear the filters.</p>}
        </div>
      ) : view === "table" ? (
        <div className="overflow-x-auto border-t">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/40">
                {cols.map((c) => {
                  const active = sort?.key === c.key
                  return (
                    <th key={c.key} className={cn("h-10 px-4 text-left font-medium text-muted-foreground", (c.type === "number" || c.type === "currency") && "text-right")}>
                      <button type="button" className="inline-flex items-center gap-1 hover:text-foreground"
                        onClick={() => setSort(active ? (sort!.dir === 1 ? { key: c.key, dir: -1 } : null) : { key: c.key, dir: 1 })}>
                        {c.label || humanize(c.key)}
                        <Icon name={active ? (sort!.dir === 1 ? "ArrowUp" : "ArrowDown") : "ChevronDown"} size={13} className={cn(!active && "opacity-30")} />
                      </button>
                    </th>
                  )
                })}
                {hasActions && <th className="h-10 w-20 px-4" />}
              </tr>
            </thead>
            <tbody>
              {pageRows.map((r, i) => (
                <tr key={r.id ?? i} onClick={() => props.onRowClick?.(r)}
                  className={cn("border-b last:border-0 hover:bg-muted/40", props.onRowClick && "cursor-pointer")}>
                  {cols.map((c) => (
                    <td key={c.key} className={cn("px-4 py-3", (c.type === "number" || c.type === "currency") && "text-right")}>
                      <Cell value={r[c.key]} type={c.type!} />
                    </td>
                  ))}
                  {hasActions && <td className="px-4 py-2">{actions(r)}</td>}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : view === "grid" ? (
        <div className="grid gap-3 border-t p-5 sm:grid-cols-2 xl:grid-cols-3">
          {pageRows.map((r, i) => (
            <div key={r.id ?? i} onClick={() => props.onRowClick?.(r)}
              className={cn("rounded-lg border bg-background p-4 transition-shadow hover:shadow-md", props.onRowClick && "cursor-pointer")}>
              <div className="mb-3 flex items-center gap-3">
                <Avatar text={String(r[titleKey] ?? "")} />
                <p className="min-w-0 flex-1 truncate font-medium">{formatValue(r[titleKey])}</p>
                {actions(r)}
              </div>
              <dl className="space-y-1.5 text-sm">
                {cols.filter((c) => c.key !== titleKey).slice(0, 4).map((c) => (
                  <div key={c.key} className="flex items-center justify-between gap-3">
                    <dt className="text-muted-foreground">{c.label || humanize(c.key)}</dt>
                    <dd className="truncate text-right"><Cell value={r[c.key]} type={c.type!} /></dd>
                  </div>
                ))}
              </dl>
            </div>
          ))}
        </div>
      ) : (
        <ul className="divide-y border-t">
          {pageRows.map((r, i) => (
            <li key={r.id ?? i} onClick={() => props.onRowClick?.(r)}
              className={cn("flex items-center gap-3 px-5 py-3 hover:bg-muted/40", props.onRowClick && "cursor-pointer")}>
              <Avatar text={String(r[titleKey] ?? "")} />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium">{formatValue(r[titleKey])}</p>
                <p className="truncate text-xs text-muted-foreground">
                  {cols.filter((c) => c.key !== titleKey && c.type !== "badge").slice(0, 3).map((c) => formatValue(r[c.key])).join(" · ")}
                </p>
              </div>
              {cols.filter((c) => c.type === "badge").slice(0, 1).map((c) => <StatusBadge key={c.key} value={r[c.key]} />)}
              {actions(r)}
            </li>
          ))}
        </ul>
      )}

      {!props.loading && filtered.length > size && (
        <div className="border-t px-5 py-3">
          <Pagination page={page} total={filtered.length} pageSize={size} onPageChange={setPage} />
        </div>
      )}
    </div>
  )
}
