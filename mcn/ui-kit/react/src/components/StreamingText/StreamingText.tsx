import * as React from 'react'
import { cn } from '../../lib/utils'

export interface StreamingTextProps {
  /** Full text to display */
  text: string
  /** Whether currently streaming (animates character by character) */
  isStreaming?: boolean
  /** Speed in ms per character when streaming */
  speed?: number
  /** Text style */
  className?: string
  /** Show blinking cursor while streaming */
  showCursor?: boolean
}

/**
 * MCN StreamingText — displays text with a typewriter animation while streaming.
 * Instantly shows full text when isStreaming becomes false.
 *
 * @example
 * <StreamingText text={aiResponse} isStreaming={isLoading} className="text-[13px]" />
 */
export function StreamingText({
  text,
  isStreaming = false,
  speed = 8,
  className,
  showCursor = true,
}: StreamingTextProps) {
  const [displayed, setDisplayed] = React.useState('')
  const prevText = React.useRef('')
  const timerRef = React.useRef<ReturnType<typeof setInterval> | null>(null)

  React.useEffect(() => {
    // If new text is longer, animate the new portion
    if (isStreaming && text.startsWith(prevText.current)) {
      let i = prevText.current.length
      if (timerRef.current) clearInterval(timerRef.current)
      timerRef.current = setInterval(() => {
        if (i >= text.length) {
          clearInterval(timerRef.current!)
          prevText.current = text
          setDisplayed(text)
        } else {
          i++
          setDisplayed(text.slice(0, i))
        }
      }, speed)
    } else {
      // Not streaming or text changed drastically — show immediately
      if (timerRef.current) clearInterval(timerRef.current)
      setDisplayed(text)
      prevText.current = text
    }

    return () => { if (timerRef.current) clearInterval(timerRef.current) }
  }, [text, isStreaming, speed])

  return (
    <span className={cn('whitespace-pre-wrap', className)}>
      {displayed}
      {showCursor && isStreaming && (
        <span
          className="inline-block w-[2px] h-[1em] align-text-bottom bg-[#3b82f6] ml-[1px]"
          style={{ animation: 'blink 1s step-end infinite' }}
        />
      )}
      <style>{`@keyframes blink { 0%,100%{opacity:1} 50%{opacity:0} }`}</style>
    </span>
  )
}
