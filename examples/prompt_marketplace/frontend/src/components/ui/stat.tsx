import * as React from "react"
import { Card, CardContent } from "./card"
import { cn } from "@/lib/utils"

export interface StatProps {
  label?: string
  value?: string | number
  change?: number | string
  trend?: number | string
  unit?: string
  className?: string
}

export const Stat: React.FC<StatProps> = ({ label = "Overview", value = "$0", change, trend, unit = "", className }) => {
  const valTrend = change !== undefined ? change : trend
  return (
    <Card className={cn("my-2", className)}>
      <CardContent className="p-4">
        <div className="text-xs font-semibold text-primary uppercase tracking-wider">{label}</div>
        <div className="text-2xl font-bold mt-1 flex items-baseline">
          {value} {unit && <span className="text-sm font-normal text-muted-foreground ml-1">{unit}</span>}
          {valTrend !== undefined && (
            <span className="text-xs text-green-500 font-semibold ml-2">↑ +{valTrend}%</span>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
export default Stat
