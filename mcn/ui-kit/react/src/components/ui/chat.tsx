import * as React from "react"
import { cn } from "@/lib/utils"
import { Icon } from "./icon"

/* Chat UI for assistants and support bots. `onSend(message, history)` returns the
   reply — a string, or an object with a `reply`, `answer`, `message` or `data`
   field (the shapes MCN endpoints usually return). */

export interface ToolCall { name: string; input?: any; output?: any; error?: string; ms?: number }
export interface ChatMessage { role: "user" | "assistant"; content: string; time: number; error?: boolean; tools?: ToolCall[] }

export interface ChatProps {
  onSend?: (message: string, history: { role: string; content: string }[]) => Promise<any> | any
  title?: string
  subtitle?: string
  placeholder?: string
  /** First message shown from the assistant */
  welcome?: string
  /** Clickable starter prompts */
  suggestions?: string[]
  height?: number | string
  className?: string
  /** Name/icon for the assistant avatar */
  avatar?: string
}

function replyText(r: any): string {
  if (r === null || r === undefined) return ""
  if (typeof r === "string") return r
  for (const k of ["reply", "answer", "message", "response", "text", "output", "data"]) {
    if (r[k] !== undefined) return replyText(r[k])
  }
  if (r.success === false && r.error) throw new Error(String(r.error))
  return JSON.stringify(r)
}

