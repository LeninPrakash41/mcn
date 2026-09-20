import * as React from 'react'
import { cn } from '../../lib/utils'
import { TrendingUp, TrendingDown, Minus } from 'lucide-react'

export interface StatProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Metric label */
  label: string
  /** Main value to display */
  value: string | number
  /** Optional unit suffix */
  unit?: string
  /** Change percentage (positive = up, negative = down) */
  change?: number
  /** Change label text */
  changeLabel?: string
  /** Optional icon */
  icon?: React.ReactNode
  /** Loading skeleton */
  isLoading?: boolean
}

/**
 * MCN Stat — metric display card for dashboards.
 *
 * @example
 * <Stat label="API Calls" value="12,847" change={+14.2} changeLabel="vs last week" icon={<Zap size={16} />} />
 */
export function Stat({ label, value, unit, change, changeLabel, icon, isLoading, className, ...props }: StatProps) {
  const isUp = change != null && change > 0
  const isDown = change != null && change < 0

  if (isLoading) {
    return (
      <div className={cn('p-5 rounded-xl border border-[#e4e4e7] bg-white animate-pulse', className)} {...props}>
        <div className="h-3 w-20 bg-[#e4e4e7] rounded mb-3" />
        <div className="h-8 w-28 bg-[#e4e4e7] rounded mb-2" />
        <div className="h-3 w-16 bg-[#e4e4e7] rounded" />
      </div>
    )
  }

  return (
    <div className={cn('p-5 rounded-xl border border-[#e4e4e7] bg-white', className)} {...props}>
      <div className="flex items-center justify-between mb-2">
        <p className="text-[13px] font-medium text-[#71717a]">{label}</p>
        {icon && <span className="text-[#71717a]">{icon}</span>}
      </div>
      <p className="text-[28px] font-bold text-[#09090b] leading-none mb-1.5">
        {typeof value === 'number' ? value.toLocaleString() : value}
        {unit && <span className="text-[16px] font-medium text-[#71717a] ml-1">{unit}</span>}
      </p>
      {change != null && (
        <div className="flex items-center gap-1 text-[12px]">
          {isUp ? <TrendingUp size={12} className="text-[#16a34a]" /> :
           isDown ? <TrendingDown size={12} className="text-[#dc2626]" /> :
           <Minus size={12} className="text-[#71717a]" />}
          <span className={cn(isUp ? 'text-[#16a34a]' : isDown ? 'text-[#dc2626]' : 'text-[#71717a]')}>
            {change > 0 ? '+' : ''}{change}%
          </span>
          {changeLabel && <span className="text-[#71717a]">{changeLabel}</span>}
        </div>
      )}
    </div>
  )
}
