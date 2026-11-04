import * as React from "react"
import { cn, formatValue, humanize } from "@/lib/utils"
import { StatusBadge } from "./data-table"

type Row = Record<string, any>

export interface KanbanProps {
  data?: Row[]
  /** Field that decides the column, e.g. "stage" */
  group_by?: string
  /** Column order; defaults to the values found in the data */
  columns?: string[]
  title_key?: string
  /** Extra fields shown on each card */
  fields?: string[]
  /** Called after a card is dropped in another column */
  onMove?: (item: Row, to: string) => Promise<any> | any
  onCardClick?: (item: Row) => void
  className?: string
}

/** Board with a column per value of `group_by`; drag cards between columns. */
export function Kanban({ data, group_by = "status", columns, title_key, fields, onMove, onCardClick, className }: KanbanProps) {
  const [items, setItems] = React.useState<Row[]>(Array.isArray(data) ? data : [])
  const [over, setOver] = React.useState<string | null>(null)
  React.useEffect(() => { setItems(Array.isArray(data) ? data : []) }, [data])
  const cols = columns?.length ? columns : [...new Set(items.map((r) => String(r[group_by] ?? "Other")))]
  const titleKey = title_key || Object.keys(items[0] || {}).find((k) => k !== "id" && k !== group_by) || "title"
  const extra = fields || Object.keys(items[0] || {}).filter((k) => ![titleKey, group_by, "id"].includes(k)).slice(0, 2)

  const drop = async (col: string, e: React.DragEvent) => {
    e.preventDefault(); setOver(null)
    const idx = Number(e.dataTransfer.getData("text/plain"))
    const item = items[idx]
    if (!item || String(item[group_by]) === col) return
    const moved = { ...item, [group_by]: col }
    setItems(items.map((r, i) => (i === idx ? moved : r)))
    try { await onMove?.(moved, col) } catch { setItems(items) }
  }

  return (
    <div className={cn("flex gap-4 overflow-x-auto pb-2", className)}>
      {cols.map((col) => {
        const cards = items.map((r, i) => [r, i] as const).filter(([r]) => String(r[group_by] ?? "Other") === col)
        return (
          <div key={col} onDragOver={(e) => { e.preventDefault(); setOver(col) }} onDragLeave={() => setOver(null)} onDrop={(e) => drop(col, e)}
            className={cn("flex w-72 shrink-0 flex-col rounded-xl border bg-muted/40 transition-colors", over === col && "border-primary bg-primary/5")}>
            <div className="flex items-center justify-between px-3 py-2.5">
              <span className="text-sm font-semibold">{col}</span>
              <span className="rounded-full bg-background px-2 py-0.5 text-xs text-muted-foreground">{cards.length}</span>
            </div>
            <div className="flex min-h-[80px] flex-1 flex-col gap-2 px-2 pb-2">
              {cards.map(([r, i]) => (
                <div key={r.id ?? i} draggable onDragStart={(e) => e.dataTransfer.setData("text/plain", String(i))} onClick={() => onCardClick?.(r)}
                  className="cursor-grab rounded-lg border bg-card p-3 shadow-sm hover:shadow-md active:cursor-grabbing">
                  <p className="text-sm font-medium">{formatValue(r[titleKey])}</p>
                  {extra.map((k) => (
                    <p key={k} className="mt-1 flex items-center justify-between gap-2 text-xs text-muted-foreground">
                      <span>{humanize(k)}</span>
                      {/^(status|priority|type)$/i.test(k) ? <StatusBadge value={r[k]} /> : <span className="truncate text-foreground">{formatValue(r[k])}</span>}
                    </p>
                  ))}
                </div>
              ))}
              {cards.length === 0 && <p className="py-6 text-center text-xs text-muted-foreground">Drop cards here</p>}
            </div>
          </div>
        )
      })}
    </div>
  )
}
