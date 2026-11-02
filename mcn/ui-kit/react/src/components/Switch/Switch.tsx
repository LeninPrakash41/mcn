import * as React from 'react'
import * as SwitchPrimitive from '@radix-ui/react-switch'
import { cn } from '../../lib/utils'

export interface SwitchProps extends React.ComponentPropsWithoutRef<typeof SwitchPrimitive.Root> {
  /** Label rendered next to the switch */
  label?: string
  /** Helper text */
  description?: string
}

/**
 * MCN Switch — toggle control using Radix Switch.
 *
 * @example
 * <Switch label="Dark mode" onCheckedChange={(v) => toggleTheme(v)} />
 */
export const Switch = React.forwardRef<
  React.ElementRef<typeof SwitchPrimitive.Root>,
  SwitchProps
>(({ className, label, description, id, ...props }, ref) => {
  const switchId = id ?? React.useId()
  return (
    <div className="flex items-center gap-2.5">
      <SwitchPrimitive.Root
        ref={ref}
        id={switchId}
        className={cn(
          'peer inline-flex h-5 w-9 shrink-0 cursor-pointer items-center rounded-full',
          'border-2 border-transparent transition-colors duration-[0.12s]',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#3b82f6] focus-visible:ring-offset-2',
          'disabled:cursor-not-allowed disabled:opacity-40',
          'bg-[#d4d4d8] data-[state=checked]:bg-[#3b82f6]',
          className
        )}
        {...props}
      >
        <SwitchPrimitive.Thumb
          className={cn(
            'pointer-events-none block h-4 w-4 rounded-full bg-white shadow-sm',
            'ring-0 transition-transform duration-[0.12s]',
            'translate-x-0 data-[state=checked]:translate-x-4'
          )}
        />
      </SwitchPrimitive.Root>
      {(label || description) && (
        <div className="flex flex-col gap-0.5">
          {label && (
            <label htmlFor={switchId} className="text-[13px] font-medium text-[#09090b] cursor-pointer">
              {label}
            </label>
          )}
          {description && (
            <p className="text-[12px] text-[#71717a]">{description}</p>
          )}
        </div>
      )}
    </div>
  )
})
Switch.displayName = SwitchPrimitive.Root.displayName
