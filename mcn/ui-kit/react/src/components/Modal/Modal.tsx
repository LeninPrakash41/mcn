import * as React from 'react'
import * as DialogPrimitive from '@radix-ui/react-dialog'
import { X } from 'lucide-react'
import { cn } from '../../lib/utils'

const sizeMap = {
  sm:   'max-w-sm',
  md:   'max-w-lg',
  lg:   'max-w-2xl',
  xl:   'max-w-4xl',
  full: 'max-w-[95vw]',
}

export interface ModalProps {
  /** Controls open state */
  open?: boolean
  /** Called when modal wants to close */
  onOpenChange?: (open: boolean) => void
  /** Modal title */
  title?: string
  /** Modal description */
  description?: string
  /** Footer content (buttons, actions) */
  footer?: React.ReactNode
  /** Main content */
  children?: React.ReactNode
  /** Max width preset */
  size?: 'sm' | 'md' | 'lg' | 'xl' | 'full'
  /** Whether clicking overlay closes the modal */
  closeOnOverlayClick?: boolean
  /** Show X close button */
  showCloseButton?: boolean
  /** Custom className for the content panel */
  className?: string
}

/**
 * MCN Modal — accessible dialog using Radix Dialog.
 *
 * @example
 * <Modal open={isOpen} onOpenChange={setIsOpen} title="Delete project?" size="sm"
 *   footer={<><Button variant="destructive">Delete</Button><Button onClick={() => setIsOpen(false)}>Cancel</Button></>}
 * >
 *   <p>This action cannot be undone.</p>
 * </Modal>
 */
export function Modal({
  open,
  onOpenChange,
  title,
  description,
  footer,
  children,
  size = 'md',
  closeOnOverlayClick = true,
  showCloseButton = true,
  className,
}: ModalProps) {
  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        {/* Overlay */}
        <DialogPrimitive.Overlay
          className={cn(
            'fixed inset-0 z-50 bg-black/40 backdrop-blur-sm',
            'data-[state=open]:animate-in data-[state=closed]:animate-out',
            'data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0'
          )}
          onClick={closeOnOverlayClick ? undefined : (e) => e.stopPropagation()}
        />
        {/* Content */}
        <DialogPrimitive.Content
          className={cn(
            'fixed left-1/2 top-1/2 z-50 w-full -translate-x-1/2 -translate-y-1/2',
            'bg-white rounded-xl border border-[#e4e4e7] shadow-xl',
            'p-6 focus:outline-none',
            'data-[state=open]:animate-in data-[state=closed]:animate-out',
            'data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0',
            'data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95',
            'data-[state=closed]:slide-out-to-left-1/2 data-[state=open]:slide-in-from-left-1/2',
            'data-[state=closed]:slide-out-to-top-[48%] data-[state=open]:slide-in-from-top-[48%]',
            sizeMap[size],
            className
          )}
        >
          {/* Header */}
          {(title || showCloseButton) && (
            <div className="flex items-start justify-between mb-4">
              <div>
                {title && (
                  <DialogPrimitive.Title className="text-[16px] font-semibold text-[#09090b]">
                    {title}
                  </DialogPrimitive.Title>
                )}
                {description && (
                  <DialogPrimitive.Description className="mt-1 text-[13px] text-[#71717a]">
                    {description}
                  </DialogPrimitive.Description>
                )}
              </div>
              {showCloseButton && (
                <DialogPrimitive.Close
                  className={cn(
                    'ml-4 flex-shrink-0 rounded-md p-1 text-[#71717a]',
                    'hover:bg-[#f4f4f5] hover:text-[#09090b]',
                    'focus:outline-none focus:ring-2 focus:ring-[#3b82f6]',
                    'transition-colors duration-[0.12s]'
                  )}
                >
                  <X size={16} />
                </DialogPrimitive.Close>
              )}
            </div>
          )}

          {/* Body */}
          <div className="text-[13px] text-[#09090b]">{children}</div>

          {/* Footer */}
          {footer && (
            <div className="mt-6 flex justify-end items-center gap-2 border-t border-[#e4e4e7] pt-4">
              {footer}
            </div>
          )}
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  )
}

/** Re-export Radix trigger for convenience */
export const ModalTrigger = DialogPrimitive.Trigger
