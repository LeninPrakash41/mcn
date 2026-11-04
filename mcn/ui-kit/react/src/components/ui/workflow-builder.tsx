import * as React from "react"
import { cn, uid } from "@/lib/utils"
import { Icon } from "./icon"
import { toast } from "./toast"

/* Visual automation editor: a trigger followed by steps. Insert, reorder,
   duplicate and delete steps, configure each one in the side panel, then run
   it and watch each step's status and output. onRun receives the workflow and
   returns { steps: [{ id, status, output?, error? }] }; without onRun, runs
   are simulated so the builder can be tried on its own. */

export interface WorkflowStep { id: string; type: string; name?: string; config: Record<string, any> }
export interface Workflow {
  id?: string
  name: string
  enabled: boolean
  trigger: { type: string; config: Record<string, any> }
  steps: WorkflowStep[]
}

type FieldSpec = { key: string; label: string; type?: "text" | "textarea" | "select" | "number"; options?: string[]; placeholder?: string; required?: boolean }
type StepSpec = { label: string; icon: string; tone: string; description: string; fields: FieldSpec[]; summary: (c: Record<string, any>) => string }

export const STEP_TYPES: Record<string, StepSpec> = {
  ai: { label: "AI", icon: "Sparkles", tone: "violet", description: "Generate, summarise or classify with AI",
    fields: [{ key: "prompt", label: "Prompt", type: "textarea", required: true, placeholder: "Summarise this ticket in one line: {{trigger.text}}" },
             { key: "save_as", label: "Save result as", placeholder: "summary" }],
    summary: (c) => c.prompt || "Write a prompt" },
  condition: { label: "Condition", icon: "GitBranch", tone: "amber", description: "Continue only when a rule matches",
    fields: [{ key: "field", label: "Value", required: true, placeholder: "{{summary}}" },
             { key: "operator", label: "Operator", type: "select", options: ["contains", "equals", "not equals", "greater than", "less than", "is empty"] },
             { key: "value", label: "Compare with", placeholder: "urgent" }],
    summary: (c) => (c.field ? `If ${c.field} ${c.operator || "contains"} ${c.value ?? ""}` : "Set a rule") },
  http: { label: "HTTP request", icon: "Globe", tone: "sky", description: "Call an API or webhook",
    fields: [{ key: "method", label: "Method", type: "select", options: ["GET", "POST", "PUT", "DELETE"] },
             { key: "url", label: "URL", required: true, placeholder: "https://api.example.com/orders" },
             { key: "body", label: "Body (JSON)", type: "textarea", placeholder: '{"id": "{{trigger.id}}"}' }],
    summary: (c) => (c.url ? `${c.method || "GET"} ${c.url}` : "Enter a URL") },
  database: { label: "Database", icon: "Database", tone: "emerald", description: "Read or write records",
    fields: [{ key: "sql", label: "SQL", type: "textarea", required: true, placeholder: "INSERT INTO tickets (title) VALUES ({{trigger.title}})" }],
    summary: (c) => c.sql || "Write a query" },
  notify: { label: "Notify", icon: "Bell", tone: "rose", description: "Send a notification",
    fields: [{ key: "channel", label: "Channel", type: "select", options: ["In-app", "Slack", "SMS"] },
             { key: "message", label: "Message", type: "textarea", required: true, placeholder: "New urgent ticket: {{summary}}" }],
    summary: (c) => (c.message ? `${c.channel || "In-app"}: ${c.message}` : "Write a message") },
  email: { label: "Email", icon: "Mail", tone: "sky", description: "Send an email",
    fields: [{ key: "to", label: "To", required: true, placeholder: "team@example.com" }, { key: "subject", label: "Subject", required: true },
             { key: "body", label: "Body", type: "textarea" }],
    summary: (c) => (c.to ? `To ${c.to}: ${c.subject || ""}` : "Add a recipient") },
  delay: { label: "Delay", icon: "Timer", tone: "slate", description: "Wait before continuing",
    fields: [{ key: "seconds", label: "Seconds", type: "number", required: true, placeholder: "60" }],
    summary: (c) => (c.seconds ? `Wait ${c.seconds}s` : "Set a duration") },
  transform: { label: "Transform", icon: "Repeat", tone: "slate", description: "Reshape data for the next step",
    fields: [{ key: "expression", label: "Expression", type: "textarea", required: true, placeholder: '{name: upper({{trigger.name}})}' },
             { key: "save_as", label: "Save result as" }],
    summary: (c) => c.expression || "Write an expression" },
  approval: { label: "Approval", icon: "UserCheck", tone: "amber", description: "Pause until someone approves",
    fields: [{ key: "approver", label: "Approver", required: true, placeholder: "manager@example.com" }, { key: "message", label: "Request", type: "textarea" }],
    summary: (c) => (c.approver ? `Ask ${c.approver}` : "Choose an approver") },
}

