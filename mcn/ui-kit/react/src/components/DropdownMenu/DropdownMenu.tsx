import * as React from 'react'
import * as DropdownMenuPrimitive from '@radix-ui/react-dropdown-menu'
import { Check, ChevronRight, Circle } from 'lucide-react'
import { cn } from '../../lib/utils'

const DropdownMenu = DropdownMenuPrimitive.Root

const DropdownMenuTrigger = DropdownMenuPrimitive.Trigger

export interface DropdownMenuItem {
  type?: 'item' | 'separator' | 'label'
  label?: string
  icon?: React.ReactNode
  shortcut?: string
  disabled?: boolean
  destructive?: boolean
  onClick?: () => void
  checked?: boolean
  children?: DropdownMenuItem[]
}

export interface DropdownMenuProps {
  trigger: React.ReactNode
  items: DropdownMenuItem[]
  align?: 'start' | 'center' | 'end'
  side?: 'top' | 'right' | 'bottom' | 'left'
  className?: string
}

const menuItemClass = cn(
  'relative flex cursor-default select-none items-center gap-2 rounded-md px-2 py-1.5 text-[12.5px]',
  'outline-none transition-colors',
  'focus:bg-[#f4f4f5] data-[disabled]:pointer-events-none data-[disabled]:opacity-40'
)

/**
 * MCN DropdownMenu — context menu / action menu using Radix DropdownMenu.
 *
 * @example
 * <DropdownMenu
 *   trigger={<Button variant="ghost" size="icon"><MoreHorizontal size={14} /></Button>}
 *   items={[
 *     { label: 'Edit', icon: <Pencil size={13} />, onClick: handleEdit },
 *     { type: 'separator' },
 *     { label: 'Delete', icon: <Trash size={13} />, destructive: true, onClick: handleDelete },
 *   ]}
 * />
 */
export function DropdownMenuComponent({ trigger, items, align = 'end', side = 'bottom', className }: DropdownMenuProps) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>{trigger}</DropdownMenuTrigger>
      <DropdownMenuPrimitive.Portal>
        <DropdownMenuPrimitive.Content
          align={align}
          side={side}
          sideOffset={6}
          className={cn(
            'z-50 min-w-[160px] overflow-hidden rounded-lg border border-[#e4e4e7] bg-white p-1 shadow-lg',
            'data-[state=open]:animate-in data-[state=closed]:animate-out',
            'data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0',
            'data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95',
            'data-[side=bottom]:slide-in-from-top-2 data-[side=top]:slide-in-from-bottom-2',
            className
          )}
        >
          {items.map((item, i) => {
            if (item.type === 'separator') {
              return <DropdownMenuPrimitive.Separator key={i} className="my-1 h-px bg-[#f4f4f5]" />
            }
            if (item.type === 'label') {
              return (
                <DropdownMenuPrimitive.Label key={i} className="px-2 py-1 text-[11px] font-semibold uppercase tracking-wider text-[#71717a]">
                  {item.label}
                </DropdownMenuPrimitive.Label>
              )
            }
            return (
              <DropdownMenuPrimitive.Item
                key={i}
                disabled={item.disabled}
                onClick={item.onClick}
                className={cn(
                  menuItemClass,
                  item.destructive ? 'text-[#dc2626] focus:bg-[#fef2f2]' : 'text-[#09090b]'
                )}
              >
                {item.icon && <span className="w-4 flex items-center">{item.icon}</span>}
                <span className="flex-1">{item.label}</span>
                {item.shortcut && (
                  <span className="ml-auto text-[11px] text-[#71717a]">{item.shortcut}</span>
                )}
              </DropdownMenuPrimitive.Item>
            )
          })}
        </DropdownMenuPrimitive.Content>
      </DropdownMenuPrimitive.Portal>
    </DropdownMenu>
  )
}

export { DropdownMenuComponent as DropdownMenu }
