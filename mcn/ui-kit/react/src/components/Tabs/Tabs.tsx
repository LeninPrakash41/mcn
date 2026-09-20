import * as React from 'react'
import * as TabsPrimitive from '@radix-ui/react-tabs'
import { cn } from '../../lib/utils'

export interface TabItem {
  value: string
  label: string
  content: React.ReactNode
  /** Optional icon before label */
  icon?: React.ReactNode
  /** Disable this tab */
  disabled?: boolean
  /** Optional badge/count next to label */
  badge?: string | number
}

export interface TabsProps extends Omit<React.ComponentPropsWithoutRef<typeof TabsPrimitive.Root>, 'children'> {
  /** Tab items */
  tabs: TabItem[]
  /** Visual style */
  variant?: 'default' | 'pills' | 'underline'
  /** className for the tabs container */
  className?: string
  /** className for tab list */
  listClassName?: string
}

/**
 * MCN Tabs — tabbed interface using Radix Tabs.
 *
 * @example
 * <Tabs
 *   tabs={[
 *     { value: 'output', label: 'Output', content: <OutputLog /> },
 *     { value: 'preview', label: 'Preview', content: <PreviewPane /> },
 *   ]}
 * />
 */
export function Tabs({ tabs, variant = 'default', className, listClassName, ...props }: TabsProps) {
  return (
    <TabsPrimitive.Root className={cn('flex flex-col', className)} {...props}>
      <TabsPrimitive.List
        className={cn(
          'flex items-center flex-shrink-0',
          variant === 'default' && 'border-b border-[#d4d4d8] bg-[#f4f4f5] h-9',
          variant === 'pills' && 'gap-1 p-1 bg-[#f4f4f5] rounded-lg w-fit',
          variant === 'underline' && 'border-b border-[#d4d4d8] gap-0',
          listClassName
        )}
      >
        {tabs.map((tab) => (
          <TabsPrimitive.Trigger
            key={tab.value}
            value={tab.value}
            disabled={tab.disabled}
            className={cn(
              'relative flex items-center gap-1.5 text-[12.5px] font-medium transition-all duration-[0.12s]',
              'disabled:pointer-events-none disabled:opacity-40',
              variant === 'default' && [
                'h-full px-4 text-[#71717a] border-r border-[#d4d4d8]',
                'hover:text-[#09090b]',
                'data-[state=active]:bg-white data-[state=active]:text-[#09090b]',
                'data-[state=active]:after:absolute data-[state=active]:after:bottom-0',
                'data-[state=active]:after:left-0 data-[state=active]:after:right-0',
                'data-[state=active]:after:h-0.5 data-[state=active]:after:bg-[#3b82f6]',
                'data-[state=active]:after:content-[""]',
              ],
              variant === 'pills' && [
                'rounded-md px-3 py-1.5 text-[#71717a]',
                'hover:text-[#09090b]',
                'data-[state=active]:bg-white data-[state=active]:text-[#09090b] data-[state=active]:shadow-sm',
              ],
              variant === 'underline' && [
                'px-4 py-2 text-[#71717a]',
                'hover:text-[#09090b]',
                'data-[state=active]:text-[#09090b]',
                'data-[state=active]:after:absolute data-[state=active]:after:-bottom-px',
                'data-[state=active]:after:left-0 data-[state=active]:after:right-0',
                'data-[state=active]:after:h-0.5 data-[state=active]:after:bg-[#3b82f6]',
                'data-[state=active]:after:content-[""]',
              ]
            )}
          >
            {tab.icon && <span className="flex-shrink-0">{tab.icon}</span>}
            {tab.label}
            {tab.badge !== undefined && (
              <span className="inline-flex items-center justify-center h-4 min-w-4 px-1 rounded-full text-[10px] font-semibold bg-[#3b82f6] text-white">
                {tab.badge}
              </span>
            )}
          </TabsPrimitive.Trigger>
        ))}
      </TabsPrimitive.List>

      {tabs.map((tab) => (
        <TabsPrimitive.Content
          key={tab.value}
          value={tab.value}
          className="flex-1 focus:outline-none"
        >
          {tab.content}
        </TabsPrimitive.Content>
      ))}
    </TabsPrimitive.Root>
  )
}