const TRIGGERS: Record<string, { label: string; icon: string; fields: FieldSpec[]; summary: (c: Record<string, any>) => string }> = {
  manual: { label: "Run manually", icon: "Play", fields: [], summary: () => "Started with the Run button" },
  schedule: { label: "On a schedule", icon: "CalendarDays", fields: [{ key: "cron", label: "Cron expression", required: true, placeholder: "0 9 * * 1-5" }],
    summary: (c) => (c.cron ? `Cron ${c.cron}` : "Set a schedule") },
  webhook: { label: "Webhook", icon: "Webhook", fields: [{ key: "path", label: "Path", required: true, placeholder: "/hooks/new-order" }],
    summary: (c) => (c.path ? `POST ${c.path}` : "Set a path") },
  record: { label: "New record", icon: "Table", fields: [{ key: "table", label: "Table", required: true, placeholder: "tickets" },
    { key: "event", label: "When", type: "select", options: ["created", "updated", "deleted"] }],
    summary: (c) => (c.table ? `When a ${c.table} row is ${c.event || "created"}` : "Choose a table") },
}

const TONE: Record<string, string> = {
  violet: "bg-violet-500/10 text-violet-600 dark:text-violet-400", amber: "bg-amber-500/10 text-amber-600 dark:text-amber-400",
  sky: "bg-sky-500/10 text-sky-600 dark:text-sky-400", emerald: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
  rose: "bg-rose-500/10 text-rose-600 dark:text-rose-400", slate: "bg-slate-500/10 text-slate-600 dark:text-slate-300",
}

type RunStatus = "pending" | "running" | "success" | "failed" | "skipped"
interface RunState { [id: string]: { status: RunStatus; output?: any; error?: string } }

export interface WorkflowBuilderProps {
  workflow?: Partial<Workflow>
  workflows?: Partial<Workflow>[]
  /** Step types to offer (default: all) */
  step_types?: string[]
  onSave?: (wf: Workflow) => Promise<any> | any
  onRun?: (wf: Workflow) => Promise<any> | any
  className?: string
}

const blank = (w?: Partial<Workflow>): Workflow => ({
  name: "Untitled workflow", enabled: true, trigger: { type: "manual", config: {} }, steps: [], ...w,
})

function missing(fields: FieldSpec[], config: Record<string, any>) {
  return fields.filter((f) => f.required && !String(config[f.key] ?? "").trim()).map((f) => f.label)
}

const input = "w-full rounded-lg border border-input bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"

