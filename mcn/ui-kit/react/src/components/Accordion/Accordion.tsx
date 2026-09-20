import * as React from 'react'
import * as AccordionPrimitive from '@radix-ui/react-accordion'
import { ChevronDown } from 'lucide-react'
import { cn } from '../../lib/utils'

export interface AccordionItem {
  value: string
  trigger: React.ReactNode
  content: React.ReactNode
  disabled?: boolean
}

export interface AccordionProps {
  items: AccordionItem[]
  type?: 'single' | 'multiple'
  defaultValue?: string | string[]
  className?: string
}

/**
 * MCN Accordion — collapsible content sections using Radix Accordion.
 *
 * @example
 * <Accordion items={[{ value: 'faq1', trigger: 'What is MCN?', content: <p>MCN is...</p> }]} />
 */
export function Accordion({ items, type = 'single', defaultValue, className }: AccordionProps) {
  return (
    <AccordionPrimitive.Root
      type={type as 'single'}
      defaultValue={defaultValue as string}
      collapsible
      className={cn('w-full divide-y divide-[#e4e4e7] border border-[#e4e4e7] rounded-xl overflow-hidden', className)}
    >
      {items.map((item) => (
        <AccordionPrimitive.Item key={item.value} value={item.value} disabled={item.disabled}>
          <AccordionPrimitive.Header>
            <AccordionPrimitive.Trigger
              className={cn(
                'flex w-full items-center justify-between px-4 py-3',
                'text-[13px] font-medium text-[#09090b] text-left',
                'hover:bg-[#f9f9fb] transition-colors duration-[0.12s]',
                'focus:outline-none focus:ring-2 focus:ring-inset focus:ring-[#3b82f6]',
                'disabled:opacity-40 disabled:pointer-events-none',
                'data-[state=open]:bg-[#f9f9fb]',
                '[&[data-state=open]>svg]:rotate-180'
              )}
            >
              {item.trigger}
              <ChevronDown size={15} className="text-[#71717a] flex-shrink-0 transition-transform duration-200" />
            </AccordionPrimitive.Trigger>
          </AccordionPrimitive.Header>
          <AccordionPrimitive.Content
            className={cn(
              'overflow-hidden text-[13px] text-[#71717a]',
              'data-[state=closed]:animate-accordion-up data-[state=open]:animate-accordion-down'
            )}
          >
            <div className="px-4 pb-4 pt-1">{item.content}</div>
          </AccordionPrimitive.Content>
        </AccordionPrimitive.Item>
      ))}
    </AccordionPrimitive.Root>
  )
}
