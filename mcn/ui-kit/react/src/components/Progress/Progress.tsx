import * as React from 'react'
import * as ProgressPrimitive from '@radix-ui/react-progress'
import { cn } from '../../lib/utils'

export interface ProgressProps extends React.ComponentPropsWithoutRef<typeof ProgressPrimitive.Root> {
  /** Value 0–100 */
  value?: number
  /** Label displayed above */
  label?: string
  /** Show percentage text */
  showValue?: boolean
  /** Color variant */
  variant?: 'default' | 'success' | 'warning' | 'error'
  /** Bar height */
  size?: 'sm' | 'md' | 'lg'
}

const colorMap = {
  default: 'bg-[#3b82f6]',
  success: 'bg-[#16a34a]',
  warning: 'bg-[#ca8a04]',
  error:   'bg-[#dc2626]',
}

const heightMap = {
  sm: 'h-1',
  md: 'h-2',
  lg: 'h-3',
}

/**
 * MCN Progress — linear progress bar.
 *
 * @example
 * <Progress value={67} label="Build progress" showValue />
 * <Progress value={100} variant="success" />
 */
export const Progress = React.forwardRef<
  React.ElementRef<typeof ProgressPrimitive.Root>,
  ProgressProps
>(({ className, value = 0, label, showValue, variant = 'default', size = 'md', ...props }, ref) => (
  <div className="w-full">
    {(label || showValue) && (
      <div className="flex justify-between items-center mb-1.5">
        {label && <span className="text-[12px] font-medium text-[#09090b]">{label}</span>}
        {showValue && <span className="text-[12px] text-[#71717a]">{Math.round(value)}%</span>}
      </div>
    )}
    <ProgressPrimitive.Root
      ref={ref}
      value={value}
      className={cn(
        'relative overflow-hidden rounded-full bg-[#e4e4e7] w-full',
        heightMap[size],
        className
      )}
      {...props}
    >
      <ProgressPrimitive.Indicator
        className={cn('h-full w-full flex-1 transition-all duration-500 ease-out', colorMap[variant])}
        style={{ transform: `translateX(-${100 - (value ?? 0)}%)` }}
      />
    </ProgressPrimitive.Root>
  </div>
))
Progress.displayName = ProgressPrimitive.Root.displayName
