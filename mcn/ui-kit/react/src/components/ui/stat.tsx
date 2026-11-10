import * as React from "react"
import { Card, CardContent } from "./card"
import { cn, formatValue } from "@/lib/utils"

type Tone = "primary" | "green" | "red" | "blue" | "amber" | "purple"

const TONES: Record<Tone, string> = {
  primary: "text-primary bg-primary/10",
  green: "text-green-600 bg-green-100 dark:bg-green-500/15",
  red: "text-red-600 bg-red-100 dark:bg-red-500/15",
  blue: "text-blue-600 bg-blue-100 dark:bg-blue-500/15",
  amber: "text-amber-600 bg-amber-100 dark:bg-amber-500/15",
  purple: "text-purple-600 bg-purple-100 dark:bg-purple-500/15",
}

export interface StatProps {
  label?: React.ReactNode
  value?: unknown
  unit?: React.ReactNode
  /** Percent change; positive shows green ↑, negative red ↓ */
  change?: number | string | null
  trend?: number | string | null
  trendLabel?: React.ReactNode
  icon?: React.ComponentType<{ className?: string }>
  tone?: Tone | string
  className?: string
}

/** A KPI card: label, formatted value with unit, optional icon and percent change. */
export function Stat({
  label,
  value,
  unit,
  change,
  trend,
  trendLabel = "vs last month",
  icon: Icon,
  tone = "primary",
  className,
}: StatProps) {
  const delta = change ?? trend
  const deltaNum = delta === null || delta === undefined || delta === "" ? null : Number(delta)
  return (
    <Card className={className}>
      <CardContent className="p-5">
        <div className="flex items-center justify-between gap-3">
          <div className="min-w-0">
            <p className="text-sm font-medium text-muted-foreground">{label}</p>
            <p className="mt-1 text-2xl font-bold tabular-nums">
              {formatValue(value)}
              {unit ? <span className="ml-1 text-sm font-normal text-muted-foreground">{unit}</span> : null}
            </p>
            {deltaNum !== null && !Number.isNaN(deltaNum) && (
              <p className="mt-1 text-xs text-muted-foreground">
                <span className={deltaNum >= 0 ? "text-green-600" : "text-red-600"}>
                  {deltaNum >= 0 ? "↑" : "↓"} {Math.abs(deltaNum)}%
                </span>{" "}
                {trendLabel}
              </p>
            )}
          </div>
          {Icon && (
            <div className={cn("shrink-0 rounded-lg p-2", TONES[tone as Tone] ?? TONES.primary)}>
              <Icon className="h-5 w-5" />
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  )
}

export default Stat
