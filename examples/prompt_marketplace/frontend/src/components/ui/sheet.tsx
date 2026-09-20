import * as React from "react"
import { cn } from "@/lib/utils"

export interface SheetProps {
  open?: boolean
  onOpenChange?: (open: boolean) => void
  children?: React.ReactNode
}

export const Sheet: React.FC<SheetProps> = ({ open, onOpenChange, children }) => {
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 bg-black/80 flex justify-end" onClick={() => onOpenChange?.(false)}>
      <div className="relative w-full max-w-md bg-background p-6 shadow-lg h-full overflow-y-auto" onClick={(e) => e.stopPropagation()}>
        {children}
      </div>
    </div>
  )
}

export const SheetContent: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({ className, children, ...props }) => (
  <div className={cn("flex flex-col h-full", className)} {...props}>{children}</div>
)

export const SheetHeader: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({ className, children, ...props }) => (
  <div className={cn("flex flex-col space-y-2 text-center sm:text-left mb-4", className)} {...props}>{children}</div>
)

export const SheetTitle: React.FC<React.HTMLAttributes<HTMLHeadingElement>> = ({ className, children, ...props }) => (
  <h2 className={cn("text-lg font-semibold text-foreground", className)} {...props}>{children}</h2>
)

export const SheetDescription: React.FC<React.HTMLAttributes<HTMLParagraphElement>> = ({ className, children, ...props }) => (
  <p className={cn("text-sm text-muted-foreground", className)} {...props}>{children}</p>
)

export const SheetFooter: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({ className, children, ...props }) => (
  <div className={cn("flex flex-col-reverse sm:flex-row sm:justify-end sm:space-x-2 mt-auto pt-4 border-t", className)} {...props}>{children}</div>
)

export const SheetTrigger: React.FC<{ children?: React.ReactNode; asChild?: boolean }> = ({ children }) => <>{children}</>