/** The tools an agent called for this reply (agent_run's tool_calls). */
function ToolCalls({ calls }: { calls: ToolCall[] }) {
  const [open, setOpen] = React.useState(false)
  return (
    <div className="mt-2 rounded-lg border bg-background/60 text-xs">
      <button type="button" onClick={() => setOpen(!open)} aria-expanded={open}
        className="flex w-full items-center gap-1.5 px-2.5 py-1.5 text-muted-foreground hover:text-foreground">
        <Icon name="Wrench" size={12} />
        Used {calls.length} tool{calls.length === 1 ? "" : "s"}: {calls.map((c) => c.name).join(", ")}
        <Icon name="ChevronDown" size={12} className={cn("ml-auto transition-transform", open && "rotate-180")} />
      </button>
      {open && (
        <ul className="space-y-2 border-t px-2.5 py-2">
          {calls.map((c, i) => (
            <li key={i}>
              <p className="flex items-center gap-1.5 font-medium">
                <Icon name={c.error ? "XCircle" : "CheckCircle"} size={12} className={c.error ? "text-red-500" : "text-emerald-500"} />
                {c.name}{c.ms !== undefined && <span className="font-normal text-muted-foreground">· {c.ms} ms</span>}
              </p>
              <pre className="mt-1 max-h-32 overflow-auto whitespace-pre-wrap rounded bg-muted px-2 py-1 font-mono text-[11px]">
                {"input: " + JSON.stringify(c.input ?? {}) + "\n" + (c.error ? "error: " + c.error : "output: " + JSON.stringify(c.output))}
              </pre>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

/** Light markdown: **bold**, `code`, ``` blocks, bullet and numbered lists, links. */
function Markdown({ text }: { text: string }) {
  const blocks = text.split(/```(?:\w+)?\n?([\s\S]*?)```/g)
  const inline = (s: string, key: number) => {
    const parts = s.split(/(\*\*[^*]+\*\*|`[^`]+`|https?:\/\/\S+)/g)
    return <React.Fragment key={key}>{parts.map((p, i) =>
      p.startsWith("**") ? <strong key={i}>{p.slice(2, -2)}</strong>
      : p.startsWith("`") ? <code key={i} className="rounded bg-black/10 px-1 py-0.5 font-mono text-[0.85em] dark:bg-white/10">{p.slice(1, -1)}</code>
      : /^https?:\/\//.test(p) ? <a key={i} href={p} target="_blank" rel="noreferrer" className="underline underline-offset-2">{p}</a>
      : p)}</React.Fragment>
  }
  return (
    <div className="space-y-2">
      {blocks.map((b, i) => i % 2 === 1
        ? <pre key={i} className="overflow-x-auto rounded-lg bg-black/80 p-3 font-mono text-xs text-white">{b.trim()}</pre>
        : b.trim().split(/\n{2,}/).map((para, j) => {
            const lines = para.split("\n")
            if (lines.every((l) => /^\s*([-*]|\d+\.)\s+/.test(l))) {
              const ordered = /^\s*\d+\./.test(lines[0])
              const Tag = ordered ? "ol" : "ul"
              return <Tag key={`${i}-${j}`} className={cn("space-y-1 pl-5", ordered ? "list-decimal" : "list-disc")}>
                {lines.map((l, k) => <li key={k}>{inline(l.replace(/^\s*([-*]|\d+\.)\s+/, ""), k)}</li>)}
              </Tag>
            }
            return <p key={`${i}-${j}`} className="whitespace-pre-wrap">{lines.map((l, k) => <React.Fragment key={k}>{k > 0 && <br />}{inline(l, k)}</React.Fragment>)}</p>
          }))}
    </div>
  )
}

export function ChatBot({ onSend, title = "Assistant", subtitle, placeholder = "Type a message…", welcome, suggestions = [], height = 520, className, avatar = "Bot" }: ChatProps) {
  const initial: ChatMessage[] = welcome ? [{ role: "assistant", content: welcome, time: Date.now() }] : []
  const [messages, setMessages] = React.useState<ChatMessage[]>(initial)
  const [input, setInput] = React.useState("")
  const [busy, setBusy] = React.useState(false)
  const end = React.useRef<HTMLDivElement>(null)
  const box = React.useRef<HTMLTextAreaElement>(null)

  React.useEffect(() => { end.current?.scrollIntoView({ block: "end", behavior: "smooth" }) }, [messages, busy])

  const send = async (text: string, base = messages) => {
    const message = text.trim()
    if (!message || busy) return
    const history = base.filter((m) => !m.error).map(({ role, content }) => ({ role, content }))
    const next: ChatMessage[] = [...base, { role: "user", content: message, time: Date.now() }]
    setMessages(next); setInput(""); setBusy(true)
    try {
      const raw = onSend ? await onSend(message, history) : "Connect this chat to an endpoint to get answers."
      const reply = replyText(raw)
      const tools = raw && Array.isArray(raw.tool_calls) && raw.tool_calls.length ? raw.tool_calls as ToolCall[] : undefined
      setMessages([...next, { role: "assistant", content: reply || "…", time: Date.now(), tools }])
    } catch (e: any) {
      setMessages([...next, { role: "assistant", content: e?.message || "Something went wrong.", time: Date.now(), error: true }])
    } finally {
      setBusy(false); box.current?.focus()
    }
  }

  const retry = () => {
    const lastUser = [...messages].reverse().find((m) => m.role === "user")
    if (!lastUser) return
    const idx = messages.lastIndexOf(lastUser)
    send(lastUser.content, messages.slice(0, idx))
  }

  return (
    <div className={cn("flex flex-col overflow-hidden rounded-xl border bg-card text-card-foreground shadow-sm", className)} style={{ height }}>
      <div className="flex items-center gap-3 border-b px-4 py-3">
        <span className="grid h-9 w-9 place-items-center rounded-full bg-primary/10 text-primary"><Icon name={avatar} size={18} /></span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-semibold">{title}</p>
          <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <span className={cn("h-1.5 w-1.5 rounded-full", busy ? "animate-pulse bg-amber-500" : "bg-emerald-500")} />
            {busy ? "Thinking…" : subtitle || "Online"}
          </p>
        </div>
        {messages.length > initial.length && (
          <button type="button" onClick={() => setMessages(initial)} aria-label="New conversation" title="New conversation"
            className="grid h-8 w-8 place-items-center rounded-lg text-muted-foreground hover:bg-accent hover:text-foreground"><Icon name="RefreshCw" size={15} /></button>
        )}
      </div>

      <div className="flex-1 space-y-4 overflow-y-auto p-4" aria-live="polite">
        {messages.length === 0 && (
          <div className="flex h-full flex-col items-center justify-center gap-3 text-center">
            <span className="grid h-12 w-12 place-items-center rounded-full bg-primary/10 text-primary"><Icon name="Sparkles" size={22} /></span>
            <p className="text-sm text-muted-foreground">Ask me anything to get started.</p>
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={cn("group flex gap-2.5", m.role === "user" && "flex-row-reverse")}>
            {m.role === "assistant" && <span className="mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-full bg-primary/10 text-primary"><Icon name={avatar} size={14} /></span>}
            <div className={cn("max-w-[80%] rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed",
              m.role === "user" ? "rounded-tr-sm bg-primary text-primary-foreground"
                : m.error ? "rounded-tl-sm border border-red-500/30 bg-red-500/5 text-red-700 dark:text-red-400" : "rounded-tl-sm bg-muted")}>
              {m.role === "assistant" ? <Markdown text={m.content} /> : <p className="whitespace-pre-wrap">{m.content}</p>}
              {m.tools && <ToolCalls calls={m.tools} />}
              {m.error && <button type="button" onClick={retry} className="mt-2 inline-flex items-center gap-1 text-xs font-medium underline-offset-2 hover:underline"><Icon name="RefreshCw" size={12} />Retry</button>}
            </div>
            {m.role === "assistant" && !m.error && (
              <button type="button" aria-label="Copy" onClick={() => navigator.clipboard?.writeText(m.content)}
                className="self-end text-muted-foreground opacity-0 transition-opacity hover:text-foreground group-hover:opacity-100"><Icon name="Copy" size={13} /></button>
            )}
          </div>
        ))}
        {busy && (
          <div className="flex gap-2.5">
            <span className="grid h-7 w-7 place-items-center rounded-full bg-primary/10 text-primary"><Icon name={avatar} size={14} /></span>
            <div className="flex items-center gap-1 rounded-2xl rounded-tl-sm bg-muted px-4 py-3">
              {[0, 1, 2].map((d) => <span key={d} className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted-foreground/60" style={{ animationDelay: `${d * 150}ms` }} />)}
            </div>
          </div>
        )}
        <div ref={end} />
      </div>

      {suggestions.length > 0 && messages.filter((m) => m.role === "user").length === 0 && (
        <div className="flex flex-wrap gap-2 px-4 pb-2">
          {suggestions.map((s) => (
            <button key={s} type="button" onClick={() => send(s)} className="rounded-full border px-3 py-1.5 text-xs hover:bg-accent">{s}</button>
          ))}
        </div>
      )}

      <form className="border-t p-3" onSubmit={(e) => { e.preventDefault(); send(input) }}>
        <div className="flex items-end gap-2 rounded-xl border border-input bg-background p-1.5 focus-within:ring-2 focus-within:ring-ring">
          <textarea ref={box} rows={1} value={input} placeholder={placeholder} aria-label="Message"
            onChange={(e) => { setInput(e.target.value); e.target.style.height = "auto"; e.target.style.height = Math.min(e.target.scrollHeight, 140) + "px" }}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(input) } }}
            className="max-h-36 flex-1 resize-none bg-transparent px-2 py-1.5 text-sm outline-none" />
          <button type="submit" disabled={!input.trim() || busy} aria-label="Send"
            className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-primary text-primary-foreground disabled:opacity-40"><Icon name="Send" size={15} /></button>
        </div>
      </form>
    </div>
  )
}

/** The same chat as a floating button in the corner that opens a panel. */
export function ChatWidget(props: ChatProps & { label?: string }) {
  const [open, setOpen] = React.useState(false)
  return (
    <div className="fixed bottom-5 right-5 z-[80] flex flex-col items-end gap-3">
      {open && <ChatBot {...props} height={props.height || 520} className={cn("w-[min(24rem,calc(100vw-2.5rem))] shadow-2xl", props.className)} />}
      <button type="button" onClick={() => setOpen(!open)} aria-label={open ? "Close chat" : props.label || "Open chat"}
        className="grid h-14 w-14 place-items-center rounded-full bg-primary text-primary-foreground shadow-xl transition-transform hover:scale-105">
        <Icon name={open ? "X" : "MessageCircle"} size={24} />
      </button>
    </div>
  )
}
