import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '../../lib/utils'
import { Loader2 } from 'lucide-react'

const spinnerVariants = cva('animate-spin', {
  variants: {
    size: {
      sm:  'h-3 w-3',
      md:  'h-4 w-4',
      lg:  'h-6 w-6',
      xl:  'h-8 w-8',
    },
    color: {
      default: 'text-[#3b82f6]',
      muted:   'text-[#a1a1aa]',
      white:   'text-white',
      current: 'text-current',
    },
  },
  defaultVariants: { size: 'md', color: 'default' },
})

export interface SpinnerProps
  extends React.HTMLAttributes<SVGSVGElement>,
    VariantProps<typeof spinnerVariants> {
  /** Accessible label */
  label?: string
}

/**
 * MCN Spinner — animated loading indicator.
 *
 * @example
 * <Spinner size="lg" />
 * <Spinner color="white" />
 */
export function Spinner({ className, size, color, label = 'Loading…', ...props }: SpinnerProps) {
  return (
    <Loader2
      className={cn(spinnerVariants({ size, color }), className)}
      aria-label={label}
      role="status"
      {...props}
    />
  )
}
