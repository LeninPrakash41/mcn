import * as React from "react"
import { cn } from "@/lib/utils"

export interface DialogProps {
  open?: boolean
  onOpenChange?: (open: boolean) => void
  children?: React.ReactNode
}

export const Dialog: React.FC<DialogProps> = ({ open, onOpenChange, children }) => {
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4" onClick={() => onOpenChange?.(false)}>
      <div className="relative w-full max-w-lg bg-background p-6 shadow-lg rounded-lg" onClick={(e) => e.stopPropagation()}>
        {children}
      </div>
    </div>
  )
}

export const DialogContent: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({ className, children, ...props }) => (
  <div className={cn("space-y-4", className)} {...props}>{children}</div>
)

export const DialogHeader: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({ className, children, ...props }) => (
  <div className={cn("flex flex-col space-y-1.5 text-center sm:text-left", className)} {...props}>{children}</div>
)

export const DialogTitle: React.FC<React.HTMLAttributes<HTMLHeadingElement>> = ({ className, children, ...props }) => (
  <h2 className={cn("text-lg font-semibold leading-none tracking-tight", className)} {...props}>{children}</h2>
)

export const DialogDescription: React.FC<React.HTMLAttributes<HTMLParagraphElement>> = ({ className, children, ...props }) => (
  <p className={cn("text-sm text-muted-foreground", className)} {...props}>{children}</p>
)

export const DialogFooter: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({ className, children, ...props }) => (
  <div className={cn("flex flex-col-reverse sm:flex-row sm:justify-end sm:space-x-2 pt-4", className)} {...props}>{children}</div>
)

export const DialogTrigger: React.FC<{ children?: React.ReactNode; asChild?: boolean }> = ({ children }) => <>{children}</>
