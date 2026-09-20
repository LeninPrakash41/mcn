import * as React from 'react'
import { Slot } from '@radix-ui/react-slot'
import { cva, type VariantProps } from 'class-variance-authority'
import { Loader2 } from 'lucide-react'
import { cn } from '../../lib/utils'

const buttonVariants = cva(
  [
    'inline-flex items-center justify-center gap-2 rounded-md font-medium',
    'transition-all duration-[0.12s] select-none whitespace-nowrap',
    'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#3b82f6] focus-visible:ring-offset-2',
    'disabled:pointer-events-none disabled:opacity-40',
  ],
  {
    variants: {
      variant: {
        default: 'bg-[#f4f4f5] text-[#09090b] border border-[#d4d4d8] hover:bg-[#e4e4e7] hover:border-[#c1c9d8]',
        primary: 'bg-[#3b82f6] text-white border border-[#3b82f6] hover:bg-[#2563eb] hover:border-[#2563eb]',
        ghost: 'bg-transparent text-[#09090b] border border-transparent hover:bg-[#f4f4f5]',
        destructive: 'bg-[#dc2626] text-white border border-[#dc2626] hover:bg-[#b91c1c]',
        outline: 'bg-transparent text-[#09090b] border border-[#d4d4d8] hover:bg-[#f4f4f5]',
        link: 'bg-transparent text-[#3b82f6] border-none underline-offset-4 hover:underline p-0 h-auto',
        gradient: 'bg-gradient-to-br from-[#7c3aed] to-[#a855f7] text-white border-none hover:opacity-90 shadow-sm',
      },
      size: {
        sm: 'h-7 px-2.5 text-xs',
        md: 'h-9 px-3 text-[13px]',
        lg: 'h-11 px-5 text-sm',
        icon: 'h-9 w-9 p-0',
        'icon-sm': 'h-7 w-7 p-0',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'md',
    },
  }
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  /** Render as a child component (e.g. anchor tag) using Radix Slot */
  asChild?: boolean
  /** Show loading spinner and disable the button */
  isLoading?: boolean
  /** Icon to show before the label */
  leftIcon?: React.ReactNode
  /** Icon to show after the label */
  rightIcon?: React.ReactNode
}

/**
 * MCN Button — the primary interactive element.
 *
 * @example
 * <Button variant="primary" size="md">Deploy</Button>
 * <Button variant="ghost" isLoading>Generating…</Button>
 * <Button variant="destructive" leftIcon={<Trash2 size={14} />}>Delete</Button>
 */
export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      className,
      variant,
      size,
      asChild = false,
      isLoading = false,
      leftIcon,
      rightIcon,
      children,
      disabled,
      ...props
    },
    ref
  ) => {
    const Comp = asChild ? Slot : 'button'

    return (
      <Comp
        ref={ref}
        className={cn(buttonVariants({ variant, size }), className)}
        disabled={disabled || isLoading}
        {...props}
      >
        {isLoading ? (
          <Loader2 size={14} className="animate-spin" />
        ) : (
          leftIcon
        )}
        {children}
        {!isLoading && rightIcon}
      </Comp>
    )
  }
)

Button.displayName = 'Button'

export { buttonVariants }
