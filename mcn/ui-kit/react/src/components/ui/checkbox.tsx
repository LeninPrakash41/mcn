import * as React from "react"
import { cn } from "@/lib/utils"

export interface CheckboxProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, "onChange" | "checked"> {
  checked?: boolean
  onCheckedChange?: (checked: boolean) => void
}

export function Checkbox({ checked, onCheckedChange, className, ...props }: CheckboxProps) {
  return (
    <input
      type="checkbox" role="checkbox" checked={!!checked}
      onChange={(e) => onCheckedChange?.(e.target.checked)}
      className={cn("h-4 w-4 rounded border-input accent-primary cursor-pointer", className)} {...props}
    />
  )
}
