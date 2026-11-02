import * as React from 'react'
import * as TooltipPrimitive from '@radix-ui/react-tooltip'
import { cn } from '../../lib/utils'

export interface TooltipProps {
  /** The element that triggers the tooltip */
  children: React.ReactNode
  /** Tooltip content */
  content: React.ReactNode
  /** Side to display */
  side?: 'top' | 'right' | 'bottom' | 'left'
  /** Delay in ms before tooltip shows */
  delayDuration?: number
  /** className for content */
  className?: string
}

/**
 * MCN Tooltip — accessible tooltip using Radix Tooltip.
 *
 * @example
 * <Tooltip content="Copy to clipboard">
 *   <Button size="icon"><Copy size={14} /></Button>
 * </Tooltip>
 */
export function Tooltip({ children, content, side = 'top', delayDuration = 300, className }: TooltipProps) {
  return (
    <TooltipPrimitive.Provider delayDuration={delayDuration}>
      <TooltipPrimitive.Root>
        <TooltipPrimitive.Trigger asChild>{children}</TooltipPrimitive.Trigger>
        <TooltipPrimitive.Portal>
          <TooltipPrimitive.Content
            side={side}
            sideOffset={6}
            className={cn(
              'z-50 rounded-md px-2.5 py-1.5 text-[12px] font-medium',
              'bg-[#09090b] text-white shadow-md',
              'animate-in fade-in-0 zoom-in-95',
              'data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95',
              'data-[side=bottom]:slide-in-from-top-2 data-[side=left]:slide-in-from-right-2',
              'data-[side=right]:slide-in-from-left-2 data-[side=top]:slide-in-from-bottom-2',
              className
            )}
          >
            {content}
            <TooltipPrimitive.Arrow className="fill-[#09090b]" />
          </TooltipPrimitive.Content>
        </TooltipPrimitive.Portal>
      </TooltipPrimitive.Root>
    </TooltipPrimitive.Provider>
  )
}
