import * as React from 'react'
import { ChevronRight, Home } from 'lucide-react'
import { cn } from '../../lib/utils'

export interface BreadcrumbItem {
  label: string
  href?: string
  icon?: React.ReactNode
}

export interface BreadcrumbProps {
  items: BreadcrumbItem[]
  separator?: React.ReactNode
  className?: string
}

/**
 * MCN Breadcrumb — navigation path display.
 *
 * @example
 * <Breadcrumb items={[{ label: 'Projects' }, { label: 'Healthcare', href: '/projects/healthcare' }, { label: 'main.mcn' }]} />
 */
export function Breadcrumb({ items, separator, className }: BreadcrumbProps) {
  return (
    <nav aria-label="Breadcrumb" className={className}>
      <ol className="flex flex-wrap items-center gap-1 text-[12.5px]">
        {items.map((item, i) => {
          const isLast = i === items.length - 1
          return (
            <li key={i} className="flex items-center gap-1">
              {i > 0 && (
                separator ?? <ChevronRight size={12} className="text-[#d4d4d8] flex-shrink-0" />
              )}
              {isLast ? (
                <span className="font-medium text-[#09090b] flex items-center gap-1">
                  {item.icon && <span className="flex-shrink-0">{item.icon}</span>}
                  {item.label}
                </span>
              ) : item.href ? (
                <a
                  href={item.href}
                  className="flex items-center gap-1 text-[#71717a] hover:text-[#09090b] transition-colors"
                >
                  {item.icon && <span className="flex-shrink-0">{item.icon}</span>}
                  {item.label}
                </a>
              ) : (
                <span className="flex items-center gap-1 text-[#71717a]">
                  {item.icon && <span className="flex-shrink-0">{item.icon}</span>}
                  {item.label}
                </span>
              )}
            </li>
          )
        })}
      </ol>
    </nav>
  )
}
