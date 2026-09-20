import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '../../lib/utils'

const cardVariants = cva('rounded-xl bg-white transition-shadow duration-[0.12s]', {
  variants: {
    variant: {
      default:  'border border-[#e4e4e7]',
      bordered: 'border-2 border-[#d4d4d8]',
      elevated: 'border border-[#e4e4e7] shadow-md hover:shadow-lg',
      ghost:    'bg-[#f4f4f5]',
    },
  },
  defaultVariants: { variant: 'default' },
})

export interface CardProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof cardVariants> {
  /** Card header slot — renders above content with border */
  header?: React.ReactNode
  /** Title shorthand */
  title?: string
  /** Description shorthand */
  description?: string
  /** Footer slot — renders below content with border-top */
  footer?: React.ReactNode
  /** Padding preset */
  padding?: 'none' | 'sm' | 'md' | 'lg'
}

const paddingMap = { none: 'p-0', sm: 'p-4', md: 'p-5', lg: 'p-7' }

/**
 * MCN Card — versatile container with header, body, and footer slots.
 *
 * @example
 * <Card title="API Usage" description="Last 30 days">
 *   <StatBlock />
 * </Card>
 */
export function Card({
  className,
  variant,
  header,
  title,
  description,
  footer,
  padding = 'md',
  children,
  ...props
}: CardProps) {
  const hasTitleRow = title || description
  const hasHeader = header || hasTitleRow

  return (
    <div className={cn(cardVariants({ variant }), className)} {...props}>
      {hasHeader && (
        <div className={cn('border-b border-[#e4e4e7]', paddingMap[padding])}>
          {header ?? (
            <>
              {title && <h3 className="text-[15px] font-semibold text-[#09090b]">{title}</h3>}
              {description && <p className="mt-0.5 text-[13px] text-[#71717a]">{description}</p>}
            </>
          )}
        </div>
      )}

      <div className={cn(paddingMap[padding])}>{children}</div>

      {footer && (
        <div className={cn('border-t border-[#e4e4e7]', paddingMap[padding])}>
          {footer}
        </div>
      )}
    </div>
  )
}
