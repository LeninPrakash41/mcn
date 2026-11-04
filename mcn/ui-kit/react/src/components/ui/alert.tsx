import * as React from "react"
import { cn } from "@/lib/utils"

export function Alert({ className, variant, ...props }: React.HTMLAttributes<HTMLDivElement> & { variant?: "default" | "destructive" }) {
  return <div role="alert" className={cn("relative w-full rounded-lg border p-4", variant === "destructive" && "border-red-500/50 text-red-600", className)} {...props} />
}

export function AlertDescription({ className, ...props }: React.HTMLAttributes<HTMLParagraphElement>) {
  return <div className={cn("text-sm", className)} {...props} />
}
