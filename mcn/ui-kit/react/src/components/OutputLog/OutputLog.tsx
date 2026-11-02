import * as React from 'react'
import { cn } from '../../lib/utils'

export type LogLevel = 'info' | 'success' | 'error' | 'warn' | 'dim' | 'default'

export interface LogLine {
  id?: string
  type: LogLevel
  text: string
  timestamp?: Date
}

export interface OutputLogProps {
  /** Array of log lines */
  lines: LogLine[]
  /** Auto-scroll to latest */
  autoScroll?: boolean
  /** Show timestamps */
  showTimestamps?: boolean
  /** Max visible lines before scrolling */
  maxHeight?: string
  /** className override */
  className?: string
}

const levelColors: Record<LogLevel, string> = {
  default: '#cdd6f4',
  info:    '#7dcfff',
  success: '#9ece6a',
  error:   '#f7768e',
  warn:    '#e0af68',
  dim:     '#565f89',
}

/**
 * MCN OutputLog — terminal-style output viewer.
 * Uses the playground's Catppuccin Mocha terminal palette.
 *
 * @example
 * <OutputLog lines={[
 *   { type: 'info', text: '→ Starting server on :7842' },
 *   { type: 'success', text: '✓ Build complete in 1.2s' },
 *   { type: 'error', text: 'Error: undefined variable foo' },
 * ]} autoScroll />
 */
export function OutputLog({ lines, autoScroll = true, showTimestamps = false, maxHeight = '300px', className }: OutputLogProps) {
  const bottomRef = React.useRef<HTMLDivElement>(null)

  React.useEffect(() => {
    if (autoScroll) bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [lines, autoScroll])

  return (
    <div
      className={cn('overflow-y-auto p-3 font-mono text-[11.5px] leading-[1.65]', className)}
      style={{ background: '#1e1e2e', color: '#cdd6f4', maxHeight, minHeight: '60px' }}
    >
      {lines.length === 0 ? (
        <span style={{ color: '#565f89' }}>// No output yet</span>
      ) : (
        lines.map((line, i) => (
          <div key={line.id ?? i} className="whitespace-pre-wrap break-all">
            {showTimestamps && line.timestamp && (
              <span style={{ color: '#565f89' }}>
                [{line.timestamp.toLocaleTimeString('en-US', { hour12: false })}]{' '}
              </span>
            )}
            <span style={{ color: levelColors[line.type] }}>{line.text}</span>
          </div>
        ))
      )}
      <div ref={bottomRef} />
    </div>
  )
}
