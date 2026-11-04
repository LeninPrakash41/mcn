import * as React from "react"
import { cn } from "@/lib/utils"
import { Icon } from "./icon"

export type Crumb = string | { label: string; href?: string; onClick?: () => void }

/** Home / Deals / Acme Ltd — the last item is the current page. */
export function Breadcrumb({ items = [], className }: { items?: Crumb[]; className?: string }) {
  const list = items.map((c) => (typeof c === "string" ? { label: c } : c))
  return (
    <nav aria-label="Breadcrumb" className={cn("flex min-w-0 items-center text-sm", className)}>
      <ol className="flex min-w-0 items-center gap-1.5">
        {list.map((c, i) => {
          const last = i === list.length - 1
          return (
            <li key={i} className="flex min-w-0 items-center gap-1.5">
              {i > 0 && <Icon name="ChevronRight" size={14} className="text-muted-foreground/60" />}
              {last ? (
                <span aria-current="page" className="truncate font-medium text-foreground">{c.label}</span>
              ) : c.href || c.onClick ? (
                <a href={c.href || "#"} onClick={(e) => { if (c.onClick) { e.preventDefault(); c.onClick() } }}
                  className="truncate text-muted-foreground hover:text-foreground">{c.label}</a>
              ) : (
                <span className="truncate text-muted-foreground">{c.label}</span>
              )}
            </li>
          )
        })}
      </ol>
    </nav>
  )
}
