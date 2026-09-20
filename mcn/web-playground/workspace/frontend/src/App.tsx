import React from "react"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"
import { AnalyticsDashboard } from "./components/AnalyticsDashboard"
import "./globals.css"

export default function App() {
  return (
    <div className="min-h-screen bg-background p-6">
      <h1 className="text-2xl font-bold mb-6">Executive Analytics & BI Hub</h1>
      <Tabs defaultValue="Executive Overview" className="w-full">
        <TabsList>
          <TabsTrigger value="Executive Overview">Executive Overview</TabsTrigger>
        </TabsList>
        <TabsContent value="Executive Overview">
          <AnalyticsDashboard />
        </TabsContent>
      </Tabs>
    </div>
  )
}
