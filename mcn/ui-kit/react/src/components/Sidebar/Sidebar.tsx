import * as React from 'react'
import { cn } from '../../lib/utils'

export interface SidebarItem {
  id: string
  label: string
  icon?: React.ReactNode
  href?: string
  active?: boolean
  badge?: string | number
  children?: SidebarItem[]
  onClick?: () => void
}

export interface SidebarProps {
  /** Navigation items */
  items: SidebarItem[]
  /** Logo/brand slot */
  logo?: React.ReactNode
  /** Bottom footer slot */
  footer?: React.ReactNode
  /** Collapsed state */
  collapsed?: boolean
  /** className */
  className?: string
  /** Width when expanded */
  width?: string
}

function SidebarNavItem({ item, depth = 0, collapsed }: { item: SidebarItem; depth?: number; collapsed?: boolean }) {
  const [open, setOpen] = React.useState(false)
  const hasChildren = item.children && item.children.length > 0

  const Wrapper = item.href ? 'a' : 'button'
  const wrapperProps = item.href
    ? { href: item.href }
    : { type: 'button' as const, onClick: () => { item.onClick?.(); if (hasChildren) setOpen((v) => !v) } }

  return (
    <li>
      <Wrapper
        {...(wrapperProps as Record<string, unknown>)}
        className={cn(
          'flex items-center gap-2 w-full rounded-md text-[13px] font-medium',
          'transition-all duration-[0.12s] select-none cursor-pointer',
          depth === 0 ? 'px-2.5 py-2' : 'px-2 py-1.5',
          item.active
            ? 'bg-[rgba(59,130,246,0.1)] text-[#3b82f6]'
            : 'text-[#71717a] hover:bg-[#f4f4f5] hover:text-[#09090b]',
          collapsed && 'justify-center'
        )}
        aria-current={item.active ? 'page' : undefined}
      >
        {item.icon && (
          <span className="flex-shrink-0 w-4 flex items-center justify-center">
            {item.icon}
          </span>
        )}
        {!collapsed && (
          <>
            <span className="flex-1 truncate">{item.label}</span>
            {item.badge && (
              <span className="text-[10px] font-bold px-1.5 py-0.5 rounded-full bg-[#3b82f6] text-white">
                {item.badge}
              </span>
            )}
          </>
        )}
      </Wrapper>
      {hasChildren && open && !collapsed && (
        <ul className="ml-4 mt-0.5 space-y-0.5 border-l border-[#e4e4e7] pl-3">
          {item.children!.map((child) => (
            <SidebarNavItem key={child.id} item={child} depth={depth + 1} />
          ))}
        </ul>
      )}
    </li>
  )
}

/**
 * MCN Sidebar — collapsible navigation sidebar.
 *
 * @example
 * <Sidebar
 *   logo={<img src="/logo.svg" className="h-7" />}
 *   items={[{ id: 'home', label: 'Home', icon: <Home size={15} />, active: true }]}
 * />
 */
export function Sidebar({ items, logo, footer, collapsed, className, width = '240px' }: SidebarProps) {
  return (
    <aside
      className={cn(
        'flex flex-col bg-[#f4f4f5] border-r border-[#d4d4d8] overflow-hidden flex-shrink-0',
        'transition-all duration-200',
        className
      )}
      style={{ width: collapsed ? '56px' : width }}
    >
      {/* Logo */}
      {logo && (
        <div className={cn('flex items-center px-3 h-14 border-b border-[#d4d4d8]', collapsed && 'justify-center')}>
          {logo}
        </div>
      )}

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto py-3 px-2">
        <ul className="space-y-0.5">
          {items.map((item) => (
            <SidebarNavItem key={item.id} item={item} collapsed={collapsed} />
          ))}
        </ul>
      </nav>

      {/* Footer */}
      {footer && (
        <div className={cn('border-t border-[#d4d4d8] p-3', collapsed && 'flex justify-center')}>
          {footer}
        </div>
      )}
    </aside>
  )
}