function Fields({ fields, config, onChange }: { fields: FieldSpec[]; config: Record<string, any>; onChange: (c: Record<string, any>) => void }) {
  if (!fields.length) return <p className="text-sm text-muted-foreground">Nothing to configure.</p>
  return (
    <div className="space-y-3">
      {fields.map((f) => (
        <label key={f.key} className="block space-y-1.5">
          <span className="text-sm font-medium">{f.label}{f.required && <span className="text-red-500"> *</span>}</span>
          {f.type === "textarea" ? (
            <textarea className={cn(input, "min-h-[96px] font-mono text-[13px]")} value={config[f.key] ?? ""} placeholder={f.placeholder}
              onChange={(e) => onChange({ ...config, [f.key]: e.target.value })} />
          ) : f.type === "select" ? (
            <select className={input} value={config[f.key] ?? f.options?.[0] ?? ""} onChange={(e) => onChange({ ...config, [f.key]: e.target.value })}>
              {f.options?.map((o) => <option key={o}>{o}</option>)}
            </select>
          ) : (
            <input className={input} type={f.type === "number" ? "number" : "text"} value={config[f.key] ?? ""} placeholder={f.placeholder}
              onChange={(e) => onChange({ ...config, [f.key]: f.type === "number" ? Number(e.target.value) : e.target.value })} />
          )}
        </label>
      ))}
      <p className="text-xs text-muted-foreground">Use <code className="rounded bg-muted px-1">{"{{trigger.field}}"}</code> or a step's saved name to pass data along.</p>
    </div>
  )
}

function StatusDot({ status }: { status?: RunStatus }) {
  if (!status) return null
  const map: Record<RunStatus, [string, string]> = {
    pending: ["Circle", "text-muted-foreground"], running: ["Loader2", "animate-spin text-sky-500"],
    success: ["CheckCircle", "text-emerald-500"], failed: ["XCircle", "text-red-500"], skipped: ["Minus", "text-muted-foreground"],
  }
  return <Icon name={map[status][0]} size={16} className={map[status][1]} aria-label={status} />
}

