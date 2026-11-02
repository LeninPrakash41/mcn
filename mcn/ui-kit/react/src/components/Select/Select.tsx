import * as React from 'react'
import * as SelectPrimitive from '@radix-ui/react-select'
import { Check, ChevronDown, ChevronUp } from 'lucide-react'
import { cn } from '../../lib/utils'
import { Label } from '../Label/Label'

export interface SelectOption {
  value: string
  label: string
  disabled?: boolean
}

export interface SelectProps {
  /** Label displayed above the select */
  label?: string
  /** Placeholder text when no value selected */
  placeholder?: string
  /** Array of options to display */
  options: SelectOption[]
  /** Current value (controlled) */
  value?: string
  /** Default value (uncontrolled) */
  defaultValue?: string
  /** Called when selection changes */
  onValueChange?: (value: string) => void
  /** Error message */
  error?: string
  /** Disabled state */
  disabled?: boolean
  /** Additional class for trigger */
  className?: string
  /** Container class */
  wrapperClassName?: string
}

/**
 * MCN Select — accessible dropdown using Radix Select.
 *
 * @example
 * <Select
 *   label="AI Provider"
 *   placeholder="Choose provider..."
 *   options={[{ value: 'openai', label: 'OpenAI' }, { value: 'anthropic', label: 'Anthropic' }]}
 *   onValueChange={(v) => setProvider(v)}
 * />
 */
export function Select({
  label,
  placeholder = 'Select an option…',
  options,
  value,
  defaultValue,
  onValueChange,
  error,
  disabled,
  className,
  wrapperClassName,
}: SelectProps) {
  return (
    <div className={cn('flex flex-col gap-1.5', wrapperClassName)}>
      {label && <Label>{label}</Label>}
      <SelectPrimitive.Root
        value={value}
        defaultValue={defaultValue}
        onValueChange={onValueChange}
        disabled={disabled}
      >
        <SelectPrimitive.Trigger
          className={cn(
            'flex h-9 w-full items-center justify-between rounded-md border',
            'bg-white px-3 py-2 text-[13px] text-[#09090b]',
            'border-[#d4d4d8] placeholder:text-[#a1a1aa]',
            'transition-all duration-[0.12s]',
            'focus:outline-none focus:border-[#3b82f6] focus:ring-2 focus:ring-[rgba(59,130,246,0.2)]',
            'disabled:opacity-40 disabled:cursor-not-allowed disabled:bg-[#f4f4f5]',
            error && 'border-[#dc2626]',
            className
          )}
        >
          <SelectPrimitive.Value placeholder={<span className="text-[#a1a1aa]">{placeholder}</span>} />
          <SelectPrimitive.Icon>
            <ChevronDown size={14} className="text-[#71717a] ml-1 flex-shrink-0" />
          </SelectPrimitive.Icon>
        </SelectPrimitive.Trigger>

        <SelectPrimitive.Portal>
          <SelectPrimitive.Content
            className={cn(
              'relative z-50 min-w-[8rem] overflow-hidden rounded-lg',
              'border border-[#d4d4d8] bg-white shadow-lg',
              'animate-in fade-in-0 zoom-in-95',
              'data-[side=bottom]:slide-in-from-top-2 data-[side=top]:slide-in-from-bottom-2'
            )}
            position="popper"
            sideOffset={4}
          >
            <SelectPrimitive.ScrollUpButton className="flex cursor-default items-center justify-center py-1">
              <ChevronUp size={14} />
            </SelectPrimitive.ScrollUpButton>

            <SelectPrimitive.Viewport className="p-1">
              {options.map((opt) => (
                <SelectPrimitive.Item
                  key={opt.value}
                  value={opt.value}
                  disabled={opt.disabled}
                  className={cn(
                    'relative flex w-full cursor-default select-none items-center',
                    'rounded-md py-1.5 pl-8 pr-3 text-[13px] text-[#09090b]',
                    'outline-none transition-colors',
                    'hover:bg-[#f4f4f5] focus:bg-[#f4f4f5]',
                    'data-[disabled]:pointer-events-none data-[disabled]:opacity-40'
                  )}
                >
                  <span className="absolute left-2 flex h-3.5 w-3.5 items-center justify-center">
                    <SelectPrimitive.ItemIndicator>
                      <Check size={12} className="text-[#3b82f6]" />
                    </SelectPrimitive.ItemIndicator>
                  </span>
                  <SelectPrimitive.ItemText>{opt.label}</SelectPrimitive.ItemText>
                </SelectPrimitive.Item>
              ))}
            </SelectPrimitive.Viewport>

            <SelectPrimitive.ScrollDownButton className="flex cursor-default items-center justify-center py-1">
              <ChevronDown size={14} />
            </SelectPrimitive.ScrollDownButton>
          </SelectPrimitive.Content>
        </SelectPrimitive.Portal>
      </SelectPrimitive.Root>

      {error && (
        <p className="text-[12px] text-[#dc2626]">{error}</p>
      )}
    </div>
  )
}
