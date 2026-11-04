import * as React from "react"
import { cn, compactNumber, formatValue, humanize, PALETTE } from "@/lib/utils"

/* Responsive SVG charts with tooltips, legends and multiple series. No dependencies.
   Every chart takes `data` (a list of objects) and the keys to plot. */

type Row = Record<string, any>

/** Width of an element, kept current. A callback ref, so it starts measuring
    whenever the element appears (charts render a placeholder until data arrives). */
function useWidth<T extends HTMLElement>(): [(el: T | null) => void, number] {
  const [el, setEl] = React.useState<T | null>(null)
  const [width, setWidth] = React.useState(0)
  React.useLayoutEffect(() => {
    if (!el) return
    setWidth(el.clientWidth)
    if (typeof ResizeObserver === "undefined") return
    const ro = new ResizeObserver(([entry]) => setWidth(entry.contentRect.width))
    ro.observe(el)
    return () => ro.disconnect()
  }, [el])
  return [setEl, width]
}

function toKeys(y: string | string[] | undefined, data: Row[], x: string): string[] {
  if (Array.isArray(y)) return y
  if (y) return [y]
  const first = data[0] || {}
  return Object.keys(first).filter((k) => k !== x && typeof first[k] === "number").slice(0, 3)
}

/** A round step for four gridlines: 2900 → 1000 (ticks 0, 1k, 2k, 3k, 4k). */
function niceStep(v: number): number {
  if (v <= 0) return 1
  const mag = Math.pow(10, Math.floor(Math.log10(v)))
  const n = v / mag
  return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 2.5 ? 2.5 : n <= 5 ? 5 : 10) * mag
}

function Empty({ height, label = "No data yet" }: { height: number; label?: string }) {
  return (
    <div className="flex items-center justify-center rounded-lg border border-dashed text-sm text-muted-foreground" style={{ height }}>
      {label}
    </div>
  )
}

function Legend({ keys, colors }: { keys: string[]; colors: string[] }) {
  if (keys.length < 2) return null
  return (
    <div className="mt-3 flex flex-wrap justify-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
      {keys.map((k, i) => (
        <span key={k} className="inline-flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-sm" style={{ background: colors[i % colors.length] }} />{humanize(k)}
        </span>
      ))}
    </div>
  )
}

function TooltipBox({ x, y, title, rows }: { x: number; y: number; title: string; rows: { label: string; value: any; color: string }[] }) {
  return (
    <div className="pointer-events-none absolute z-10 min-w-[8rem] -translate-x-1/2 -translate-y-full rounded-lg border bg-popover px-3 py-2 text-xs shadow-lg"
      style={{ left: x, top: y - 8 }}>
      <div className="mb-1 font-medium text-foreground">{title}</div>
      {rows.map((r) => (
        <div key={r.label} className="flex items-center justify-between gap-4 text-muted-foreground">
          <span className="inline-flex items-center gap-1.5"><span className="h-2 w-2 rounded-full" style={{ background: r.color }} />{r.label}</span>
          <span className="font-medium tabular-nums text-foreground">{formatValue(r.value)}</span>
        </div>
      ))}
    </div>
  )
}

export interface CartesianChartProps {
  data?: Row[]
  /** Key for the category axis (aliases: x_key, xKey, dataKey) */
  x?: string
  /** Key or keys to plot (aliases: y_key, yKey) */
  y?: string | string[]
  x_key?: string
  y_key?: string | string[]
  height?: number
  colors?: string[]
  stacked?: boolean
  className?: string
  /** Shown when there's no data */
  empty?: string
}

type Kind = "bar" | "line" | "area"

