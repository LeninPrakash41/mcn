import React, { useState, useCallback } from "react"
import { api } from "../services/api"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { TrendingUp } from "lucide-react"

export function PromptTester() {
  const [template_text, setTemplateText] = useState("Cinematic shot of {{subject}}, volumetric rim lighting, 8k resolution, shot on 35mm lens, f/1.8, photorealistic textures --ar 16:9")
  const [subject, setSubject] = useState("Cyberpunk Samurai in Neon Rain")
  const [language, setLanguage] = useState("TypeScript")
  const [audience, setAudience] = useState("Founders and Engineers")
  const [test_output, setTestOutput] = useState("")
  const [interpolated_prompt, setInterpolatedPrompt] = useState("")
  const [loading, setLoading] = useState(false)
  const [tokens_count, setTokensCount] = useState(0)
  const [latency, setLatency] = useState(0)

  const submit = useCallback(async (e?: React.FormEvent) => {
    if (e) e.preventDefault()
    setLoading(true)
    const res = await api.post('/test_prompt_live', {template_text: template_text, subject: subject, language: language, audience: audience})
    if (res.success) {
      setTestOutput(res.result)
      setInterpolatedPrompt(res.interpolated_prompt)
      setTokensCount(res.tokens_used)
      setLatency(res.latency_ms)
    }
    setLoading(false)
  }, [template_text, subject, language, audience, test_output, interpolated_prompt, loading, tokens_count, latency])

  return (
    <div >
      <Card >
        <CardHeader>
          <h2 className="text-xl font-semibold">{"Live Prompt Playground & Variable Interpolator"}</h2>
        </CardHeader>
        <CardContent className="pt-6">
          <form onSubmit={submit} className="space-y-4">
            <div className="space-y-1">
              <Label>{"Prompt Template (Supports {{variables}})"}</Label>
              <Textarea value={template_text} onChange={(e) => setTemplateText(e.target.value)} />
            </div>
            <div className="grid grid-cols-3 gap-4">
              <div className="space-y-1">
                <Label htmlFor="subject">{"Variable: {{subject}} or {{topic}}"}</Label>
                <Input value={subject} onChange={(e) => setSubject(e.target.value)} />
              </div>
              <div className="space-y-1">
                <Label htmlFor="language">{"Variable: {{language}} or {{framework}}"}</Label>
                <Input value={language} onChange={(e) => setLanguage(e.target.value)} />
              </div>
              <div className="space-y-1">
                <Label htmlFor="audience">{"Variable: {{audience}} or {{target}}"}</Label>
                <Input value={audience} onChange={(e) => setAudience(e.target.value)} />
              </div>
            </div>
            <Button variant="default" disabled={loading}>{"Execute Prompt with AI Simulator"}</Button>
          </form>
        </CardContent>
      </Card>
      <Card >
        <CardHeader>
          <h2 className="text-xl font-semibold">{"Execution Result & Interpolated Output"}</h2>
        </CardHeader>
        <CardContent className="pt-6">
          <div className="grid grid-cols-2 gap-4">
            <Card>
              <CardContent className="p-5">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-muted-foreground">{"Simulated Tokens"}</p>
                    <p className="text-2xl font-bold mt-1">{tokens_count}<span className="text-sm font-normal ml-1 text-muted-foreground">{"tok"}</span></p>
                    
                  </div>
                  <div className="p-2 rounded-lg text-primary bg-primary/10">
                    <TrendingUp className="w-5 h-5" />
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-5">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-muted-foreground">{"Latency"}</p>
                    <p className="text-2xl font-bold mt-1">{latency}<span className="text-sm font-normal ml-1 text-muted-foreground">{"ms"}</span></p>
                    
                  </div>
                  <div className="p-2 rounded-lg text-primary bg-primary/10">
                    <TrendingUp className="w-5 h-5" />
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </CardContent>
        <CardContent >
          <div >
            <span>{test_output}</span>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

export default PromptTester
