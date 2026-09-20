import React, { useState } from "react"
import { ChevronRight, Circle, LogOut, Menu, X } from "lucide-react"
import { MarketplaceCatalog } from "./components/MarketplaceCatalog"
import { PromptTester } from "./components/PromptTester"
import { WorkflowsStudio } from "./components/WorkflowsStudio"
import { PublishStudio } from "./components/PublishStudio"
import { CreatorAnalytics } from "./components/CreatorAnalytics"
import "./globals.css"

export default function App() {
  const [active, setActive] = useState("Marketplace")
  const [mobileOpen, setMobileOpen] = useState(false)

  return (
    <div className="flex min-h-screen bg-background">
      {/* Sidebar for Desktop */}
      <aside className="hidden md:flex md:w-64 border-r bg-card flex flex-col shadow-sm">
        {/* Header */}
        <div className="flex items-center gap-3 px-4 py-4 border-b">
          <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center">
            <Circle className="w-4 h-4 text-primary-foreground" />
          </div>
          <div>
            <h2 className="text-sm font-bold leading-tight">PromptVerse — AI Prompt & Workflow Marketplace</h2>
            <p className="text-xs text-muted-foreground">Workspace</p>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 p-3 space-y-0.5 overflow-y-auto">
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider px-3 py-2 mt-1">Navigation</p>
          <button
            onClick={() => setActive("Marketplace")}
            className={`flex items-center gap-3 w-full px-3 py-2 rounded-lg text-sm font-medium transition-colors ${active === "Marketplace" ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-accent hover:text-foreground"}`}
          >
            <Circle className="w-4 h-4 shrink-0" />
            Marketplace
          </button>
          <button
            onClick={() => setActive("Prompt Playground")}
            className={`flex items-center gap-3 w-full px-3 py-2 rounded-lg text-sm font-medium transition-colors ${active === "Prompt Playground" ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-accent hover:text-foreground"}`}
          >
            <Circle className="w-4 h-4 shrink-0" />
            Prompt Playground
          </button>
          <button
            onClick={() => setActive("Workflow Pipelines")}
            className={`flex items-center gap-3 w-full px-3 py-2 rounded-lg text-sm font-medium transition-colors ${active === "Workflow Pipelines" ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-accent hover:text-foreground"}`}
          >
            <Circle className="w-4 h-4 shrink-0" />
            Workflow Pipelines
          </button>
          <button
            onClick={() => setActive("Publish Prompt")}
            className={`flex items-center gap-3 w-full px-3 py-2 rounded-lg text-sm font-medium transition-colors ${active === "Publish Prompt" ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-accent hover:text-foreground"}`}
          >
            <Circle className="w-4 h-4 shrink-0" />
            Publish Prompt
          </button>
          <button
            onClick={() => setActive("Creator Analytics")}
            className={`flex items-center gap-3 w-full px-3 py-2 rounded-lg text-sm font-medium transition-colors ${active === "Creator Analytics" ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-accent hover:text-foreground"}`}
          >
            <Circle className="w-4 h-4 shrink-0" />
            Creator Analytics
          </button>
        </nav>

        {/* User footer */}
        <div className="border-t p-3">
          <div className="flex items-center gap-3 px-2 py-2 rounded-lg hover:bg-accent cursor-pointer group">
            <div className="w-7 h-7 rounded-full bg-primary/20 flex items-center justify-center text-xs font-semibold text-primary">
              U
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium truncate">User</p>
              <p className="text-xs text-muted-foreground truncate">user@example.com</p>
            </div>
            <ChevronRight className="w-3 h-3 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
          </div>
        </div>
      </aside>

      {/* Main Layout container (Desktop vs Mobile handling) */}
      <div className="flex-1 flex flex-col min-h-screen overflow-hidden">
        {/* Mobile Top Navbar */}
        <header className="flex md:hidden items-center justify-between px-4 py-3 border-b bg-card shadow-sm w-full">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center">
              <Circle className="w-4 h-4 text-primary-foreground" />
            </div>
            <span className="text-sm font-bold">PromptVerse — AI Prompt & Workflow Marketplace</span>
          </div>
          <button 
            onClick={() => setMobileOpen(!mobileOpen)}
            className="p-1 rounded-md hover:bg-accent text-muted-foreground hover:text-foreground"
          >
            {mobileOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
          </button>
        </header>

        {/* Mobile Menu Overlay / Drawer */}
        {mobileOpen && (
          <div className="fixed inset-0 z-50 flex bg-background/80 backdrop-blur-sm md:hidden">
            <div className="relative w-64 max-w-xs bg-card border-r flex flex-col p-4 shadow-xl">
              <div className="flex items-center justify-between mb-6 pb-4 border-b">
                <span className="text-sm font-bold">PromptVerse — AI Prompt & Workflow Marketplace</span>
                <button onClick={() => setMobileOpen(false)} className="p-1 text-muted-foreground hover:text-foreground">
                  <X className="w-5 h-5" />
                </button>
              </div>
              <nav className="flex-1 space-y-1">
                <button
                  onClick={() => { setActive("Marketplace"); setMobileOpen(false); }}
                  className={`flex items-center gap-3 w-full px-3 py-2 rounded-lg text-sm font-medium transition-colors ${active === "Marketplace" ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-accent hover:text-foreground"}`}
                >
                  <Circle className="w-4 h-4 shrink-0" />
                  Marketplace
                </button>
                <button
                  onClick={() => { setActive("Prompt Playground"); setMobileOpen(false); }}
                  className={`flex items-center gap-3 w-full px-3 py-2 rounded-lg text-sm font-medium transition-colors ${active === "Prompt Playground" ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-accent hover:text-foreground"}`}
                >
                  <Circle className="w-4 h-4 shrink-0" />
                  Prompt Playground
                </button>
                <button
                  onClick={() => { setActive("Workflow Pipelines"); setMobileOpen(false); }}
                  className={`flex items-center gap-3 w-full px-3 py-2 rounded-lg text-sm font-medium transition-colors ${active === "Workflow Pipelines" ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-accent hover:text-foreground"}`}
                >
                  <Circle className="w-4 h-4 shrink-0" />
                  Workflow Pipelines
                </button>
                <button
                  onClick={() => { setActive("Publish Prompt"); setMobileOpen(false); }}
                  className={`flex items-center gap-3 w-full px-3 py-2 rounded-lg text-sm font-medium transition-colors ${active === "Publish Prompt" ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-accent hover:text-foreground"}`}
                >
                  <Circle className="w-4 h-4 shrink-0" />
                  Publish Prompt
                </button>
                <button
                  onClick={() => { setActive("Creator Analytics"); setMobileOpen(false); }}
                  className={`flex items-center gap-3 w-full px-3 py-2 rounded-lg text-sm font-medium transition-colors ${active === "Creator Analytics" ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-accent hover:text-foreground"}`}
                >
                  <Circle className="w-4 h-4 shrink-0" />
                  Creator Analytics
                </button>
              </nav>
              <div className="border-t pt-4">
                <div className="flex items-center gap-3">
                  <div className="w-7 h-7 rounded-full bg-primary/20 flex items-center justify-center text-xs font-semibold text-primary">U</div>
                  <div>
                    <p className="text-xs font-medium">User</p>
                    <p className="text-xs text-muted-foreground">user@example.com</p>
                  </div>
                </div>
              </div>
            </div>
            {/* Click outside to close */}
            <div className="flex-1" onClick={() => setMobileOpen(false)}></div>
          </div>
        )}

        {/* Main Content Area */}
        <main className="flex-1 overflow-auto p-4 md:p-6 bg-background">
      {active === "Marketplace" && <MarketplaceCatalog />}
      {active === "Prompt Playground" && <PromptTester />}
      {active === "Workflow Pipelines" && <WorkflowsStudio />}
      {active === "Publish Prompt" && <PublishStudio />}
      {active === "Creator Analytics" && <CreatorAnalytics />}
        </main>
      </div>
    </div>
  )
}