export function WorkflowBuilder({ workflow, workflows, step_types, onSave, onRun, className }: WorkflowBuilderProps) {
  const [wf, setWf] = React.useState<Workflow>(() => blank(workflow))
  const [selected, setSelected] = React.useState<string>("trigger")
  const [adding, setAdding] = React.useState<number | null>(null)
  const [run, setRun] = React.useState<RunState | null>(null)
  const [running, setRunning] = React.useState(false)
  const types = (step_types?.length ? step_types : Object.keys(STEP_TYPES)).filter((t) => STEP_TYPES[t])

  React.useEffect(() => { if (workflow) setWf(blank(workflow)) }, [workflow?.id])

  const update = (fn: (w: Workflow) => Workflow) => { setWf(fn); setRun(null) }
  const insert = (index: number, type: string) => {
    const step: WorkflowStep = { id: uid("step"), type, config: {} }
    update((w) => ({ ...w, steps: [...w.steps.slice(0, index), step, ...w.steps.slice(index)] }))
    setSelected(step.id); setAdding(null)
  }
  const move = (i: number, d: number) => update((w) => {
    const s = [...w.steps]; const j = i + d
    if (j < 0 || j >= s.length) return w
    ;[s[i], s[j]] = [s[j], s[i]]; return { ...w, steps: s }
  })
  const remove = (id: string) => { update((w) => ({ ...w, steps: w.steps.filter((s) => s.id !== id) })); setSelected("trigger") }
  const duplicate = (i: number) => update((w) => {
    const copy = { ...w.steps[i], id: uid("step"), config: { ...w.steps[i].config } }
    return { ...w, steps: [...w.steps.slice(0, i + 1), copy, ...w.steps.slice(i + 1)] }
  })

  const triggerSpec = TRIGGERS[wf.trigger.type] || TRIGGERS.manual
  const problems = [
    ...missing(triggerSpec.fields, wf.trigger.config).map((f) => `Trigger: ${f}`),
    ...wf.steps.flatMap((s, i) => missing(STEP_TYPES[s.type]?.fields || [], s.config).map((f) => `Step ${i + 1}: ${f}`)),
  ]

  const save = async () => {
    if (problems.length) { toast.warning("Fix the highlighted steps first", { description: problems[0] }); return }
    try {
      const res = await onSave?.({ ...wf, id: wf.id || uid("wf") })
      if (res && res.success === false) throw new Error(res.error)
      toast.success("Workflow saved")
    } catch (e: any) { toast.error("Couldn't save the workflow", { description: e?.message }) }
  }

  const start = async () => {
    if (!wf.steps.length) { toast.info("Add a step first"); return }
    if (problems.length) { toast.warning("Fix the highlighted steps first", { description: problems[0] }); return }
    setRunning(true)
    const state: RunState = Object.fromEntries(wf.steps.map((s) => [s.id, { status: "pending" as RunStatus }]))
    setRun({ ...state })
    try {
      if (onRun) {
        wf.steps.forEach((s) => (state[s.id] = { status: "running" })); setRun({ ...state })
        const res = await onRun(wf)
        const results: any[] = Array.isArray(res) ? res : res?.steps || res?.data?.steps || []
        wf.steps.forEach((s, i) => {
          const r = results.find((x) => x.id === s.id) || results[i]
          state[s.id] = r ? { status: (r.status as RunStatus) || "success", output: r.output, error: r.error } : { status: "skipped" }
        })
        if (res && res.success === false) toast.error("Run failed", { description: res.error })
      } else {
        for (const s of wf.steps) {
          state[s.id] = { status: "running" }; setRun({ ...state })
          await new Promise((r) => setTimeout(r, 450))
          state[s.id] = { status: "success", output: `${STEP_TYPES[s.type].label} step completed (simulated)` }
        }
      }
      setRun({ ...state })
      const failed = Object.values(state).some((r) => r.status === "failed")
      failed ? toast.error("Workflow finished with errors") : toast.success("Workflow run complete")
    } catch (e: any) {
      toast.error("Run failed", { description: e?.message })
      wf.steps.forEach((s) => state[s.id].status === "running" && (state[s.id] = { status: "failed", error: e?.message }))
      setRun({ ...state })
    } finally { setRunning(false) }
  }

  const sel = wf.steps.find((s) => s.id === selected)
  const Connector = ({ index }: { index: number }) => (
    <div className="relative flex flex-col items-center py-1">
      <div className="h-4 w-px bg-border" />
      <div className="relative">
        <button type="button" onClick={() => setAdding(adding === index ? null : index)} aria-label="Add step here"
          className="grid h-7 w-7 place-items-center rounded-full border bg-background text-muted-foreground shadow-sm hover:border-primary hover:text-primary">
          <Icon name="Plus" size={14} />
        </button>
        {adding === index && (
          <div className="absolute left-1/2 top-9 z-20 max-h-80 w-72 -translate-x-1/2 overflow-y-auto rounded-xl border bg-popover p-2 text-popover-foreground shadow-xl">
            <p className="px-2 pb-1 pt-1 text-xs font-medium text-muted-foreground">Add a step</p>
            {types.map((t) => (
              <button key={t} type="button" onClick={() => insert(index, t)} className="flex w-full items-start gap-3 rounded-lg p-2 text-left hover:bg-accent">
                <span className={cn("grid h-8 w-8 shrink-0 place-items-center rounded-lg", TONE[STEP_TYPES[t].tone])}><Icon name={STEP_TYPES[t].icon} size={15} /></span>
                <span><span className="block text-sm font-medium">{STEP_TYPES[t].label}</span><span className="block text-xs text-muted-foreground">{STEP_TYPES[t].description}</span></span>
              </button>
            ))}
          </div>
        )}
      </div>
      <div className="h-4 w-px bg-border" />
    </div>
  )

  const node = (id: string, icon: string, tone: string, kicker: string, title: string, summary: string, bad: boolean, extra?: React.ReactNode) => (
    <div role="button" tabIndex={0} onClick={() => setSelected(id)} onKeyDown={(e) => e.key === "Enter" && setSelected(id)}
      className={cn("group w-full max-w-md cursor-pointer rounded-xl border bg-card p-3.5 text-left shadow-sm transition-shadow hover:shadow-md",
        selected === id && "ring-2 ring-primary", bad && "border-amber-500/60")}>
      <div className="flex items-start gap-3">
        <span className={cn("grid h-9 w-9 shrink-0 place-items-center rounded-lg", TONE[tone])}><Icon name={icon} size={17} /></span>
        <div className="min-w-0 flex-1">
          <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">{kicker}</p>
          <p className="truncate text-sm font-semibold">{title}</p>
          <p className={cn("truncate text-xs", bad ? "text-amber-600" : "text-muted-foreground")}>{summary}</p>
        </div>
        <StatusDot status={run?.[id]?.status} />
        {extra}
      </div>
      {run?.[id]?.output !== undefined && (
        <pre className="mt-2 max-h-24 overflow-auto rounded-md bg-muted px-2 py-1.5 text-[11px]">{typeof run[id].output === "string" ? run[id].output : JSON.stringify(run[id].output, null, 2)}</pre>
      )}
      {run?.[id]?.error && <p className="mt-2 rounded-md bg-red-500/10 px-2 py-1.5 text-xs text-red-600">{run[id].error}</p>}
    </div>
  )

  return (
    <div className={cn("overflow-hidden rounded-xl border bg-card text-card-foreground shadow-sm", className)}>
      <div className="flex flex-wrap items-center gap-3 border-b px-5 py-3.5">
        <span className="grid h-9 w-9 place-items-center rounded-lg bg-primary/10 text-primary"><Icon name="Workflow" size={18} /></span>
        <input value={wf.name} onChange={(e) => update((w) => ({ ...w, name: e.target.value }))} aria-label="Workflow name"
          className="min-w-[10rem] flex-1 rounded-md bg-transparent px-1 py-1 font-semibold outline-none hover:bg-accent focus:bg-accent" />
        {workflows && workflows.length > 0 && (
          <select aria-label="Saved workflows" className={cn(input, "w-auto")} value={wf.id || ""}
            onChange={(e) => { setWf(blank(workflows.find((x) => x.id === e.target.value))); setRun(null); setSelected("trigger") }}>
            <option value="">New workflow</option>
            {workflows.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
          </select>
        )}
        <label className="flex items-center gap-2 text-sm text-muted-foreground">
          <input type="checkbox" checked={wf.enabled} onChange={(e) => update((w) => ({ ...w, enabled: e.target.checked }))} className="h-4 w-4 accent-primary" />
          {wf.enabled ? "Enabled" : "Paused"}
        </label>
        <button type="button" onClick={start} disabled={running}
          className="inline-flex h-9 items-center gap-1.5 rounded-lg border px-3 text-sm hover:bg-accent disabled:opacity-60">
          <Icon name={running ? "Loader2" : "Play"} size={15} className={cn(running && "animate-spin")} />{running ? "Running…" : "Run"}
        </button>
        <button type="button" onClick={save} className="inline-flex h-9 items-center gap-1.5 rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground hover:bg-primary/90">
          <Icon name="Save" size={15} />Save
        </button>
      </div>

      <div className="grid min-h-[560px] lg:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="overflow-auto bg-[radial-gradient(circle,hsl(var(--border))_1px,transparent_1px)] p-6 [background-size:18px_18px]">
          <div className="flex flex-col items-center">
            {node("trigger", triggerSpec.icon, "emerald", "Trigger", triggerSpec.label, triggerSpec.summary(wf.trigger.config),
              missing(triggerSpec.fields, wf.trigger.config).length > 0)}
            <Connector index={0} />
            {wf.steps.map((s, i) => {
              const spec = STEP_TYPES[s.type]
              if (!spec) return null
              return (
                <React.Fragment key={s.id}>
                  {node(s.id, spec.icon, spec.tone, `Step ${i + 1} · ${spec.label}`, s.name || spec.label, spec.summary(s.config),
                    missing(spec.fields, s.config).length > 0,
                    <div className="flex opacity-0 transition-opacity group-hover:opacity-100" onClick={(e) => e.stopPropagation()}>
                      <button type="button" aria-label="Move up" onClick={() => move(i, -1)} className="grid h-6 w-6 place-items-center rounded hover:bg-accent"><Icon name="ArrowUp" size={13} /></button>
                      <button type="button" aria-label="Move down" onClick={() => move(i, 1)} className="grid h-6 w-6 place-items-center rounded hover:bg-accent"><Icon name="ArrowDown" size={13} /></button>
                      <button type="button" aria-label="Duplicate" onClick={() => duplicate(i)} className="grid h-6 w-6 place-items-center rounded hover:bg-accent"><Icon name="Copy" size={13} /></button>
                      <button type="button" aria-label="Delete" onClick={() => remove(s.id)} className="grid h-6 w-6 place-items-center rounded hover:bg-red-500/10 hover:text-red-600"><Icon name="Trash2" size={13} /></button>
                    </div>)}
                  <Connector index={i + 1} />
                </React.Fragment>
              )
            })}
            <div className="rounded-full border border-dashed px-4 py-1.5 text-xs text-muted-foreground">End</div>
          </div>
        </div>

        <aside className="border-t p-5 lg:border-l lg:border-t-0">
          {selected === "trigger" ? (
            <div className="space-y-4">
              <div><p className="text-sm font-semibold">Trigger</p><p className="text-xs text-muted-foreground">What starts this workflow</p></div>
              <div className="grid grid-cols-2 gap-2">
                {Object.entries(TRIGGERS).map(([k, t]) => (
                  <button key={k} type="button" onClick={() => update((w) => ({ ...w, trigger: { type: k, config: {} } }))}
                    className={cn("flex flex-col items-start gap-1.5 rounded-lg border p-2.5 text-left text-xs", wf.trigger.type === k ? "border-primary bg-primary/5" : "hover:bg-accent")}>
                    <Icon name={t.icon} size={16} />{t.label}
                  </button>
                ))}
              </div>
              <Fields fields={triggerSpec.fields} config={wf.trigger.config} onChange={(c) => update((w) => ({ ...w, trigger: { ...w.trigger, config: c } }))} />
            </div>
          ) : sel ? (
            <div className="space-y-4">
              <div className="flex items-center gap-3">
                <span className={cn("grid h-9 w-9 place-items-center rounded-lg", TONE[STEP_TYPES[sel.type].tone])}><Icon name={STEP_TYPES[sel.type].icon} size={17} /></span>
                <div><p className="text-sm font-semibold">{STEP_TYPES[sel.type].label}</p><p className="text-xs text-muted-foreground">{STEP_TYPES[sel.type].description}</p></div>
              </div>
              <label className="block space-y-1.5"><span className="text-sm font-medium">Step name</span>
                <input className={input} value={sel.name ?? ""} placeholder={STEP_TYPES[sel.type].label}
                  onChange={(e) => update((w) => ({ ...w, steps: w.steps.map((s) => (s.id === sel.id ? { ...s, name: e.target.value } : s)) }))} /></label>
              <Fields fields={STEP_TYPES[sel.type].fields} config={sel.config}
                onChange={(c) => update((w) => ({ ...w, steps: w.steps.map((s) => (s.id === sel.id ? { ...s, config: c } : s)) }))} />
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">Select a step to configure it.</p>
          )}
          {problems.length > 0 && (
            <div className="mt-6 rounded-lg border border-amber-500/40 bg-amber-500/5 p-3 text-xs">
              <p className="mb-1 font-medium text-amber-700 dark:text-amber-400">Needs attention</p>
              <ul className="list-disc space-y-0.5 pl-4 text-muted-foreground">{problems.slice(0, 5).map((p) => <li key={p}>{p}</li>)}</ul>
            </div>
          )}
        </aside>
      </div>
    </div>
  )
}
