import * as React from "react"
import { cn } from "@/lib/utils"
import { Icon } from "./icon"

/** A friendly placeholder for empty lists and first-run screens. */
export function EmptyState({ icon = "Inbox", title, description, action, className }: {
  icon?: string; title: string; description?: string; action?: React.ReactNode; className?: string
}) {
  return (
    <div className={cn("flex flex-col items-center justify-center gap-2 rounded-xl border border-dashed p-10 text-center", className)}>
      <span className="grid h-12 w-12 place-items-center rounded-full bg-muted"><Icon name={icon} size={22} className="text-muted-foreground" /></span>
      <p className="mt-1 font-medium">{title}</p>
      {description && <p className="max-w-sm text-sm text-muted-foreground">{description}</p>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  )
}
