import * as React from "react"
import { cn } from "@/lib/utils"

/** Where a screen's data load is: still loading, failed with a message, or done. */
export interface LoadState {
  loading: boolean
  error: string | null
}

export interface LoadStatusProps {
  loading: boolean
  error: string | null
  onRetry?: () => void
  className?: string
}

/** A screen's loading bar, or its load error with a Retry button. Renders nothing once loaded. */
export function LoadStatus({ loading, error, onRetry, className }: LoadStatusProps) {
  if (error) {
    return (
      <div
        role="alert"
        className={cn(
          "flex flex-wrap items-center justify-between gap-3 rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm",
          className,
        )}
      >
        <span className="text-destructive">{error}</span>
        {onRetry && (
          <button
            type="button"
            onClick={onRetry}
            className="rounded-md border border-destructive/30 px-3 py-1 font-medium text-destructive hover:bg-destructive/10 focus:outline-none focus-visible:ring-2 focus-visible:ring-destructive/40"
          >
            Retry
          </button>
        )}
      </div>
    )
  }
  if (!loading) return null
  return (
    <div role="status" aria-live="polite" className={cn("h-1 w-full overflow-hidden rounded-full bg-muted", className)}>
      <div className="h-full w-1/3 animate-pulse rounded-full bg-primary/60" />
      <span className="sr-only">Loading…</span>
    </div>
  )
}

export default LoadStatus
