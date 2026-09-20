import * as React from 'react'
import { cn } from '../../lib/utils'
import { Label } from '../Label/Label'
import { AlertCircle } from 'lucide-react'

export interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  /** Label displayed above */
  label?: string
  /** Helper text */
  hint?: string
  /** Error message */
  error?: string
  /** Container className */
  wrapperClassName?: string
}

/**
 * MCN Textarea — multi-line text input with label and error support.
 *
 * @example
 * <Textarea label="Description" rows={4} placeholder="Describe your use case..." />
 */
export const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, label, hint, error, wrapperClassName, id, ...props }, ref) => {
    const textareaId = id ?? React.useId()
    const hasError = Boolean(error)

    return (
      <div className={cn('flex flex-col gap-1.5', wrapperClassName)}>
        {label && <Label htmlFor={textareaId}>{label}</Label>}
        <textarea
          ref={ref}
          id={textareaId}
          className={cn(
            'w-full min-h-[80px] rounded-md border bg-white px-3 py-2',
            'text-[13px] text-[#09090b] font-sans resize-y',
            'border-[#d4d4d8] placeholder:text-[#a1a1aa]',
            'transition-all duration-[0.12s]',
            'focus:outline-none focus:border-[#3b82f6] focus:ring-2 focus:ring-[rgba(59,130,246,0.2)]',
            'disabled:opacity-40 disabled:cursor-not-allowed disabled:bg-[#f4f4f5]',
            hasError && 'border-[#dc2626] focus:border-[#dc2626] focus:ring-[rgba(220,38,38,0.2)]',
            className
          )}
          aria-invalid={hasError}
          {...props}
        />
        {(error || hint) && (
          <p className={cn('flex items-center gap-1 text-[12px]', hasError ? 'text-[#dc2626]' : 'text-[#71717a]')}>
            {hasError && <AlertCircle size={11} />}
            {error ?? hint}
          </p>
        )}
      </div>
    )
  }
)
Textarea.displayName = 'Textarea'
