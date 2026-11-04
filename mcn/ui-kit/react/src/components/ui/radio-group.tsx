import * as React from "react"
import { cn } from "@/lib/utils"

const RadioCtx = React.createContext<{ value?: string; onValueChange?: (v: string) => void; name: string }>({ name: "radio" })

export function RadioGroup({ value, onValueChange, className, children }: {
  value?: string; onValueChange?: (value: string) => void; className?: string; children?: React.ReactNode
}) {
  const name = React.useId()
  return <RadioCtx.Provider value={{ value, onValueChange, name }}><div role="radiogroup" className={cn("grid gap-2", className)}>{children}</div></RadioCtx.Provider>
}

export function RadioGroupItem({ value, id, className }: { value: string; id?: string; className?: string }) {
  const ctx = React.useContext(RadioCtx)
  return (
    <input type="radio" id={id} name={ctx.name} value={value} checked={ctx.value === value}
      onChange={() => ctx.onValueChange?.(value)} className={cn("h-4 w-4 accent-primary cursor-pointer", className)} />
  )
}
