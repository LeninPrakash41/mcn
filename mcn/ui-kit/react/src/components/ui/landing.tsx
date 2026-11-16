import * as React from "react"
import { Icon } from "./icon"
import { Toaster } from "./toast"
import { appMode, cn } from "@/lib/utils"

/* Landing-page sections: navbar, hero, features, pricing, testimonials, logos,
   FAQ, call to action and footer. They read the app's colors (`brand` in the
   app block), so a whole page follows one brand color in light and dark mode. */

type Action = (() => unknown) | undefined
type Text = React.ReactNode

export const slug = (s: unknown) =>
  String(s ?? "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "")

/** Follow a link: "#pricing" scrolls to that section, anything else opens it. */
export function follow(link?: string) {
  if (!link) return
  if (link.startsWith("#")) {
    document.getElementById(link.slice(1))?.scrollIntoView({ behavior: "smooth", block: "start" })
    return
  }
  window.location.href = link
}

function act(handler: Action, link?: string) {
  return handler || link ? () => (handler ? handler() : follow(link)) : undefined
}

const gradient = {
  background:
    "radial-gradient(1200px 500px at 15% -10%, hsl(var(--primary) / 0.22), transparent 60%)," +
    "radial-gradient(900px 500px at 100% 0%, hsl(var(--primary) / 0.14), transparent 55%)",
}

function Cta({ children, onClick, variant = "primary", size = "lg", className }: {
  children: Text; onClick?: () => unknown; variant?: "primary" | "outline" | "light" | "ghost"; size?: "md" | "lg"; className?: string
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-full font-semibold transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
        size === "lg" ? "h-12 px-6 text-[15px]" : "h-10 px-5 text-sm",
        variant === "primary" && "bg-primary text-primary-foreground shadow-lg shadow-primary/25 hover:-translate-y-0.5 hover:shadow-xl hover:shadow-primary/30",
        variant === "outline" && "border border-border bg-background/70 backdrop-blur hover:bg-accent",
        variant === "light" && "bg-white text-slate-900 shadow-lg hover:-translate-y-0.5",
        variant === "ghost" && "text-white/90 ring-1 ring-white/30 hover:bg-white/10",
        className,
      )}
    >
      {children}
    </button>
  )
}

