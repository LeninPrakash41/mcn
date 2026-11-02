import * as React from 'react'
import * as LabelPrimitive from '@radix-ui/react-label'
import { cn } from '../../lib/utils'

export interface LabelProps extends React.ComponentPropsWithoutRef<typeof LabelPrimitive.Root> {}

/**
 * MCN Label — accessible form label using Radix Label primitive.
 *
 * @example
 * <Label htmlFor="email">Email address</Label>
 */
export const Label = React.forwardRef<
  React.ElementRef<typeof LabelPrimitive.Root>,
  LabelProps
>(({ className, ...props }, ref) => (
  <LabelPrimitive.Root
    ref={ref}
    className={cn(
      'text-[13px] font-medium text-[#09090b] leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-50',
      className
    )}
    {...props}
  />
))
Label.displayName = LabelPrimitive.Root.displayName
