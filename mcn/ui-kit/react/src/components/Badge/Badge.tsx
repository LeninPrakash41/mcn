import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '../../lib/utils'

const badgeVariants = cva(
  'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium transition-colors select-none',
  {
    variants: {
      variant: {
        default:  'bg-[#f4f4f5] text-[#09090b] border border-[#e4e4e7]',
        primary:  'bg-[rgba(59,130,246,0.1)] text-[#3b82f6] border border-[rgba(59,130,246,0.25)]',
        success:  'bg-[rgba(22,163,74,0.1)] text-[#16a34a] border border-[rgba(22,163,74,0.25)]',
        warning:  'bg-[rgba(234,179,8,0.1)] text-[#a16207] border border-[rgba(234,179,8,0.25)]',
        error:    'bg-[rgba(220,38,38,0.1)] text-[#dc2626] border border-[rgba(220,38,38,0.25)]',
        outline:  'bg-transparent text-[#09090b] border border-[#d4d4d8]',
        solid:    'bg-[#09090b] text-white border border-[#09090b]',
      },
    },
    defaultVariants: {
      variant: 'default',
    },
  }
)

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {
  /** Optional dot indicator */
  dot?: boolean
}

/**
 * MCN Badge — inline status / label chip.
 *
 * @example
 * <Badge variant="success">Running</Badge>
 * <Badge variant="error" dot>Failed</Badge>
 */
export function Badge({ className, variant, dot, children, ...props }: BadgeProps) {
  return (
    <span className={cn(badgeVariants({ variant }), className)} {...props}>
      {dot && (
        <span
          className={cn(
            'inline-block h-1.5 w-1.5 rounded-full',
            variant === 'success' && 'bg-[#16a34a]',
            variant === 'error' && 'bg-[#dc2626]',
            variant === 'warning' && 'bg-[#ca8a04]',
            variant === 'primary' && 'bg-[#3b82f6]',
            (!variant || variant === 'default') && 'bg-[#71717a]'
          )}
        />
      )}
      {children}
    </span>
  )
}

export { badgeVariants }
