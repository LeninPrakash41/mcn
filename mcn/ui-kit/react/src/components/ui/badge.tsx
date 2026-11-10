import * as React from "react"
import { cn } from "@/lib/utils"

const VARIANTS: Record<string, string> = {
  default: "border-transparent bg-primary text-primary-foreground hover:bg-primary/80",
  secondary: "border-transparent bg-secondary text-secondary-foreground hover:bg-secondary/80",
  destructive: "border-transparent bg-destructive text-destructive-foreground hover:bg-destructive/80",
  outline: "text-foreground",
}

export const Badge: React.FC<React.HTMLAttributes<HTMLDivElement> & { variant?: string }> = ({
  className,
  variant = "default",
  ...props
}) => (
  <div
    className={cn(
      "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
      VARIANTS[variant] ?? VARIANTS.default,
      className,
    )}
    {...props}
  />
)
