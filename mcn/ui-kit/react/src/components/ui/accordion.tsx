import * as React from "react"
import { cn } from "@/lib/utils"
import { Icon } from "./icon"

const AccCtx = React.createContext<{ open: string | null; toggle: (v: string) => void }>({ open: null, toggle: () => {} })
const ItemCtx = React.createContext<string>("")

export function Accordion({ className, children }: { type?: string; collapsible?: boolean; className?: string; children?: React.ReactNode }) {
  const [open, setOpen] = React.useState<string | null>(null)
  return (
    <AccCtx.Provider value={{ open, toggle: (v) => setOpen((o) => (o === v ? null : v)) }}>
      <div className={cn("divide-y rounded-lg border", className)}>{children}</div>
    </AccCtx.Provider>
  )
}

export function AccordionItem({ value, children }: { value: string; children?: React.ReactNode }) {
  return <ItemCtx.Provider value={value}><div>{children}</div></ItemCtx.Provider>
}

export function AccordionTrigger({ children }: { children?: React.ReactNode }) {
  const { open, toggle } = React.useContext(AccCtx)
  const value = React.useContext(ItemCtx)
  return (
    <button type="button" aria-expanded={open === value} onClick={() => toggle(value)}
      className="flex w-full items-center justify-between px-4 py-3 text-left text-sm font-medium hover:bg-muted/50">
      {children}
      <Icon name="ChevronDown" className={cn("text-muted-foreground transition-transform", open === value && "rotate-180")} />
    </button>
  )
}

export function AccordionContent({ children }: { children?: React.ReactNode }) {
  const { open } = React.useContext(AccCtx)
  const value = React.useContext(ItemCtx)
  return open === value ? <div className="px-4 pb-4 text-sm text-muted-foreground">{children}</div> : null
}
