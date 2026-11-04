import * as React from "react"
import { cn } from "@/lib/utils"

/* CSS-only tooltip: the content shows on hover or keyboard focus of the trigger. */

export function TooltipProvider({ children }: { children?: React.ReactNode }) { return <>{children}</> }

export function Tooltip({ children }: { children?: React.ReactNode }) {
  return <span className="group relative inline-flex">{children}</span>
}

export function TooltipTrigger({ children }: { children?: React.ReactNode; asChild?: boolean }) {
  return <span tabIndex={0} className="inline-flex outline-none">{children}</span>
}

export function TooltipContent({ className, children }: { className?: string; children?: React.ReactNode }) {
  return (
    <span role="tooltip" className={cn(
      "pointer-events-none absolute bottom-full left-1/2 z-50 mb-2 -translate-x-1/2 whitespace-nowrap rounded-md",
      "bg-foreground px-2.5 py-1.5 text-xs text-background opacity-0 shadow-md transition-opacity",
      "group-hover:opacity-100 group-focus-within:opacity-100", className)}>
      {children}
    </span>
  )
}
