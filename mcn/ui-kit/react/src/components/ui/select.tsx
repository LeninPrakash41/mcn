import * as React from "react"
import { cn } from "@/lib/utils"

// Native <select> behind the shadcn Select API: Select > SelectTrigger > SelectValue, SelectContent > SelectItem
type Ctx = { value?: string; onValueChange?: (v: string) => void; placeholder?: string; setPlaceholder: (p?: string) => void }
const SelectCtx = React.createContext<Ctx>({ setPlaceholder: () => {} })

export function Select({ value, defaultValue, onValueChange, children }: {
  value?: any; defaultValue?: any; onValueChange?: (v: string) => void; children?: React.ReactNode
}) {
  const [placeholder, setPlaceholder] = React.useState<string | undefined>()
  const [inner, setInner] = React.useState<string>(defaultValue != null ? String(defaultValue) : "")
  const current = value != null ? String(value) : inner
  const change = (v: string) => { setInner(v); onValueChange?.(v) }
  return <SelectCtx.Provider value={{ value: current, onValueChange: change, placeholder, setPlaceholder }}>{children}</SelectCtx.Provider>
}

export function SelectTrigger({ children }: { children?: React.ReactNode; className?: string }) {
  return <>{children}</>
}

export function SelectValue({ placeholder }: { placeholder?: string }) {
  const { setPlaceholder } = React.useContext(SelectCtx)
  React.useEffect(() => { setPlaceholder(placeholder) }, [placeholder])
  return null
}

export function SelectContent({ children, className }: { children?: React.ReactNode; className?: string }) {
  const { value, onValueChange, placeholder } = React.useContext(SelectCtx)
  return (
    <select
      className={cn("flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring", className)}
      value={value ?? ""}
      onChange={(e) => onValueChange?.(e.target.value)}
    >
      {placeholder !== undefined && <option value="" disabled>{placeholder}</option>}
      {children}
    </select>
  )
}

export function SelectItem({ value, children }: { value: any; children?: React.ReactNode }) {
  return <option value={String(value)}>{children}</option>
}