function CartesianChart({ kind, ...p }: CartesianChartProps & { kind: Kind }) {
  const data = Array.isArray(p.data) ? p.data : []
  const x = p.x || p.x_key || "label"
  const keys = toKeys(p.y || p.y_key, data, x)
  const height = Number(p.height) || 300
  const colors = p.colors || PALETTE
  const [ref, width] = useWidth<HTMLDivElement>()
  const [hover, setHover] = React.useState<number | null>(null)

  if (!data.length || !keys.length) return <Empty height={height} label={p.empty} />

  const pad = { top: 12, right: 12, bottom: 28, left: 44 }
  const w = width - pad.left - pad.right
  const h = height - pad.top - pad.bottom
  const val = (r: Row, k: string) => Number(r[k]) || 0
  const totals = data.map((r) => keys.reduce((s, k) => s + val(r, k), 0))
  const rawMax = kind === "bar" && p.stacked ? Math.max(...totals) : Math.max(...data.flatMap((r) => keys.map((k) => val(r, k))))
  const max = niceStep(rawMax / 4) * 4
  const yAt = (v: number) => pad.top + h - (v / max) * h
  const band = w / data.length
  const xAt = (i: number) => pad.left + band * i + band / 2
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((t) => t * max)
  const labelEvery = Math.ceil(data.length / Math.max(1, Math.floor(w / 70)))

  return (
    <div ref={ref} className={cn("relative w-full min-w-0 select-none", p.className)} style={{ minHeight: height }}>
      {width > 0 && <>
      <svg width={width} height={height} role="img" aria-label={`${kind} chart of ${keys.map(humanize).join(", ")}`}
        onMouseLeave={() => setHover(null)}>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={pad.left} x2={width - pad.right} y1={yAt(t)} y2={yAt(t)} className="stroke-border" strokeDasharray={t ? "3 3" : undefined} />
            <text x={pad.left - 8} y={yAt(t)} dy="0.32em" textAnchor="end" className="fill-muted-foreground text-[11px]">{compactNumber(t)}</text>
          </g>
        ))}
        {data.map((r, i) => i % labelEvery === 0 && (
          <text key={i} x={xAt(i)} y={height - 8} textAnchor="middle" className="fill-muted-foreground text-[11px]">
            {String(r[x] ?? "").slice(0, 12)}
          </text>
        ))}

        {kind === "bar" && data.map((r, i) => {
          let stackTop = 0
          const groupW = Math.min(band * 0.7, 56)
          const barW = p.stacked ? groupW : groupW / keys.length
          return keys.map((k, j) => {
            const v = val(r, k)
            const bx = p.stacked ? xAt(i) - groupW / 2 : xAt(i) - groupW / 2 + j * barW
            const by = p.stacked ? yAt(stackTop + v) : yAt(v)
            const bh = p.stacked ? yAt(stackTop) - yAt(stackTop + v) : yAt(0) - yAt(v)
            stackTop += v
            return <rect key={k} x={bx} y={by} width={Math.max(1, barW - (p.stacked ? 0 : 2))} height={Math.max(0, bh)}
              rx={p.stacked ? 0 : 3} fill={colors[j % colors.length]} opacity={hover === null || hover === i ? 1 : 0.45} />
          })
        })}

        {kind !== "bar" && keys.map((k, j) => {
          const pts = data.map((r, i) => [xAt(i), yAt(val(r, k))] as const)
          const line = pts.map(([px, py], i) => `${i ? "L" : "M"}${px},${py}`).join(" ")
          const color = colors[j % colors.length]
          return (
            <g key={k}>
              {kind === "area" && (
                <path d={`${line} L${pts[pts.length - 1][0]},${yAt(0)} L${pts[0][0]},${yAt(0)} Z`} fill={color} opacity={0.15} />
              )}
              <path d={line} fill="none" stroke={color} strokeWidth={2.25} strokeLinejoin="round" strokeLinecap="round" />
              {pts.map(([px, py], i) => (hover === i || data.length <= 12) && (
                <circle key={i} cx={px} cy={py} r={hover === i ? 4.5 : 3} fill="hsl(var(--background))" stroke={color} strokeWidth={2} />
              ))}
            </g>
          )
        })}

        {hover !== null && kind !== "bar" && (
          <line x1={xAt(hover)} x2={xAt(hover)} y1={pad.top} y2={pad.top + h} className="stroke-muted-foreground" strokeDasharray="3 3" />
        )}
        {data.map((_, i) => (
          <rect key={i} x={pad.left + band * i} y={pad.top} width={band} height={h} fill="transparent" onMouseEnter={() => setHover(i)} />
        ))}
      </svg>
      {hover !== null && (
        <TooltipBox
          x={Math.min(Math.max(xAt(hover), 70), width - 70)}
          y={yAt(kind === "bar" && p.stacked ? totals[hover] : Math.max(...keys.map((k) => val(data[hover], k))))}
          title={String(data[hover][x] ?? "")}
          rows={keys.map((k, j) => ({ label: humanize(k), value: data[hover][k], color: colors[j % colors.length] }))}
        />
      )}
      <Legend keys={keys} colors={colors} />
      </>}
    </div>
  )
}

export function BarChart(props: CartesianChartProps) { return <CartesianChart kind="bar" {...props} /> }
export function LineChart(props: CartesianChartProps) { return <CartesianChart kind="line" {...props} /> }
export function AreaChart(props: CartesianChartProps) { return <CartesianChart kind="area" {...props} /> }

export interface PieChartProps {
  data?: Row[]
  /** Label key (alias: name_key) */
  name?: string
  /** Value key (alias: value_key) */
  value?: string
  name_key?: string
  value_key?: string
  x_key?: string
  y_key?: string
  height?: number
  donut?: boolean
  colors?: string[]
  className?: string
  empty?: string
}

