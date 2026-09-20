import * as React from 'react'
import * as CheckboxPrimitive from '@radix-ui/react-checkbox'
import { Check } from 'lucide-react'
import { cn } from '../../lib/utils'

export interface CheckboxProps extends React.ComponentPropsWithoutRef<typeof CheckboxPrimitive.Root> {
  /** Label rendered next to the checkbox */
  label?: string
  /** Helper or error text */
  description?: string
}

/**
 * MCN Checkbox — accessible checkbox with optional label.
 *
 * @example
 * <Checkbox label="Enable telemetry" defaultChecked />
 * <Checkbox label="Accept terms" onCheckedChange={(v) => setAccepted(!!v)} />
 */
export const Checkbox = React.forwardRef<
  React.ElementRef<typeof CheckboxPrimitive.Root>,
  CheckboxProps
>(({ className, label, description, id, ...props }, ref) => {
  const checkId = id ?? React.useId()
  return (
    <div className="flex items-start gap-2">
      <CheckboxPrimitive.Root
        ref={ref}
        id={checkId}
        className={cn(
          'mt-0.5 h-4 w-4 shrink-0 rounded border border-[#d4d4d8] bg-white',
          'transition-colors duration-[0.12s]',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#3b82f6] focus-visible:ring-offset-2',
          'disabled:cursor-not-allowed disabled:opacity-40',
          'data-[state=checked]:bg-[#3b82f6] data-[state=checked]:border-[#3b82f6]',
          className
        )}
        {...props}
      >
        <CheckboxPrimitive.Indicator className="flex items-center justify-center">
          <Check size={10} className="text-white stroke-[3]" />
        </CheckboxPrimitive.Indicator>
      </CheckboxPrimitive.Root>
      {(label || description) && (
        <div className="flex flex-col gap-0.5">
          {label && (
            <label htmlFor={checkId} className="text-[13px] font-medium text-[#09090b] cursor-pointer leading-tight">
              {label}
            </label>
          )}
          {description && (
            <p className="text-[12px] text-[#71717a] leading-tight">{description}</p>
          )}
        </div>
      )}
    </div>
  )
})
Checkbox.displayName = CheckboxPrimitive.Root.displayName
