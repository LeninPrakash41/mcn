import * as React from "react"
import { Icon } from "./icon"
import { initials } from "./landing"
import { cn, formatValue } from "@/lib/utils"

/* Elements for consumer-style app screens: avatars, list rows, progress rings
   and sideways-scrolling carousels. Each has a native equivalent on phones. */

const TONE: Record<string, string> = {
  primary: "hsl(var(--primary))", green: "#10b981", emerald: "#10b981", red: "#ef4444", rose: "#f43f5e",
  blue: "#3b82f6", sky: "#0ea5e9", amber: "#f59e0b", orange: "#f97316", purple: "#8b5cf6", violet: "#8b5cf6",
  pink: "#ec4899", teal: "#14b8a6", cyan: "#06b6d4", indigo: "#6366f1", slate: "#64748b",
}
export const toneColor = (c?: string) => (c ? TONE[String(c).toLowerCase()] || c : TONE.primary)

export interface PersonAvatarProps {
  name?: React.ReactNode
  src?: string
  size?: number
  color?: string
  /** Show a green dot */
  online?: boolean
  className?: string
}

/** A round photo, or initials on a tinted circle when there's no photo. */
export function PersonAvatar({ name, src, size = 40, color, online, className }: PersonAvatarProps) {
  const px = Number(size) || 40
  const tint = toneColor(color)
  return (
    <span className={cn("relative inline-flex shrink-0", className)} style={{ width: px, height: px }}>
      {src ? (
        <img src={src} alt={typeof name === "string" ? name : ""} className="h-full w-full rounded-full object-cover ring-2 ring-background" />
      ) : (
        <span className="grid h-full w-full place-items-center rounded-full font-semibold ring-2 ring-background"
          style={{ background: `color-mix(in srgb, ${tint} 16%, transparent)`, color: tint, fontSize: Math.max(11, px * 0.38) }}>
          {initials(name)}
        </span>
      )}
      {online ? <span className="absolute bottom-0 right-0 h-3 w-3 rounded-full bg-emerald-500 ring-2 ring-background" /> : null}
    </span>
  )
}

export interface ListItemProps {
  title?: React.ReactNode
  subtitle?: React.ReactNode
  icon?: string
  color?: string
  avatar?: string
  /** Show initials for this name as the leading avatar */
  person?: React.ReactNode
  trailing?: React.ReactNode
  badge?: React.ReactNode
  onClick?: () => unknown
  link?: string
}

/** A row: an icon or avatar, a title and subtitle, and a value or badge at the end. */
export function ListItem({ title, subtitle, icon, color, avatar, person, trailing, badge, onClick, link }: ListItemProps) {
  const tap = onClick || link ? () => (onClick ? onClick() : link && (window.location.href = link)) : undefined
  const tint = toneColor(color)
  const Tag = tap ? "button" : "div"
  return (
    <Tag type={tap ? "button" : undefined} onClick={tap}
      className={cn("flex w-full items-center gap-3.5 rounded-xl border border-border/60 bg-card px-4 py-3 text-left",
        tap && "transition-colors hover:border-primary/40 hover:bg-accent/40")}>
      {avatar || person ? <PersonAvatar src={avatar} name={person || title} size={42} color={color} />
        : icon ? (
          <span className="grid h-[42px] w-[42px] shrink-0 place-items-center rounded-xl"
            style={{ background: `color-mix(in srgb, ${tint} 14%, transparent)`, color: tint }}>
            <Icon name={icon} size={20} />
          </span>
        ) : null}
      <span className="min-w-0 flex-1">
        <span className="block truncate font-semibold">{title}</span>
        {subtitle ? <span className="block truncate text-sm text-muted-foreground">{subtitle}</span> : null}
      </span>
      {badge ? <span className="rounded-full bg-primary/10 px-2.5 py-0.5 text-xs font-semibold text-primary">{badge}</span> : null}
      {trailing !== undefined && trailing !== null && trailing !== "" ? <span className="shrink-0 text-sm font-semibold tabular-nums">{formatValue(trailing)}</span> : null}
      {tap ? <Icon name="ChevronRight" size={18} className="text-muted-foreground" /> : null}
    </Tag>
  )
}

export interface ProgressRingProps {
  value?: number | string
  label?: React.ReactNode
  /** Text in the middle; the percentage when omitted */
  center?: React.ReactNode
  color?: string
  size?: number
  thickness?: number
}

/** A circular progress ring (0–100), like activity rings. */
export function ProgressRing({ value = 0, label, center, color, size = 96, thickness }: ProgressRingProps) {
  const px = Number(size) || 96
  const stroke = Number(thickness) || Math.max(6, px / 10)
  const r = (px - stroke) / 2
  const circ = 2 * Math.PI * r
  const pct = Math.max(0, Math.min(100, Number(value) || 0))
  const tint = toneColor(color)
  return (
    <div className="inline-flex flex-col items-center gap-2">
      <div className="relative" style={{ width: px, height: px }}>
        <svg width={px} height={px} className="-rotate-90">
          <circle cx={px / 2} cy={px / 2} r={r} fill="none" strokeWidth={stroke} style={{ stroke: `color-mix(in srgb, ${tint} 16%, transparent)` }} />
          <circle cx={px / 2} cy={px / 2} r={r} fill="none" strokeWidth={stroke} strokeLinecap="round"
            strokeDasharray={circ} strokeDashoffset={circ * (1 - pct / 100)} style={{ stroke: tint, transition: "stroke-dashoffset .6s ease" }} />
        </svg>
        <span className="absolute inset-0 grid place-items-center font-bold tabular-nums" style={{ fontSize: Math.max(12, px * 0.22) }}>
          {center ?? `${Math.round(pct)}%`}
        </span>
      </div>
      {label ? <span className="text-sm font-medium text-muted-foreground">{label}</span> : null}
    </div>
  )
}

/** Children in a row that scrolls sideways and snaps, one card at a time on phones. */
export function Carousel({ title, children, width = 260 }: { title?: React.ReactNode; children?: React.ReactNode; width?: number }) {
  return (
    <div className="min-w-0">
      {title ? <h3 className="mb-3 text-lg font-semibold tracking-tight">{title}</h3> : null}
      <div className="-mx-1 flex snap-x snap-mandatory gap-4 overflow-x-auto px-1 pb-3 [scrollbar-width:thin]">
        {React.Children.map(children, (child) => (
          <div className="shrink-0 snap-start" style={{ width: Number(width) || 260 }}>{child}</div>
        ))}
      </div>
    </div>
  )
}
