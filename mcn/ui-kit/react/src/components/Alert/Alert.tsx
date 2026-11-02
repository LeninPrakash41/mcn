import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { CheckCircle, AlertCircle, AlertTriangle, Info, X } from 'lucide-react'
import { cn } from '../../lib/utils'

const alertVariants = cva(
  'flex items-start gap-3 rounded-lg border p-4 text-[13px]',
  {
    variants: {
      variant: {
        default:  'bg-[#f4f4f5] border-[#e4e4e7] text-[#09090b]',
        info:     'bg-[rgba(59,130,246,0.06)] border-[rgba(59,130,246,0.25)] text-[#1e40af]',
        success:  'bg-[rgba(22,163,74,0.06)] border-[rgba(22,163,74,0.25)] text-[#166534]',
        warning:  'bg-[rgba(234,179,8,0.06)] border-[rgba(234,179,8,0.35)] text-[#854d0e]',
        error:    'bg-[rgba(220,38,38,0.06)] border-[rgba(220,38,38,0.25)] text-[#991b1b]',
      },
    },
    defaultVariants: { variant: 'default' },
  }
)

const iconMap = {
  default:  <Info size={16} className="text-[#71717a]" />,
  info:     <Info size={16} className="text-[#3b82f6]" />,
  success:  <CheckCircle size={16} className="text-[#16a34a]" />,
  warning:  <AlertTriangle size={16} className="text-[#ca8a04]" />,
  error:    <AlertCircle size={16} className="text-[#dc2626]" />,
}

export interface AlertProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof alertVariants> {
  /** Alert title */
  title?: string
  /** Whether to show the leading icon */
  icon?: boolean
  /** Whether to show a dismiss X button */
  dismissible?: boolean
  /** Called when dismissed */
  onDismiss?: () => void
}

/**
 * MCN Alert — inline contextual message with 5 variants.
 *
 * @example
 * <Alert variant="success" title="Deployed!" icon>Your app is live.</Alert>
 * <Alert variant="error" dismissible onDismiss={handleDismiss}>Build failed.</Alert>
 */
export function Alert({
  className,
  variant = 'default',
  title,
  icon = true,
  dismissible,
  onDismiss,
  children,
  ...props
}: AlertProps) {
  const [dismissed, setDismissed] = React.useState(false)

  if (dismissed) return null

  return (
    <div className={cn(alertVariants({ variant }), className)} role="alert" {...props}>
      {icon && (
        <span className="mt-0.5 flex-shrink-0">{iconMap[variant ?? 'default']}</span>
      )}
      <div className="flex-1 min-w-0">
        {title && <p className="font-semibold mb-0.5">{title}</p>}
        {children && <div className="leading-relaxed opacity-90">{children}</div>}
      </div>
      {dismissible && (
        <button
          onClick={() => { setDismissed(true); onDismiss?.() }}
          className="flex-shrink-0 opacity-60 hover:opacity-100 transition-opacity"
          aria-label="Dismiss"
        >
          <X size={14} />
        </button>
      )}
    </div>
  )
}
