import * as React from 'react'
import { Send, Square, ChevronDown } from 'lucide-react'
import { cn } from '../../lib/utils'
import { Button } from '../Button/Button'

export interface AIPromptProps {
  /** Placeholder text in the textarea */
  placeholder?: string
  /** Whether an AI request is streaming/loading */
  isStreaming?: boolean
  /** Called with the prompt when submitted */
  onSubmit: (prompt: string) => void
  /** Called to cancel streaming */
  onCancel?: () => void
  /** List of available model names */
  models?: string[]
  /** Currently selected model */
  selectedModel?: string
  /** Called when the model changes */
  onModelChange?: (model: string) => void
  /** Disable the prompt */
  disabled?: boolean
  /** className */
  className?: string
}

/**
 * MCN AIPrompt — multi-line prompt input with model selector and streaming control.
 *
 * @example
 * <AIPrompt
 *   placeholder="Generate a REST API for..."
 *   models={['claude-3-5-sonnet', 'gpt-4o', 'gemini-1.5-pro']}
 *   onSubmit={(prompt) => generate(prompt)}
 * />
 */
export function AIPrompt({
  placeholder = 'Describe what to build…',
  isStreaming = false,
  onSubmit,
  onCancel,
  models = [],
  selectedModel,
  onModelChange,
  disabled,
  className,
}: AIPromptProps) {
  const [value, setValue] = React.useState('')
  const [showModels, setShowModels] = React.useState(false)
  const textareaRef = React.useRef<HTMLTextAreaElement>(null)

  // Auto-resize textarea
  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setValue(e.target.value)
    const ta = e.target
    ta.style.height = 'auto'
    ta.style.height = `${Math.min(ta.scrollHeight, 200)}px`
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey) && value.trim() && !isStreaming) {
      e.preventDefault()
      submit()
    }
  }

  const submit = () => {
    if (!value.trim() || isStreaming) return
    onSubmit(value.trim())
    setValue('')
    if (textareaRef.current) textareaRef.current.style.height = 'auto'
  }

  return (
    <div
      className={cn(
        'flex flex-col rounded-xl border border-[#d4d4d8] bg-white overflow-hidden',
        'focus-within:border-[#3b82f6] focus-within:ring-2 focus-within:ring-[rgba(59,130,246,0.2)]',
        'transition-all duration-[0.12s]',
        disabled && 'opacity-40 pointer-events-none',
        className
      )}
    >
      <textarea
        ref={textareaRef}
        value={value}
        onChange={handleChange}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        disabled={disabled || isStreaming}
        rows={3}
        className={cn(
          'w-full resize-none px-4 py-3 text-[13px] text-[#09090b] font-sans',
          'placeholder:text-[#a1a1aa] focus:outline-none bg-transparent',
          'min-h-[76px] max-h-[200px]'
        )}
      />

      {/* Toolbar */}
      <div className="flex items-center justify-between border-t border-[#f4f4f5] px-3 py-2">
        {/* Model picker */}
        {models.length > 0 && (
          <div className="relative">
            <button
              type="button"
              onClick={() => setShowModels((v) => !v)}
              className="flex items-center gap-1 text-[12px] text-[#71717a] hover:text-[#09090b] transition-colors rounded-md px-2 py-1 hover:bg-[#f4f4f5]"
            >
              <span className="max-w-[120px] truncate">{selectedModel ?? models[0]}</span>
              <ChevronDown size={11} />
            </button>
            {showModels && (
              <div className="absolute bottom-full left-0 mb-1 min-w-[160px] rounded-lg border border-[#e4e4e7] bg-white shadow-lg z-10 py-1">
                {models.map((m) => (
                  <button
                    key={m}
                    type="button"
                    onClick={() => { onModelChange?.(m); setShowModels(false) }}
                    className={cn(
                      'w-full text-left px-3 py-1.5 text-[12.5px] hover:bg-[#f4f4f5] transition-colors',
                      m === (selectedModel ?? models[0]) && 'text-[#3b82f6] font-medium'
                    )}
                  >
                    {m}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        {!models.length && <div />}

        {/* Action */}
        <div className="flex items-center gap-2">
          <span className="text-[11px] text-[#a1a1aa] hidden sm:block">
            {isStreaming ? '' : '⌘↵'}
          </span>
          {isStreaming ? (
            <Button variant="destructive" size="sm" onClick={onCancel} leftIcon={<Square size={12} />}>
              Stop
            </Button>
          ) : (
            <Button
              variant="primary"
              size="sm"
              onClick={submit}
              disabled={!value.trim()}
              leftIcon={<Send size={12} />}
            >
              Send
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}