/** Pie or donut chart. With `donut`, the total is shown in the middle. */
export function PieChart(p: PieChartProps) {
  const data = Array.isArray(p.data) ? p.data : []
  const nameKey = p.name || p.name_key || p.x_key || "name"
  const valueKey = p.value || p.value_key || p.y_key || "value"
  const height = Number(p.height) || 260
  const colors = p.colors || PALETTE
  const [hover, setHover] = React.useState<number | null>(null)
  const [ref, width] = useWidth<HTMLDivElement>()
  const total = data.reduce((s, r) => s + (Number(r[valueKey]) || 0), 0)
  if (!data.length || !total) return <Empty height={height} label={p.empty} />

  // Fits the container: the legend wraps below the chart on narrow screens
  const r = Math.max(40, Math.min(height / 2 - 8, 120, (width || 280) / 2 - 8)), cx = r + 8, cy = height / 2
  const inner = p.donut ? r * 0.62 : 0
  let angle = -Math.PI / 2
  const arcs = data.map((row, i) => {
    const v = Number(row[valueKey]) || 0
    const a0 = angle, a1 = angle + (v / total) * Math.PI * 2
    angle = a1
    const big = a1 - a0 > Math.PI ? 1 : 0
    const pt = (rad: number, a: number) => `${cx + rad * Math.cos(a)},${cy + rad * Math.sin(a)}`
    const d = inner
      ? `M${pt(r, a0)} A${r},${r} 0 ${big} 1 ${pt(r, a1)} L${pt(inner, a1)} A${inner},${inner} 0 ${big} 0 ${pt(inner, a0)} Z`
      : `M${cx},${cy} L${pt(r, a0)} A${r},${r} 0 ${big} 1 ${pt(r, a1)} Z`
    return { d, i, v, label: String(row[nameKey] ?? `Item ${i + 1}`) }
  })

  return (
    <div ref={ref} className={cn("flex flex-wrap items-center justify-center gap-6", p.className)}>
      <svg width={cx * 2} height={height} role="img" aria-label="Pie chart" onMouseLeave={() => setHover(null)}>
        {arcs.map((a) => (
          <path key={a.i} d={a.d} fill={colors[a.i % colors.length]} stroke="hsl(var(--background))" strokeWidth={2}
            opacity={hover === null || hover === a.i ? 1 : 0.5} onMouseEnter={() => setHover(a.i)} />
        ))}
        {p.donut && (
          <>
            <text x={cx} y={cy - 4} textAnchor="middle" className="fill-foreground text-xl font-semibold">
              {compactNumber(hover === null ? total : arcs[hover].v)}
            </text>
            <text x={cx} y={cy + 16} textAnchor="middle" className="fill-muted-foreground text-[11px]">
              {hover === null ? "Total" : arcs[hover].label}
            </text>
          </>
        )}
      </svg>
      <ul className="min-w-[10rem] flex-1 space-y-1.5 text-sm">
        {arcs.map((a) => (
          <li key={a.i} className={cn("flex items-center justify-between gap-3 rounded px-1", hover === a.i && "bg-muted")}
            onMouseEnter={() => setHover(a.i)} onMouseLeave={() => setHover(null)}>
            <span className="inline-flex min-w-0 items-center gap-2">
              <span className="h-2.5 w-2.5 shrink-0 rounded-sm" style={{ background: colors[a.i % colors.length] }} />
              <span className="truncate">{a.label}</span>
            </span>
            <span className="tabular-nums text-muted-foreground">{Math.round((a.v / total) * 100)}%</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

export function DonutChart(props: PieChartProps) { return <PieChart donut {...props} /> }

/** A tiny trend line for stat cards and table cells. */
export function Sparkline({ data, y, y_key, height = 32, width = 96, color = PALETTE[0] }: {
  data?: (number | Row)[]; y?: string; y_key?: string; height?: number; width?: number; color?: string
}) {
  const key = y || y_key || "value"
  const vals = (Array.isArray(data) ? data : []).map((d) => (typeof d === "number" ? d : Number((d as Row)[key]) || 0))
  if (vals.length < 2) return null
  const min = Math.min(...vals), max = Math.max(...vals), span = max - min || 1
  const pts = vals.map((v, i) => `${(i / (vals.length - 1)) * width},${height - 2 - ((v - min) / span) * (height - 4)}`)
  return (
    <svg width={width} height={height} aria-hidden="true">
      <polyline points={pts.join(" ")} fill="none" stroke={color} strokeWidth={1.75} strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  )
}
