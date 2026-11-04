import * as React from "react"
import { cn, uid } from "@/lib/utils"
import { Icon } from "./icon"
import { ChatBot } from "./chat"
import { toast } from "./toast"

/* Configure an AI agent (instructions, model, tools, knowledge, memory), try it
   in a live chat, and save it. The backend decides what "run" means: onTest
   receives the draft agent and the message, onSave receives the agent. */

export interface Agent {
  id?: string
  name: string
  description: string
  instructions: string
  model: string
  temperature: number
  tools: string[]
  knowledge: string
  memory: boolean
}

export interface ToolOption { key: string; label: string; icon?: string; description?: string }

const DEFAULT_TOOLS: ToolOption[] = [
  { key: "search_docs", label: "Search documents", icon: "BookOpen", description: "Answer from your knowledge base" },
  { key: "query_db", label: "Query database", icon: "Database", description: "Read records from your tables" },
  { key: "http", label: "Call APIs", icon: "Globe", description: "Make HTTP requests" },
  { key: "send_email", label: "Send email", icon: "Mail", description: "Email customers or the team" },
  { key: "create_task", label: "Create tasks", icon: "ListTodo", description: "Add follow-ups to your task list" },
  { key: "notify", label: "Notify team", icon: "Bell", description: "Post to Slack or notifications" },
]

const DEFAULT_MODELS = ["claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"]

export interface AgentBuilderProps {
  agent?: Partial<Agent>
  /** Saved agents, shown in a list to switch between */
  agents?: Partial<Agent>[]
  tools?: (string | ToolOption)[]
  models?: string[]
  onSave?: (agent: Agent) => Promise<any> | any
  onTest?: (agent: Agent, message: string, history: { role: string; content: string }[]) => Promise<any> | any
  onDelete?: (agent: Agent) => Promise<any> | any
  className?: string
}

const blank = (a?: Partial<Agent>): Agent => ({
  name: "", description: "", instructions: "", model: DEFAULT_MODELS[0], temperature: 0.3, tools: [], knowledge: "", memory: true, ...a,
})

const field = "w-full rounded-lg border border-input bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"

