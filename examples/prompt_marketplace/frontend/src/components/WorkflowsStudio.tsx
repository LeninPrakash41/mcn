import React, { useState, useEffect, useCallback } from "react"
import { api } from "../services/api"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

export function WorkflowsStudio() {
  const [workflows, setWorkflows] = useState([])
  const [selected_workflow, setSelectedWorkflow] = useState("End-to-End SEO Content Pipeline")
  const [topic, setTopic] = useState("Autonomous Agents in Financial Services")
  const [stage1, setStage1] = useState("")
  const [stage2, setStage2] = useState("")
  const [stage3, setStage3] = useState("")
  const [running, setRunning] = useState(false)

  useEffect(() => {
    ;(async () => {
      const res = await api.post('/list_workflows', {})
      setWorkflows(res.data)
    })()
  }, [])
  const submit = useCallback(async (e?: React.FormEvent) => {
    if (e) e.preventDefault()
    setRunning(true)
    const res = await api.post('/run_multi_stage_workflow', {selected_workflow: selected_workflow, topic: topic})
    if (res.success) {
      setStage1("".output)
      setStage2("".output)
      setStage3("".output)
    }
    setRunning(false)
  }, [workflows, selected_workflow, topic, stage1, stage2, stage3, running])

  return (
    <div >
      <Card >
        <CardHeader>
          <h2 className="text-xl font-semibold">{"Multi-Step AI Workflow Orchestrator"}</h2>
        </CardHeader>
        <CardContent className="pt-6">
          <form onSubmit={submit} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1">
                <Label htmlFor="selected_workflow">{"Workflow Pipeline"}</Label>
                <Input value={selected_workflow} onChange={(e) => setSelectedWorkflow(e.target.value)} />
              </div>
              <div className="space-y-1">
                <Label htmlFor="topic">{"Workflow Execution Subject / Topic"}</Label>
                <Input value={topic} onChange={(e) => setTopic(e.target.value)} />
              </div>
            </div>
            <Button variant="default" disabled={running}>{"Run Multi-Stage Workflow"}</Button>
          </form>
        </CardContent>
      </Card>
      <div className="grid grid-cols-3 gap-4">
        <Card >
          <CardHeader>
            <h2 className="text-xl font-semibold">{"Stage 1: Intent & Market Intelligence"}</h2>
          </CardHeader>
          <CardContent className="pt-6">
            <span>{stage1}</span>
          </CardContent>
        </Card>
        <Card >
          <CardHeader>
            <h2 className="text-xl font-semibold">{"Stage 2: Architecture & Content Framework"}</h2>
          </CardHeader>
          <CardContent className="pt-6">
            <span>{stage2}</span>
          </CardContent>
        </Card>
        <Card >
          <CardHeader>
            <h2 className="text-xl font-semibold">{"Stage 3: Final Delivery & Executive Score"}</h2>
          </CardHeader>
          <CardContent className="pt-6">
            <span>{stage3}</span>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

export default WorkflowsStudio
