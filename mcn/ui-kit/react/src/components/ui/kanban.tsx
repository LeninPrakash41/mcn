import * as React from "react"
import { cn, formatValue, humanize } from "@/lib/utils"
import { Icon } from "./icon"
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
  /** Called after a card moves to another column */
  onMove?: (item: Row, to: string) => Promise<any> | any
  onCardClick?: (item: Row) => void
  className?: string
}

interface Drag { index: number; x: number; y: number; dx: number; dy: number; width: number; started: boolean }

/**
 * Board with a column per value of `group_by`. Move cards by dragging them with
 * a mouse, dragging the grip with a finger or pen, or with the arrow keys
 * (← → between columns) when a card has focus.
 */
export function Kanban({ data, group_by = "status", columns, title_key, fields, onMove, onCardClick, className }: KanbanProps) {
  const [items, setItems] = React.useState<Row[]>(Array.isArray(data) ? data : [])
  const [drag, setDrag] = React.useState<Drag | null>(null)
  const [over, setOver] = React.useState<string | null>(null)
  const [announce, setAnnounce] = React.useState("")
  const boardRef = React.useRef<HTMLDivElement>(null)
  React.useEffect(() => { setItems(Array.isArray(data) ? data : []) }, [data])

  const cols = columns?.length ? columns : [...new Set(items.map((r) => String(r[group_by] ?? "Other")))]
  const titleKey = title_key || Object.keys(items[0] || {}).find((k) => k !== "id" && k !== group_by) || "title"
  const extra = fields || Object.keys(items[0] || {}).filter((k) => ![titleKey, group_by, "id"].includes(k)).slice(0, 2)

  const move = async (index: number, to: string) => {
    const item = items[index]
    if (!item || String(item[group_by]) === to) return
    const before = items
    const moved = { ...item, [group_by]: to }
    setItems(items.map((r, i) => (i === index ? moved : r)))
    setAnnounce(`Moved ${formatValue(item[titleKey])} to ${to}`)
    try { await onMove?.(moved, to) } catch { setItems(before); setAnnounce("Move failed") }
  }

  const columnAt = (x: number, y: number): string | null => {
    const el = document.elementFromPoint(x, y)?.closest("[data-kanban-col]")
    return el && boardRef.current?.contains(el) ? el.getAttribute("data-kanban-col") : null
  }

  const start = (e: React.PointerEvent, index: number, fromHandle: boolean) => {
    if (e.button !== 0 || (e.pointerType !== "mouse" && !fromHandle)) return
    const card = (e.currentTarget as HTMLElement).closest("[data-kanban-card]") as HTMLElement
    const rect = card.getBoundingClientRect()
    ;(e.currentTarget as HTMLElement).setPointerCapture(e.pointerId)
    setDrag({ index, x: e.clientX, y: e.clientY, dx: e.clientX - rect.left, dy: e.clientY - rect.top, width: rect.width, started: false })
  }
  const moveDrag = (e: React.PointerEvent) => {
    if (!drag) return
    const started = drag.started || Math.hypot(e.clientX - drag.x, e.clientY - drag.y) > 5
    setDrag({ ...drag, x: e.clientX, y: e.clientY, started })
    if (started) setOver(columnAt(e.clientX, e.clientY))
  }
  const end = (e: React.PointerEvent) => {
    if (!drag) return
    const target = drag.started ? columnAt(e.clientX, e.clientY) : null
    const index = drag.index
    setDrag(null); setOver(null)
    if (target) move(index, target)
    else if (!drag.started) onCardClick?.(items[index])
  }
  const onKey = (e: React.KeyboardEvent, index: number) => {
    const at = cols.indexOf(String(items[index][group_by] ?? "Other"))
    if (e.key === "ArrowRight" && at < cols.length - 1) { e.preventDefault(); move(index, cols[at + 1]) }
    if (e.key === "ArrowLeft" && at > 0) { e.preventDefault(); move(index, cols[at - 1]) }
    if (e.key === "Enter") onCardClick?.(items[index])
  }

  const card = (r: Row, ghost = false) => (
    <>
      <div className="flex items-start gap-2">
        <p className="flex-1 text-sm font-medium">{formatValue(r[titleKey])}</p>
        {!ghost && <Icon name="GripVertical" size={15} className="mt-0.5 text-muted-foreground/60" />}
      </div>
      {extra.map((k) => (
        <p key={k} className="mt-1 flex items-center justify-between gap-2 text-xs text-muted-foreground">
          <span>{humanize(k)}</span>
          {/^(status|priority|type)$/i.test(k) ? <StatusBadge value={r[k]} /> : <span className="truncate text-foreground">{formatValue(r[k])}</span>}
        </p>
      ))}
    </>
  )

  return (
    <div ref={boardRef} className={cn("flex gap-4 overflow-x-auto pb-2", drag?.started && "select-none", className)}>
      <span className="sr-only" aria-live="polite">{announce}</span>
      {cols.map((col) => {
        const cards = items.map((r, i) => [r, i] as const).filter(([r]) => String(r[group_by] ?? "Other") === col)
        return (
          <section key={col} data-kanban-col={col} aria-label={`${col}, ${cards.length} cards`}
            className={cn("flex w-72 shrink-0 flex-col rounded-xl border bg-muted/40 transition-colors", over === col && "border-primary bg-primary/5")}>
            <div className="flex items-center justify-between px-3 py-2.5">
              <span className="text-sm font-semibold">{col}</span>
              <span className="rounded-full bg-background px-2 py-0.5 text-xs text-muted-foreground">{cards.length}</span>
            </div>
            <div className="flex min-h-[80px] flex-1 flex-col gap-2 px-2 pb-2">
              {cards.map(([r, i]) => (
                <div key={r.id ?? i} data-kanban-card tabIndex={0} role="button"
                  aria-label={`${formatValue(r[titleKey])}. Use left and right arrow keys to move between columns.`}
                  onPointerDown={(e) => start(e, i, false)} onPointerMove={moveDrag} onPointerUp={end} onPointerCancel={() => { setDrag(null); setOver(null) }}
                  onKeyDown={(e) => onKey(e, i)}
                  className={cn("relative cursor-grab rounded-lg border bg-card p-3 shadow-sm outline-none hover:shadow-md focus-visible:ring-2 focus-visible:ring-ring",
                    drag?.started && drag.index === i && "opacity-40")}>
                  {card(r)}
                  {/* Touch and pen drag from the grip, so the rest of the card still scrolls the page */}
                  <span aria-hidden="true" className="absolute right-1 top-1 h-8 w-8 touch-none"
                    onPointerDown={(e) => { e.stopPropagation(); start(e, i, true) }} onPointerMove={moveDrag} onPointerUp={end}
                    onPointerCancel={() => { setDrag(null); setOver(null) }} />
                </div>
              ))}
              {cards.length === 0 && <p className="py-6 text-center text-xs text-muted-foreground">Drop cards here</p>}
            </div>
          </section>
        )
      })}
      {drag?.started && items[drag.index] && (
        <div className="pointer-events-none fixed z-[90] rotate-2 rounded-lg border bg-card p-3 shadow-2xl"
          style={{ left: drag.x - drag.dx, top: drag.y - drag.dy, width: drag.width }}>
          {card(items[drag.index], true)}
        </div>
      )}
    </div>
  )
}