export function AgentBuilder({ agent, agents, tools, models = DEFAULT_MODELS, onSave, onTest, onDelete, className }: AgentBuilderProps) {
  const [draft, setDraft] = React.useState<Agent>(() => blank(agent))
  const [saving, setSaving] = React.useState(false)
  const [tab, setTab] = React.useState<"configure" | "test">("configure")
  const [chatKey, setChatKey] = React.useState(0)
  const set = <K extends keyof Agent>(k: K, v: Agent[K]) => setDraft((d) => ({ ...d, [k]: v }))
  const toolOpts: ToolOption[] = (tools?.length ? tools : DEFAULT_TOOLS).map((t) => (typeof t === "string" ? { key: t, label: t.replace(/_/g, " ") } : t))
  const problems = [!draft.name.trim() && "Give the agent a name", !draft.instructions.trim() && "Write its instructions"].filter(Boolean) as string[]

  React.useEffect(() => { if (agent) setDraft(blank(agent)) }, [agent?.id])

  const save = async () => {
    if (problems.length) { toast.warning(problems[0]); return }
    setSaving(true)
    try {
      const res = await onSave?.({ ...draft, id: draft.id || uid("agent") })
      if (res && res.success === false) throw new Error(res.error || "Save failed")
      toast.success(`${draft.name} saved`)
    } catch (e: any) { toast.error("Couldn't save the agent", { description: e?.message }) }
    finally { setSaving(false) }
  }

  const configure = (
    <div className="space-y-5">
      <section className="space-y-3">
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="space-y-1.5"><span className="text-sm font-medium">Name</span>
            <input className={field} value={draft.name} placeholder="Support triage" onChange={(e) => set("name", e.target.value)} /></label>
          <label className="space-y-1.5"><span className="text-sm font-medium">Model</span>
            <select className={field} value={draft.model} onChange={(e) => set("model", e.target.value)}>
              {models.map((m) => <option key={m} value={m}>{m}</option>)}
            </select></label>
        </div>
        <label className="block space-y-1.5"><span className="text-sm font-medium">Description</span>
          <input className={field} value={draft.description} placeholder="Routes incoming tickets and drafts first replies" onChange={(e) => set("description", e.target.value)} /></label>
        <label className="block space-y-1.5">
          <span className="flex items-center justify-between text-sm font-medium">Instructions<span className="text-xs font-normal text-muted-foreground">{draft.instructions.length} chars</span></span>
          <textarea className={cn(field, "min-h-[140px] font-mono text-[13px] leading-relaxed")} value={draft.instructions}
            placeholder={"You are a support agent for Acme.\n- Classify each ticket as billing, bug or account.\n- Reply politely in under 80 words."}
            onChange={(e) => set("instructions", e.target.value)} />
        </label>
        <label className="block space-y-1.5">
          <span className="flex items-center justify-between text-sm font-medium">Creativity<span className="text-xs font-normal tabular-nums text-muted-foreground">{draft.temperature.toFixed(1)}</span></span>
          <input type="range" min={0} max={1} step={0.1} value={draft.temperature} onChange={(e) => set("temperature", Number(e.target.value))} className="w-full accent-primary" />
          <span className="flex justify-between text-xs text-muted-foreground"><span>Precise</span><span>Creative</span></span>
        </label>
      </section>

      <section className="space-y-2">
        <p className="text-sm font-medium">Tools</p>
        <div className="grid gap-2 sm:grid-cols-2">
          {toolOpts.map((t) => {
            const on = draft.tools.includes(t.key)
            return (
              <button key={t.key} type="button" aria-pressed={on}
                onClick={() => set("tools", on ? draft.tools.filter((x) => x !== t.key) : [...draft.tools, t.key])}
                className={cn("flex items-start gap-3 rounded-lg border p-3 text-left transition-colors", on ? "border-primary bg-primary/5" : "hover:bg-accent")}>
                <span className={cn("grid h-8 w-8 shrink-0 place-items-center rounded-lg", on ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground")}>
                  <Icon name={t.icon || "Plug"} size={15} />
                </span>
                <span className="min-w-0">
                  <span className="block text-sm font-medium capitalize">{t.label}</span>
                  {t.description && <span className="block text-xs text-muted-foreground">{t.description}</span>}
                </span>
              </button>
            )
          })}
        </div>
      </section>

      <section className="space-y-3">
        <label className="block space-y-1.5"><span className="text-sm font-medium">Knowledge</span>
          <textarea className={cn(field, "min-h-[90px]")} value={draft.knowledge}
            placeholder="Paste FAQs, policies or product facts the agent should rely on." onChange={(e) => set("knowledge", e.target.value)} /></label>
        <label className="flex items-center justify-between rounded-lg border p-3">
          <span><span className="block text-sm font-medium">Conversation memory</span>
            <span className="block text-xs text-muted-foreground">Remember earlier messages in the same conversation</span></span>
          <input type="checkbox" checked={draft.memory} onChange={(e) => set("memory", e.target.checked)} className="h-4 w-4 accent-primary" />
        </label>
      </section>
    </div>
  )

  return (
    <div className={cn("overflow-hidden rounded-xl border bg-card text-card-foreground shadow-sm", className)}>
      <div className="flex flex-wrap items-center gap-3 border-b px-5 py-4">
        <span className="grid h-10 w-10 place-items-center rounded-xl bg-primary/10 text-primary"><Icon name="Bot" size={20} /></span>
        <div className="min-w-0 flex-1">
          <p className="truncate font-semibold">{draft.name || "New agent"}</p>
          <p className="truncate text-sm text-muted-foreground">{draft.description || "Configure, test and save an AI agent"}</p>
        </div>
        {agents && agents.length > 0 && (
          <select aria-label="Saved agents" className={cn(field, "w-auto")} value={draft.id || ""}
            onChange={(e) => { const a = agents.find((x) => x.id === e.target.value); setDraft(blank(a)); setChatKey((k) => k + 1) }}>
            <option value="">New agent</option>
            {agents.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
          </select>
        )}
        {onDelete && draft.id && (
          <button type="button" onClick={async () => { await onDelete(draft); setDraft(blank()); toast("Agent deleted") }}
            className="inline-flex h-9 items-center gap-1.5 rounded-lg border px-3 text-sm text-red-600 hover:bg-red-500/10"><Icon name="Trash2" size={15} />Delete</button>
        )}
        <button type="button" onClick={save} disabled={saving}
          className="inline-flex h-9 items-center gap-1.5 rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-60">
          <Icon name={saving ? "Loader2" : "Save"} size={15} className={cn(saving && "animate-spin")} />{saving ? "Saving…" : "Save agent"}
        </button>
      </div>

      <div className="flex border-b lg:hidden" role="tablist">
        {(["configure", "test"] as const).map((t) => (
          <button key={t} type="button" role="tab" aria-selected={tab === t} onClick={() => setTab(t)}
            className={cn("flex-1 border-b-2 py-2.5 text-sm font-medium capitalize", tab === t ? "border-primary" : "border-transparent text-muted-foreground")}>{t}</button>
        ))}
      </div>

      <div className="grid lg:grid-cols-[minmax(0,1fr)_minmax(0,26rem)]">
        <div className={cn("p-5 lg:block", tab !== "configure" && "hidden")}>{configure}</div>
        <div className={cn("bg-muted/30 p-5 lg:block lg:border-l", tab !== "test" && "hidden")}>
          <div className="mb-3 flex items-center justify-between">
            <p className="text-sm font-medium">Test your agent</p>
            {problems.length > 0 && <p className="text-xs text-amber-600">{problems[0]}</p>}
          </div>
          <ChatBot key={chatKey} title={draft.name || "Agent preview"} subtitle={draft.model} height={560}
            welcome={draft.description ? `Hi! ${draft.description}.` : "Configure me on the left, then try a message."}
            onSend={(m, h) => (onTest ? onTest(draft, m, h) : `(${draft.name || "agent"}) I'd answer using: ${draft.tools.join(", ") || "no tools"}.`)} />
        </div>
      </div>
    </div>
  )
}
