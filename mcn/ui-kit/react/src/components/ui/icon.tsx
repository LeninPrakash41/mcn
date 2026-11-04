import * as React from "react"
import { ICONS } from "./icons-data"
import { cn } from "@/lib/utils"

const LOOKUP: Record<string, string> = {}
for (const name of Object.keys(ICONS)) LOOKUP[name.toLowerCase().replace(/[-_ ]/g, "")] = name

/** Resolve "users", "Users", "check-circle" or "check_circle" to an icon name. */
export function iconName(name: string | undefined): string {
  if (!name) return "Circle"
  return ICONS[name] ? name : LOOKUP[String(name).toLowerCase().replace(/[-_ ]/g, "")] || "Circle"
}

export interface IconProps extends React.SVGAttributes<SVGSVGElement> {
  /** A lucide icon name, e.g. "Users", "TrendingUp", "bell" */
  name: string
  size?: number
}

/** An outline icon from MCN's built-in set. Unknown names render a circle. */
export function Icon({ name, size = 16, className, strokeWidth = 2, ...props }: IconProps) {
  const nodes = ICONS[iconName(name)]
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg" width={size} height={size} viewBox="0 0 24 24"
      fill="none" stroke="currentColor" strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round"
      aria-hidden="true" className={cn("shrink-0", className)} {...props}
    >
      {nodes.map(([tag, attrs], i) => React.createElement(tag, { key: i, ...attrs }))}
    </svg>
  )
}

export type IconComponent = (props: Omit<IconProps, "name">) => JSX.Element

/** Named icon components on demand: `const { Users, Bell } = icons`. Any name works. */
export const icons: Record<string, IconComponent> = new Proxy({} as Record<string, IconComponent>, {
  get: (cache, key: string) => (cache[key] ??= (props) => <Icon name={key} {...props} />),
})
