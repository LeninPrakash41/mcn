import * as React from 'react'
import { cn } from '../../lib/utils'
import { Label } from '../Label/Label'
import { AlertCircle } from 'lucide-react'

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  /** Label displayed above the input */
  label?: string
  /** Helper text displayed below */
  hint?: string
  /** Error message — replaces hint, colors border red */
  error?: string
  /** Left slot — icon or text prefix */
  prefix?: React.ReactNode
  /** Right slot — icon or text suffix */
  suffix?: React.ReactNode
  /** Container className */
  wrapperClassName?: string
}

/**
 * MCN Input — a labelled, accessible text input with error, hint, and prefix/suffix slots.
 *
 * @example
 * <Input label="API Key" placeholder="sk-..." suffix={<Eye size={14} />} />
 * <Input label="Port" error="Port must be between 1–65535" type="number" />
 */
export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  (
    { className, label, hint, error, prefix, suffix, wrapperClassName, id, ...props },
    ref
  ) => {
    const inputId = id ?? React.useId()
    const hasError = Boolean(error)

    return (
      <div className={cn('flex flex-col gap-1.5', wrapperClassName)}>
        {label && (
          <Label htmlFor={inputId}>
            {label}
          </Label>
        )}
        <div className="relative flex items-center">
          {prefix && (
            <div className="absolute left-2.5 flex items-center text-[#71717a] pointer-events-none">
              {prefix}
            </div>
          )}
          <input
            ref={ref}
            id={inputId}
            className={cn(
              'w-full h-9 rounded-md border bg-white px-3 py-2',
              'text-[13px] text-[#09090b] font-sans',
              'border-[#d4d4d8] placeholder:text-[#a1a1aa]',
              'transition-all duration-[0.12s]',
              'focus:outline-none focus:border-[#3b82f6] focus:ring-2 focus:ring-[rgba(59,130,246,0.2)]',
              'disabled:opacity-40 disabled:cursor-not-allowed disabled:bg-[#f4f4f5]',
              hasError && 'border-[#dc2626] focus:border-[#dc2626] focus:ring-[rgba(220,38,38,0.2)]',
              prefix && 'pl-8',
              suffix && 'pr-8',
              className
            )}
            aria-invalid={hasError}
            aria-describedby={error ? `${inputId}-error` : hint ? `${inputId}-hint` : undefined}
            {...props}
          />
          {suffix && (
            <div className="absolute right-2.5 flex items-center text-[#71717a]">
              {suffix}
            </div>
          )}
        </div>
        {(error || hint) && (
          <p
            id={error ? `${inputId}-error` : `${inputId}-hint`}
            className={cn(
              'flex items-center gap-1 text-[12px]',
              hasError ? 'text-[#dc2626]' : 'text-[#71717a]'
            )}
          >
            {hasError && <AlertCircle size={11} />}
            {error ?? hint}
          </p>
        )}
      </div>
    )
  }
)
Input.displayName = 'Input'
