# @mcn/ui — MCN Studio Component Library

Modern, accessible, customizable UI components for building MCN-powered web applications, inspired by 21st.dev and shadcn/ui.

## Features
- 🎨 **Design Tokens**: Matches MCN studio theme (Light, Dark, and System mode).
- 🧩 **25+ Essential Components**: Button, Input, Modal, Toast, Tabs, Data Table, Sidebar, AIPrompt, Code / OutputLog, and more.
- ⚡ **Tailwind CSS + Radix UI**: High performance, fully accessible keyboard navigation, WAI-ARIA compliant.
- 🤖 **AI Primitives**: Built-in `AIPrompt`, `StreamingText`, and `useMCN` hooks for seamless connection to MCN scripts.

## Installation

```bash
npm install @mcn/ui
# or copy-paste directly into your project
```

## Quick Start

```tsx
import React, { useState } from 'react'
import { Button, Input, Card, AIPrompt, StreamingText, useMCN } from '@mcn/ui'

export function App() {
  const { execute, generate, isStreaming } = useMCN()
  const [output, setOutput] = useState('')

  return (
    <div className="p-8 max-w-2xl mx-auto space-y-6">
      <Card title="MCN AI Assistant" description="Execute natural language commands">
        <AIPrompt
          isStreaming={isStreaming}
          onSubmit={(prompt) => {
            setOutput('')
            generate(prompt, (chunk) => setOutput((prev) => prev + chunk))
          }}
        />
        {output && (
          <div className="mt-4 p-4 bg-surface rounded-lg">
            <StreamingText text={output} isStreaming={isStreaming} />
          </div>
        )}
      </Card>
    </div>
  )
}
```
