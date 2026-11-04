import * as React from "react"
import { cn } from "@/lib/utils"

const MenuCtx = React.createContext<{ open: boolean; setOpen: (o: boolean) => void }>({ open: false, setOpen: () => {} })

export function DropdownMenu({ children }: { children?: React.ReactNode }) {
  const [open, setOpen] = React.useState(false)
  const ref = React.useRef<HTMLDivElement>(null)
  React.useEffect(() => {
    if (!open) return
    const close = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false) }
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false) }
    document.addEventListener("mousedown", close); document.addEventListener("keydown", esc)
    return () => { document.removeEventListener("mousedown", close); document.removeEventListener("keydown", esc) }
  }, [open])
  return <MenuCtx.Provider value={{ open, setOpen }}><div ref={ref} className="relative inline-block">{children}</div></MenuCtx.Provider>
}

export function DropdownMenuTrigger({ children }: { children?: React.ReactNode; asChild?: boolean }) {
  const { open, setOpen } = React.useContext(MenuCtx)
  return <span onClick={() => setOpen(!open)} aria-haspopup="menu" aria-expanded={open}>{children}</span>
}

export function DropdownMenuContent({ className, align = "end", children }: { className?: string; align?: "start" | "end"; children?: React.ReactNode }) {
  const { open } = React.useContext(MenuCtx)
  if (!open) return null
  return (
    <div role="menu" className={cn("absolute z-50 mt-1 min-w-[10rem] rounded-md border bg-popover p-1 text-popover-foreground shadow-lg",
      align === "end" ? "right-0" : "left-0", className)}>
      {children}
    </div>
  )
}

export function DropdownMenuItem({ className, onClick, children }: { className?: string; onClick?: () => void; children?: React.ReactNode }) {
  const { setOpen } = React.useContext(MenuCtx)
  return (
    <button type="button" role="menuitem" onClick={() => { onClick?.(); setOpen(false) }}
      className={cn("flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-left text-sm hover:bg-accent", className)}>
      {children}
    </button>
  )
}

export function DropdownMenuSeparator() { return <div className="-mx-1 my-1 h-px bg-border" /> }