function SectionHead({ eyebrow, title, subtitle, center = true }: { eyebrow?: Text; title?: Text; subtitle?: Text; center?: boolean }) {
  if (!title && !subtitle && !eyebrow) return null
  return (
    <div className={cn("mb-10 max-w-2xl", center && "mx-auto text-center")}>
      {eyebrow ? <p className="mb-3 text-sm font-semibold uppercase tracking-wider text-primary">{eyebrow}</p> : null}
      {title ? <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">{title}</h2> : null}
      {subtitle ? <p className="mt-4 text-lg leading-relaxed text-muted-foreground">{subtitle}</p> : null}
    </div>
  )
}

function Section({ id, children, className, tint }: { id?: string; children: React.ReactNode; className?: string; tint?: boolean }) {
  return (
    <section id={id} className={cn("scroll-mt-20 px-5 py-20 sm:px-8 sm:py-24", tint && "bg-muted/40", className)}>
      <div className="mx-auto max-w-6xl">{children}</div>
    </section>
  )
}

/** True inside a `page` layout, where sections run edge to edge. */
const SiteContext = React.createContext(false)

/** A whole page without the app frame: sections stack edge to edge. */
export function SitePage({ children }: { children?: React.ReactNode }) {
  React.useEffect(() => {
    const mode = appMode()
    const dark = mode === "dark" || (mode === "auto" && typeof matchMedia !== "undefined" && matchMedia("(prefers-color-scheme: dark)").matches)
    document.documentElement.classList.toggle("dark", dark)
  }, [])
  return (
    <SiteContext.Provider value={true}>
      <div className="min-h-screen bg-background text-foreground antialiased">
        {children}
        <Toaster />
      </div>
    </SiteContext.Provider>
  )
}

export interface NavbarProps {
  title?: Text
  logo?: string
  links?: string[]
  cta?: Text
  onCta?: Action
  ctaLink?: string
}

/** A sticky top bar: brand, links that scroll to sections, and a call to action. */
export function Navbar({ title, logo = "Sparkles", links = [], cta, onCta, ctaLink }: NavbarProps) {
  const [open, setOpen] = React.useState(false)
  const linkTo = (l: string) => (l.startsWith("#") || l.includes("/") ? l : "#" + slug(l))
  const label = (l: string) => l.replace(/^#/, "")
  return (
    <header className="sticky top-0 z-40 border-b border-border/60 bg-background/75 backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-6xl items-center gap-6 px-5 sm:px-8">
        <a href="#" className="flex items-center gap-2.5 font-bold tracking-tight" onClick={(e) => { e.preventDefault(); window.scrollTo({ top: 0, behavior: "smooth" }) }}>
          <span className="grid h-8 w-8 place-items-center rounded-lg bg-primary text-primary-foreground shadow-sm shadow-primary/30">
            <Icon name={logo} size={17} />
          </span>
          <span className="text-[17px]">{title}</span>
        </a>
        <nav className="hidden flex-1 items-center gap-1 md:flex">
          {links.map((l) => (
            <button key={l} type="button" onClick={() => follow(linkTo(l))}
              className="rounded-full px-3.5 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-foreground">
              {label(l)}
            </button>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-2">
          {cta ? <Cta size="md" onClick={act(onCta, ctaLink)} className="hidden sm:inline-flex">{cta}</Cta> : null}
          {links.length ? (
            <button type="button" aria-label="Menu" onClick={() => setOpen(!open)} className="grid h-10 w-10 place-items-center rounded-full hover:bg-accent md:hidden">
              <Icon name={open ? "X" : "Menu"} size={20} />
            </button>
          ) : null}
        </div>
      </div>
      {open ? (
        <div className="border-t border-border/60 px-5 py-3 md:hidden">
          {links.map((l) => (
            <button key={l} type="button" onClick={() => { setOpen(false); follow(linkTo(l)) }}
              className="block w-full rounded-lg px-3 py-2.5 text-left font-medium hover:bg-accent">{label(l)}</button>
          ))}
          {cta ? <Cta size="md" onClick={act(onCta, ctaLink)} className="mt-2 w-full">{cta}</Cta> : null}
        </div>
      ) : null}
    </header>
  )
}

export interface HeroProps {
  title?: Text
  eyebrow?: Text
  subtitle?: Text
  primary?: Text
  secondary?: Text
  onPrimary?: Action
  onSecondary?: Action
  primaryLink?: string
  secondaryLink?: string
  image?: string
  note?: Text
  /** "gradient" (default), "dark" or "plain" */
  variant?: string
  id?: string
  children?: React.ReactNode
}

/** The opening section: a big headline, a line about the product, two calls to
 *  action, and an image (or any elements nested under it) beside or below. */
export function Hero({ title, eyebrow, subtitle, primary, secondary, onPrimary, onSecondary, primaryLink, secondaryLink,
  image, note, variant = "gradient", id, children }: HeroProps) {
  const dark = variant === "dark"
  const side = Boolean(image || children)
  // Inside an app screen the hero is a rounded banner; on a page it runs edge to edge
  const inApp = !React.useContext(SiteContext)
  return (
    <section id={id} className={cn("relative overflow-hidden px-5 sm:px-8", dark ? "bg-slate-950 text-white" : "bg-background",
      inApp && "rounded-3xl border border-border/60 sm:px-10")}
      style={variant === "plain" ? undefined : dark ? { background: "radial-gradient(900px 500px at 20% 0%, hsl(var(--primary) / 0.45), transparent 60%), #020617" }
        : inApp ? { background: "radial-gradient(700px 260px at 0% 0%, hsl(var(--primary) / 0.22), transparent 70%), linear-gradient(120deg, hsl(var(--primary) / 0.10), hsl(var(--primary) / 0.02))" } : gradient}>
      <div className={cn("mx-auto grid max-w-6xl items-center gap-12", inApp ? "gap-8 py-8 sm:py-10" : "py-20 sm:py-28", side ? "lg:grid-cols-[1.1fr_1fr]" : !inApp && "text-center")}>
        <div className={cn(!side && !inApp && "mx-auto max-w-3xl")}>
          {eyebrow ? (
            <span className={cn("mb-6 inline-flex items-center gap-2 rounded-full px-3.5 py-1.5 text-sm font-medium ring-1",
              dark ? "bg-white/10 text-white ring-white/20" : "bg-primary/10 text-primary ring-primary/20")}>
              <span className="h-1.5 w-1.5 rounded-full bg-current" />{eyebrow}
            </span>
          ) : null}
          <h1 className={cn("font-extrabold leading-[1.05] tracking-tight", inApp ? "text-3xl sm:text-4xl" : "text-4xl sm:text-6xl")}>{title}</h1>
          {subtitle ? <p className={cn(inApp ? "mt-3 text-base leading-relaxed" : "mt-6 text-lg leading-relaxed sm:text-xl", dark ? "text-slate-300" : "text-muted-foreground", !side && !inApp && "mx-auto max-w-2xl", inApp && "max-w-2xl")}>{subtitle}</p> : null}
          {primary || secondary ? (
            <div className={cn(inApp ? "mt-6" : "mt-9", "flex flex-wrap gap-3", !side && !inApp && "justify-center")}>
              {primary ? <Cta variant={dark ? "light" : "primary"} onClick={act(onPrimary, primaryLink)}>{primary}<Icon name="ArrowRight" size={17} /></Cta> : null}
              {secondary ? <Cta variant={dark ? "ghost" : "outline"} onClick={act(onSecondary, secondaryLink)}>{secondary}</Cta> : null}
            </div>
          ) : null}
          {note ? <p className={cn("mt-5 text-sm", dark ? "text-slate-400" : "text-muted-foreground")}>{note}</p> : null}
        </div>
        {side ? (
          <div className="relative">
            <div className="absolute -inset-6 -z-0 rounded-[2rem] bg-primary/20 blur-3xl" aria-hidden="true" />
            {image ? (
              <img src={image} alt="" className="relative w-full rounded-3xl border border-border/60 object-cover shadow-2xl" />
            ) : (
              <div className={cn("relative space-y-4", dark && "[&_.text-muted-foreground]:text-slate-300")}>{children}</div>
            )}
          </div>
        ) : null}
      </div>
    </section>
  )
}

export function FeatureGrid({ title, subtitle, eyebrow, columns = 3, id, children }: {
  title?: Text; subtitle?: Text; eyebrow?: Text; columns?: number; id?: string; children?: React.ReactNode
}) {
  const cols = Number(columns) >= 4 ? "lg:grid-cols-4" : Number(columns) === 2 ? "" : "lg:grid-cols-3"
  return (
    <Section id={id}>
      <SectionHead eyebrow={eyebrow} title={title} subtitle={subtitle} />
      <div className={cn("grid gap-5 sm:grid-cols-2", cols)}>{children}</div>
    </Section>
  )
}

export function Feature({ title, description, icon = "Sparkles", children }: { title?: Text; description?: Text; icon?: string; children?: React.ReactNode }) {
  return (
    <div className="group relative rounded-2xl border border-border/70 bg-card p-6 transition-all hover:-translate-y-1 hover:border-primary/40 hover:shadow-xl hover:shadow-primary/5">
      <span className="mb-5 grid h-11 w-11 place-items-center rounded-xl bg-primary/10 text-primary ring-1 ring-primary/15 transition-colors group-hover:bg-primary group-hover:text-primary-foreground">
        <Icon name={icon} size={21} />
      </span>
      <h3 className="text-lg font-semibold tracking-tight">{title}</h3>
      {description ? <p className="mt-2 leading-relaxed text-muted-foreground">{description}</p> : null}
      {children}
    </div>
  )
}

export function Pricing({ title, subtitle, eyebrow, id, children }: { title?: Text; subtitle?: Text; eyebrow?: Text; id?: string; children?: React.ReactNode }) {
  return (
    <Section id={id} tint>
      <SectionHead eyebrow={eyebrow} title={title} subtitle={subtitle} />
      <div className="mx-auto grid max-w-5xl items-stretch gap-6 md:grid-cols-3">{children}</div>
    </Section>
  )
}

export interface PlanProps {
  title?: Text
  price?: Text
  period?: Text
  description?: Text
  features?: Text[]
  cta?: Text
  onClick?: Action
  link?: string
  highlight?: boolean
  badge?: Text
}

export function Plan({ title, price, period, description, features = [], cta = "Get started", onClick, link, highlight, badge }: PlanProps) {
  return (
    <div className={cn("relative flex flex-col rounded-3xl border bg-card p-7",
      highlight ? "border-primary shadow-2xl shadow-primary/15 ring-1 ring-primary md:-my-3 md:py-10" : "border-border/70")}>
      {highlight ? (
        <span className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-primary px-3 py-1 text-xs font-semibold text-primary-foreground shadow">
          {badge || "Most popular"}
        </span>
      ) : null}
      <h3 className="text-lg font-semibold">{title}</h3>
      {description ? <p className="mt-1.5 text-sm text-muted-foreground">{description}</p> : null}
      <p className="mt-6 flex items-baseline gap-1">
        <span className="text-4xl font-extrabold tracking-tight">{price}</span>
        {period ? <span className="text-muted-foreground">{period}</span> : null}
      </p>
      <ul className="mt-6 flex-1 space-y-3">
        {features.map((f, i) => (
          <li key={i} className="flex gap-3 text-[15px]">
            <span className="mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full bg-primary/10 text-primary"><Icon name="Check" size={13} strokeWidth={3} /></span>
            <span>{f}</span>
          </li>
        ))}
      </ul>
      <Cta size="md" variant={highlight ? "primary" : "outline"} onClick={act(onClick, link)} className="mt-8 w-full">{cta}</Cta>
    </div>
  )
}

export function Testimonials({ title, subtitle, eyebrow, id, children }: { title?: Text; subtitle?: Text; eyebrow?: Text; id?: string; children?: React.ReactNode }) {
  return (
    <Section id={id}>
      <SectionHead eyebrow={eyebrow} title={title} subtitle={subtitle} />
      <div className="grid gap-5 md:grid-cols-3">{children}</div>
    </Section>
  )
}

export function initials(name: unknown) {
  return String(name ?? "?").split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]?.toUpperCase()).join("") || "?"
}

export function Testimonial({ title, author, role, avatar, rating = 5 }: { title?: Text; author?: Text; role?: Text; avatar?: string; rating?: number }) {
  return (
    <figure className="flex flex-col rounded-2xl border border-border/70 bg-card p-6 shadow-sm">
      <div className="mb-4 flex gap-0.5 text-amber-400">
        {Array.from({ length: Math.max(0, Math.min(5, Number(rating) || 0)) }).map((_, i) => <Icon key={i} name="Star" size={16} fill="currentColor" />)}
      </div>
      <blockquote className="flex-1 text-[15px] leading-relaxed">“{title}”</blockquote>
      <figcaption className="mt-6 flex items-center gap-3">
        {avatar ? <img src={avatar} alt="" className="h-10 w-10 rounded-full object-cover" />
          : <span className="grid h-10 w-10 place-items-center rounded-full bg-primary/10 text-sm font-semibold text-primary">{initials(author)}</span>}
        <span>
          <span className="block text-sm font-semibold">{author}</span>
          {role ? <span className="block text-sm text-muted-foreground">{role}</span> : null}
        </span>
      </figcaption>
    </figure>
  )
}

export function LogoCloud({ title, names = [] }: { title?: Text; names?: Text[] }) {
  return (
    <section className="px-5 py-12 sm:px-8">
      <div className="mx-auto max-w-6xl text-center">
        {title ? <p className="text-sm font-medium text-muted-foreground">{title}</p> : null}
        <div className="mt-6 flex flex-wrap items-center justify-center gap-x-12 gap-y-5">
          {names.map((n, i) => <span key={i} className="text-xl font-bold tracking-tight text-muted-foreground/70">{n}</span>)}
        </div>
      </div>
    </section>
  )
}

export function Faq({ title, subtitle, eyebrow, id, children }: { title?: Text; subtitle?: Text; eyebrow?: Text; id?: string; children?: React.ReactNode }) {
  return (
    <Section id={id}>
      <SectionHead eyebrow={eyebrow} title={title} subtitle={subtitle} />
      <div className="mx-auto max-w-3xl divide-y divide-border rounded-2xl border border-border/70 bg-card">{children}</div>
    </Section>
  )
}

export function Question({ title, answer, children }: { title?: Text; answer?: Text; children?: React.ReactNode }) {
  const [open, setOpen] = React.useState(false)
  return (
    <div>
      <button type="button" aria-expanded={open} onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between gap-4 px-6 py-5 text-left font-semibold">
        <span>{title}</span>
        <span className={cn("grid h-7 w-7 shrink-0 place-items-center rounded-full bg-muted transition-transform", open && "rotate-45")}><Icon name="Plus" size={15} /></span>
      </button>
      {open ? <div className="-mt-1 px-6 pb-5 leading-relaxed text-muted-foreground">{answer}{children}</div> : null}
    </div>
  )
}

export function CtaBand({ title, subtitle, cta, onClick, link, secondary, onSecondary, secondaryLink, id, children }: {
  title?: Text; subtitle?: Text; cta?: Text; onClick?: Action; link?: string; secondary?: Text; onSecondary?: Action; secondaryLink?: string
  id?: string; children?: React.ReactNode
}) {
  return (
    <section id={id} className="scroll-mt-20 px-5 py-16 sm:px-8">
      <div className="relative mx-auto max-w-6xl overflow-hidden rounded-[2rem] px-6 py-16 text-center text-white sm:px-12"
        style={{ background: "radial-gradient(700px 300px at 85% 0%, rgba(255,255,255,0.22), transparent 60%), linear-gradient(135deg, hsl(var(--primary)), hsl(var(--primary) / 0.75))" }}>
        <h2 className="mx-auto max-w-2xl text-3xl font-bold tracking-tight sm:text-4xl">{title}</h2>
        {subtitle ? <p className="mx-auto mt-4 max-w-xl text-lg text-white/85">{subtitle}</p> : null}
        {cta || secondary ? (
          <div className="mt-8 flex flex-wrap justify-center gap-3">
            {cta ? <Cta variant="light" onClick={act(onClick, link)}>{cta}</Cta> : null}
            {secondary ? <Cta variant="ghost" onClick={act(onSecondary, secondaryLink)}>{secondary}</Cta> : null}
          </div>
        ) : null}
        {children ? <div className="mx-auto mt-8 max-w-md rounded-2xl bg-background p-6 text-left text-foreground shadow-2xl">{children}</div> : null}
      </div>
    </section>
  )
}

export function SiteFooter({ title, logo = "Sparkles", text, links = [] }: { title?: Text; logo?: string; text?: Text; links?: string[] }) {
  const linkTo = (l: string) => (l.startsWith("#") || l.includes("/") ? l : "#" + slug(l))
  return (
    <footer className="border-t border-border/70 px-5 py-10 sm:px-8">
      <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-6 sm:flex-row">
        <div className="flex items-center gap-2.5 font-bold">
          <span className="grid h-7 w-7 place-items-center rounded-lg bg-primary text-primary-foreground"><Icon name={logo} size={15} /></span>
          {title}
        </div>
        {links.length ? (
          <nav className="flex flex-wrap justify-center gap-x-6 gap-y-2 text-sm text-muted-foreground">
            {links.map((l) => <button key={l} type="button" onClick={() => follow(linkTo(l))} className="hover:text-foreground">{l.replace(/^#/, "")}</button>)}
          </nav>
        ) : null}
        {text ? <p className="text-sm text-muted-foreground">{text}</p> : null}
      </div>
    </footer>
  )
}
