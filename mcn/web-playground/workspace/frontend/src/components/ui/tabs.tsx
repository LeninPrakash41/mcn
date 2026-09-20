import * as React from "react"
import { cn } from "@/lib/utils"

interface TabsContextValue {
  value: string
  setValue: (v: string) => void
}
const TabsContext = React.createContext<TabsContextValue>({ value: "", setValue: () => {} })

export const Tabs: React.FC<{ defaultValue?: string; value?: string; onValueChange?: (v: string) => void; className?: string; children?: React.ReactNode }> = ({ defaultValue = "", value: controlledValue, onValueChange, className, children }) => {
  const [uncontrolledValue, setUncontrolledValue] = React.useState(defaultValue)
  const isControlled = controlledValue !== undefined
  const currentValue = isControlled ? controlledValue : uncontrolledValue
  const handleChange = (v: string) => {
    if (!isControlled) setUncontrolledValue(v)
    onValueChange?.(v)
  }
  return (
    <TabsContext.Provider value={{ value: currentValue, setValue: handleChange }}>
      <div className={cn("space-y-4", className)}>{children}</div>
    </TabsContext.Provider>
  )
}

export const TabsList: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({ className, ...props }) => (
  <div className={cn("inline-flex h-10 items-center justify-center rounded-md bg-muted p-1 text-muted-foreground", className)} {...props} />
)

export const TabsTrigger: React.FC<{ value: string; className?: string; children?: React.ReactNode }> = ({ value, className, children }) => {
  const ctx = React.useContext(TabsContext)
  const active = ctx.value === value
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center whitespace-nowrap rounded-sm px-3 py-1.5 text-sm font-medium ring-offset-background transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50",
        active && "bg-background text-foreground shadow-sm",
        className
      )}
      onClick={() => ctx.setValue(value)}
    >{children}</button>
  )
}

export const TabsContent: React.FC<{ value: string; className?: string; children?: React.ReactNode }> = ({ value, className, children }) => {
  const ctx = React.useContext(TabsContext)
  if (ctx.value !== value) return null
  return <div className={cn("mt-2 ring-offset-background focus-visible:outline-none", className)}>{children}</div>
}
