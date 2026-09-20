import { useState, useCallback, useRef } from 'react'

export interface MCNConfig {
  /** Base URL of the MCN server (default: http://localhost:7842) */
  baseUrl?: string
}

export interface MCNResult {
  output?: string
  error?: string
  success: boolean
}

export interface UseMCNReturn {
  /** Execute MCN code and return the output */
  execute: (code: string) => Promise<MCNResult>
  /** Format MCN code */
  format: (code: string) => Promise<string>
  /** Type-check MCN code */
  check: (code: string) => Promise<MCNResult>
  /** Run tests in MCN code */
  runTests: (code: string) => Promise<MCNResult>
  /** Stream AI-generated MCN code (calls onChunk for each token) */
  generate: (prompt: string, onChunk: (chunk: string) => void) => Promise<void>
  /** Cancel any in-flight streaming request */
  cancelGenerate: () => void
  /** True while any request is in-flight */
  isLoading: boolean
  /** True while generate is streaming */
  isStreaming: boolean
  /** Last error encountered */
  error: string | null
}

/**
 * Hook to connect to an MCN backend server.
 * Provides execute, format, check, test, and AI generate operations.
 *
 * @example
 * const { execute, isLoading } = useMCN({ baseUrl: 'http://localhost:7842' })
 * const result = await execute('log("Hello, MCN!")')
 */
export function useMCN({ baseUrl = 'http://localhost:7842' }: MCNConfig = {}): UseMCNReturn {
  const [isLoading, setIsLoading] = useState(false)
  const [isStreaming, setIsStreaming] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  const request = useCallback(
    async (endpoint: string, body: Record<string, unknown>): Promise<Response> => {
      setIsLoading(true)
      setError(null)
      try {
        const res = await fetch(`${baseUrl}${endpoint}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        })
        return res
      } finally {
        setIsLoading(false)
      }
    },
    [baseUrl]
  )

  const execute = useCallback(
    async (code: string): Promise<MCNResult> => {
      try {
        const res = await request('/api/execute', { code })
        const data = await res.json()
        return { output: data.output, error: data.error, success: res.ok && !data.error }
      } catch (e) {
        const msg = e instanceof Error ? e.message : 'Network error'
        setError(msg)
        return { error: msg, success: false }
      }
    },
    [request]
  )

  const format = useCallback(
    async (code: string): Promise<string> => {
      try {
        const res = await request('/api/format', { code })
        const data = await res.json()
        return data.formatted ?? code
      } catch {
        return code
      }
    },
    [request]
  )

  const check = useCallback(
    async (code: string): Promise<MCNResult> => {
      try {
        const res = await request('/api/check', { code })
        const data = await res.json()
        return { output: data.output, error: data.error, success: res.ok && !data.error }
      } catch (e) {
        const msg = e instanceof Error ? e.message : 'Network error'
        return { error: msg, success: false }
      }
    },
    [request]
  )

  const runTests = useCallback(
    async (code: string): Promise<MCNResult> => {
      try {
        const res = await request('/api/test', { code })
        const data = await res.json()
        return { output: data.output, error: data.error, success: res.ok && !data.error }
      } catch (e) {
        const msg = e instanceof Error ? e.message : 'Network error'
        return { error: msg, success: false }
      }
    },
    [request]
  )

  const generate = useCallback(
    async (prompt: string, onChunk: (chunk: string) => void): Promise<void> => {
      abortRef.current = new AbortController()
      setIsStreaming(true)
      setError(null)
      try {
        const res = await fetch(`${baseUrl}/api/generate`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ prompt }),
          signal: abortRef.current.signal,
        })

        if (!res.ok) throw new Error(`Server error ${res.status}`)

        const reader = res.body?.getReader()
        if (!reader) return

        const decoder = new TextDecoder()
        let buffer = ''

        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          buffer += decoder.decode(value, { stream: true })

          const lines = buffer.split('\n')
          buffer = lines.pop() ?? ''
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const data = line.slice(6).trim()
              if (data === '[DONE]') continue
              try {
                const parsed = JSON.parse(data)
                if (parsed.token) onChunk(parsed.token)
              } catch {
                // non-JSON line, pass raw
                onChunk(data)
              }
            }
          }
        }
      } catch (e) {
        if ((e as Error).name !== 'AbortError') {
          const msg = e instanceof Error ? e.message : 'Streaming error'
          setError(msg)
        }
      } finally {
        setIsStreaming(false)
        abortRef.current = null
      }
    },
    [baseUrl]
  )

  const cancelGenerate = useCallback(() => {
    abortRef.current?.abort()
  }, [])

  return { execute, format, check, runTests, generate, cancelGenerate, isLoading, isStreaming, error }
}
