# AI functions

AI calls are ordinary functions. They use Claude (`claude-opus-5-5` by default) when `ANTHROPIC_API_KEY` is set, and return clearly labelled mock answers when it isn't, so code always runs.

```bash
export ANTHROPIC_API_KEY=your-key
```

## Generate text: `ai`

```mcn
var article = "MCN is a language for building full-stack apps with AI built in."
var summary = ai("Summarise in one sentence: " + article)
var formal = ai("Rewrite formally: " + summary, {temperature: 0.2})
log(summary)
```

`llm(model, prompt, options?)` does the same with an explicit model name.

## Choose a label: `classify`

```mcn
var ticket = "I was charged twice this month"
var team = classify(ticket, ["billing", "bug", "account"])
log(team)      // billing
```

It always returns one of the labels you give it, so you can branch on the result safely.

## Pull out fields: `extract`

Describe the shape with a `contract`, then extract it from free text:

```mcn
contract Invoice
    vendor: str
    amount: float
    due_date: str

var email = "Acme Ltd invoice for $1,250.00, payment due 30 November."
var invoice = extract(email, Invoice)
log(invoice.vendor)
```

## Answer from documents: `rag`

```mcn
var docs = [
    "Refunds are issued within 5 working days.",
    "Support is available Monday to Friday, 9am to 5pm."
]
var answer = rag("How long do refunds take?", docs)
log(answer)
```

For larger collections, store documents once and search them:

```mcn
vector_upsert("refunds", "Refunds are issued within 5 working days.")
vector_upsert("hours", "Support is available Monday to Friday.")
var hits = vector_search("when will I get my money back", 1)
log(hits[0].id)       // refunds
```

`embed(text)` returns the embedding vector itself. Embeddings use OpenAI when `OPENAI_API_KEY` is set, Ollama when `OLLAMA_URL` is set, and a deterministic local fallback otherwise.

## Human approval: `checkpoint`

`checkpoint(message, data)` pauses a script and asks a person to approve, reject or edit `data` before it continues — for example before sending an AI-written email.

## Seeing what happened

Studio's **AI & RAG Inspector** lists every AI call with its prompt, response, model and duration. That's the quickest way to debug a prompt.

## Mock mode

Without a key:

- `ai`, `llm`, `extract` and `rag` return text starting with `[Claude Mock — set ANTHROPIC_API_KEY to enable]`.
- `classify` returns the first label.
- `vector_search` still works, using the local fallback embeddings.

> **Note** Mock answers are for running code without a key — in class, in CI, offline. Don't judge prompt quality on them.

## Settings

| Variable | Effect |
|---|---|
| `ANTHROPIC_API_KEY` | Enables real AI calls |
| `MCN_AI_MODEL` | Model for `ai()` (default `claude-opus-5-5`) |
| `MCN_CLAUDE_MODEL` | Model for Studio's Copilot and `mcn generate` |
