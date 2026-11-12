"""
MCN Version 3.0 Extensions - Natural Language Programming
- AI Model Management & Fine-tuning
- IoT & Edge Integration
- Event-driven & Workflow Syntax
- AI-powered Data Pipelines
- Natural Language to Code Translation
"""

import asyncio
import json
import os
import re
import time
from typing import Any, Dict, List, Optional, Union, Callable
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
import threading
import queue


@dataclass
class MCNModel:
    """AI Model registration and management"""
    name: str
    provider: str
    api_key: Optional[str] = None
    endpoint: Optional[str] = None
    config: Dict = None
    fine_tuned: bool = False


@dataclass
class MCNEvent:
    """Event system for triggers and workflows"""
    name: str
    data: Dict
    timestamp: float
    source: str


@dataclass
class MCNAgent:
    """Autonomous agent definition"""
    name: str
    prompt: str
    model: str
    memory: Dict
    tools: List[str]
    active: bool = False


class MCNModelRegistry:
    """Named model settings for `use "ai_v3"`. Any provider model name works
    (claude-*, gpt-*, an Ollama model, or a name given to fine_tune())."""

    def __init__(self):
        self.models = {}
        self.active_model = None

    def register_model(self, name: str, provider: str, **config):
        """Remember settings (provider, temperature…) under a name"""
        self.models[name] = MCNModel(name, provider, config=config)
        return f"Model '{name}' registered with {provider}"

    def set_active_model(self, name: str):
        """Use this model for ai_v3's run() when no model is named"""
        self.active_model = name
        return f"Active model set to '{name}'"

    def get_model(self, name: str = None) -> Optional[MCNModel]:
        return self.models.get(name or self.active_model or "")

    def options_for(self, name: Optional[str]) -> Dict[str, Any]:
        """ai() options for a model name: its registered settings, if any."""
        model = self.models.get(name or "")
        opts: Dict[str, Any] = dict(model.config or {}) if model else {}
        if name:
            opts["model"] = name
        if model and model.provider in ("anthropic", "openai", "ollama"):
            opts.setdefault("provider", model.provider)
        return opts

    def fine_tune_model(self, base_model: str, dataset_path: str, new_name: str, params: dict = None):
        """Fine-tune for real (see fine_tuning.py)"""
        from .fine_tuning import fine_tune
        return fine_tune(base_model, dataset_path, new_name, params)


class MCNEventSystem:
    """Event-driven programming system"""
    
    def __init__(self):
        self.event_handlers = {}
        self.event_queue = queue.Queue()
        self.running = False
        self.worker_thread = None
    
    def on_event(self, event_name: str, handler: Callable):
        """Register event handler"""
        if event_name not in self.event_handlers:
            self.event_handlers[event_name] = []
        self.event_handlers[event_name].append(handler)
    
    def trigger_event(self, event_name: str, data: Dict = None, source: str = "user"):
        """Trigger an event"""
        event = MCNEvent(event_name, data or {}, time.time(), source)
        self.event_queue.put(event)
        
        if not self.running:
            self._start_event_loop()
        
        return f"Event '{event_name}' triggered"
    
    def _start_event_loop(self):
        """Start the event processing loop"""
        if self.running:
            return
        
        self.running = True
        self.worker_thread = threading.Thread(target=self._process_events)
        self.worker_thread.daemon = True
        self.worker_thread.start()
    
    def _process_events(self):
        """Process events in background thread"""
        while self.running:
            try:
                event = self.event_queue.get(timeout=1)
                self._handle_event(event)
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Event processing error: {e}")
    
    def _handle_event(self, event: MCNEvent):
        """Handle a single event"""
        handlers = self.event_handlers.get(event.name, [])
        for handler in handlers:
            try:
                handler(event.data)
            except Exception as e:
                print(f"Event handler error for '{event.name}': {e}")


from .iot import DeviceRegistry as MCNIoTConnector, shared_registry as get_shared_iot_connector  # noqa: E402,F401


class MCNAgentSystem:
    """Named agents: a role prompt, a model, conversation memory, and optional tools.

    agent("create", "analyst", {prompt: "You analyse sales data", tools: ["revenue_by_month"]})
    agent("think", "analyst", "Which month was best?")
    """

    HISTORY = 12                    # exchanges each agent remembers

    def __init__(self, model_registry: MCNModelRegistry):
        self.agents = {}
        self.model_registry = model_registry
        # Set by the interpreter: runs agent_run() so tools can call the program's functions
        self.tool_runner: Optional[Callable[[str, dict], Any]] = None

    def create_agent(self, name: str, prompt: str, model: str = None, tools: List[str] = None):
        agent_model = model or self.model_registry.active_model
        self.agents[name] = MCNAgent(name=name, prompt=prompt, model=agent_model,
                                     memory={"history": []}, tools=list(tools or []), active=True)
        return f"Agent '{name}' created" + (f" with model '{agent_model}'" if agent_model else "")

    def create_multi_agent(self, name: str, sub_agents: List[str], coordinator_prompt: str, model: str = None):
        missing = [a for a in sub_agents if a not in self.agents]
        if missing:
            raise Exception(f"Create these agents first: {', '.join(missing)}")
        self.agents[name] = MCNAgent(name=name, prompt=coordinator_prompt, model=model or self.model_registry.active_model,
                                     memory={"history": [], "sub_agents": list(sub_agents), "is_coordinator": True},
                                     tools=[], active=True)
        return f"Multi-agent coordinator '{name}' created with {len(sub_agents)} sub-agents"

    def activate_agent(self, name: str):
        self._get(name).active = True
        return f"Agent '{name}' activated"

    def reset_agent(self, name: str):
        self._get(name).memory["history"] = []
        return f"Agent '{name}' forgot its conversation"

    def list_agents(self):
        return [{"name": a.name, "model": a.model, "tools": a.tools, "remembers": len(a.memory.get("history", [])),
                 "coordinator": bool(a.memory.get("is_coordinator"))} for a in self.agents.values()]

    def _get(self, name: str) -> MCNAgent:
        if name not in self.agents:
            raise Exception(f"Agent '{name}' not found. Create it with agent(\"create\", \"{name}\", {{prompt: ...}})")
        return self.agents[name]

    def agent_think(self, name: str, input_data: Any):
        """The agent answers, using its role, its recent conversation and its tools."""
        from .ai_builtins import mcn_ai
        agent = self._get(name)
        if not agent.active:
            raise Exception(f"Agent '{name}' is not active")
        message = input_data if isinstance(input_data, str) else json.dumps(input_data, default=str)
        history = agent.memory.setdefault("history", [])
        transcript = "\n".join(f"{h['role']}: {h['content']}" for h in history[-2 * self.HISTORY:])
        prompt = (f"Conversation so far:\n{transcript}\n\nNew message: {message}" if transcript else message)

        if agent.memory.get("is_coordinator"):
            answers = []
            for sub in agent.memory.get("sub_agents", []):
                if sub in self.agents and self.agents[sub].active:
                    answers.append(f"{sub}: {self.agent_think(sub, message)}")
            prompt = (f"{prompt}\n\nYour team's answers:\n" + "\n\n".join(answers) +
                      "\n\nCombine them into one answer, resolving any disagreement.")
            reply = mcn_ai(prompt, {**self.model_registry.options_for(agent.model), "system": agent.prompt})
        elif agent.tools and self.tool_runner:
            result = self.tool_runner(prompt, {"system": agent.prompt, "tools": agent.tools,
                                               **({"model": agent.model} if agent.model else {})})
            reply = result.get("reply", "") if isinstance(result, dict) else str(result)
        else:
            reply = mcn_ai(prompt, {**self.model_registry.options_for(agent.model), "system": agent.prompt})

        history += [{"role": "user", "content": message}, {"role": "assistant", "content": str(reply)}]
        del history[:-2 * self.HISTORY]
        return reply


class MCNDataPipeline:
    """Data pipelines: named steps run in order. Lists are processed item by item.

    Steps: clean, transform, ai_classify (params.categories), ai_extract (params.fields), and
    any MCN function name (set by the interpreter), which gets the data and returns the new data.
    """

    STEPS = ("clean", "transform", "ai_classify", "ai_extract")

    def __init__(self, model_registry: MCNModelRegistry):
        self.model_registry = model_registry
        self.pipelines = {}
        self.function_lookup: Optional[Callable[[str], Any]] = None    # set by the interpreter

    def create_pipeline(self, name: str, steps: List[Dict]):
        for step in steps:
            kind = step.get("type")
            if kind not in self.STEPS and not (self.function_lookup and self.function_lookup(kind)):
                raise Exception(f"Unknown pipeline step '{kind}'. Use {', '.join(self.STEPS)} or a function name")
        self.pipelines[name] = {"steps": steps, "created": time.time(), "runs": 0}
        return f"Pipeline '{name}' created with {len(steps)} steps"

    def list_pipelines(self):
        return [{"name": n, "steps": [s.get("type") for s in p["steps"]], "runs": p["runs"]}
                for n, p in self.pipelines.items()]

    def run_pipeline(self, name: str, data: Any):
        if name not in self.pipelines:
            raise Exception(f"Pipeline '{name}' not found")
        pipeline = self.pipelines[name]
        result = data
        for step in pipeline["steps"]:
            kind, params = step.get("type"), step.get("params", {}) or {}
            if kind in self.STEPS:
                handler = getattr(self, f"_{kind.replace('ai_', 'ai_')}" if kind.startswith("ai_") else f"_{kind}_data")
                result = [handler(item, params) for item in result] if isinstance(result, list) else handler(result, params)
            else:
                fn = self.function_lookup(kind) if self.function_lookup else None
                if not fn:
                    raise Exception(f"Unknown pipeline step '{kind}'")
                result = fn(result)
        pipeline["runs"] += 1
        return result

    def _clean_data(self, data: Any, params: Dict):
        if isinstance(data, str):
            cleaned = re.sub(r'\s+', ' ', data.strip())
            if params.get("remove_special_chars"):
                cleaned = re.sub(r'[^\w\s]', '', cleaned)
            return cleaned
        if isinstance(data, dict):
            return {k: (re.sub(r'\s+', ' ', v.strip()) if isinstance(v, str) else v) for k, v in data.items()}
        return data

    def _transform_data(self, data: Any, params: Dict):
        kind = params.get("type", "normalize")
        if kind == "normalize" and isinstance(data, str):
            return data.lower()
        if kind == "extract_numbers" and isinstance(data, str):
            return [float(n) for n in re.findall(r'-?\d+\.?\d*', data)]
        return data

    @staticmethod
    def _text(data: Any, params: Dict) -> str:
        if isinstance(data, dict):
            field = params.get("field")
            return str(data.get(field, "")) if field else json.dumps(data, default=str)
        return str(data)

    def _ai_classify(self, data: Any, params: Dict):
        """Label each item with classify()."""
        from .ai_builtins import mcn_classify
        categories = params.get("categories") or ["positive", "negative", "neutral"]
        label = mcn_classify(self._text(data, params), list(categories))
        if isinstance(data, dict):
            return {**data, params.get("as", "classification"): label}
        return {"data": data, "classification": label}

    def _ai_extract(self, data: Any, params: Dict):
        """Pull out fields with extract(): params.fields is a list of names or {name: type}."""
        from .ai_builtins import mcn_extract
        fields = params.get("fields") or {"people": "list", "organizations": "list", "places": "list", "dates": "list"}
        if isinstance(fields, list):
            fields = {f: "str" for f in fields}
        contract = type("Fields", (), {"fields": list(fields.items())})()
        extracted = mcn_extract(self._text(data, params), contract)
        if isinstance(data, dict):
            return {**data, **(extracted if isinstance(extracted, dict) else {})}
        return {"data": data, **(extracted if isinstance(extracted, dict) else {"extracted": extracted})}


class MCNDataSourceSystem:
    """Knowledge sources for questions answered from your documents.

    datasource("create", "handbook", "file", "docs/handbook.md")
    datasource("create", "faq", "text", faq_text)
    datasource("create", "site", "url", "https://example.com/help")
    rag("query_datasource", "How many days off do I get?", "handbook")
    """

    CHUNK = 1200
    TOP_K = 5

    def __init__(self):
        self.datasources = {}

    @classmethod
    def _chunks(cls, text: str, source: str) -> List[Dict[str, str]]:
        parts, current = [], ""
        for para in re.split(r"\n\s*\n", text):
            para = para.strip()
            if not para:
                continue
            if current and len(current) + len(para) > cls.CHUNK:
                parts.append(current)
                current = ""
            current = (current + "\n\n" + para).strip()
            while len(current) > cls.CHUNK * 2:
                parts.append(current[:cls.CHUNK])
                current = current[cls.CHUNK:]
        if current:
            parts.append(current)
        return [{"text": p, "source": source} for p in parts]

    @staticmethod
    def _read_file(path: str) -> str:
        from pathlib import Path
        file = Path(str(path))
        if not file.exists():
            raise Exception(f"File not found: {path}")
        if file.suffix.lower() == ".pdf":
            try:
                from pypdf import PdfReader
            except ImportError:
                raise Exception("Reading PDFs needs the pypdf package: pip install pypdf")
            return "\n\n".join(page.extract_text() or "" for page in PdfReader(str(file)).pages)
        return file.read_text(encoding="utf-8", errors="replace")

    @staticmethod
    def _read_url(url: str) -> str:
        import html as _html
        import requests
        res = requests.get(url, timeout=20, headers={"User-Agent": "mcn-datasource"})
        res.raise_for_status()
        text = res.text
        if "html" in res.headers.get("content-type", ""):
            text = re.sub(r"(?is)<(script|style|nav|footer)[^>]*>.*?</\1>", " ", text)
            text = re.sub(r"(?i)<(br|/p|/div|/h[1-6]|/li)[^>]*>", "\n\n", text)
            text = _html.unescape(re.sub(r"<[^>]+>", " ", text))
            text = re.sub(r"[ \t]+", " ", text)
        return text

    def create_datasource(self, name: str, source_type: str, payload: Any):
        if source_type == "text":
            documents = self._chunks(str(payload), "text")
        elif source_type == "file":
            paths = payload if isinstance(payload, list) else [payload]
            documents = [c for path in paths for c in self._chunks(self._read_file(path), str(path))]
        elif source_type == "url":
            urls = payload if isinstance(payload, list) else [payload]
            documents = [c for url in urls for c in self._chunks(self._read_url(url), str(url))]
        elif source_type == "documents" and isinstance(payload, list):
            documents = [{"text": d.get("text", "") if isinstance(d, dict) else str(d), "source": "documents"}
                         for d in payload]
        else:
            raise Exception(f"Unknown source type '{source_type}'. Use text, file, url or documents")
        self.datasources[name] = {"type": source_type, "documents": documents, "created": time.time()}
        return f"DataSource '{name}' created with {len(documents)} chunks"

    def list_datasources(self):
        return [{"name": n, "type": d["type"], "chunks": len(d["documents"])} for n, d in self.datasources.items()]

    def search(self, name: str, query: str, top_k: int = TOP_K) -> List[Dict[str, Any]]:
        """The chunks most relevant to the question (word overlap, weighted by rarity)."""
        if name not in self.datasources:
            raise Exception(f"DataSource '{name}' not found")
        docs = self.datasources[name]["documents"]
        words = [w for w in re.findall(r"\w+", query.lower()) if len(w) > 2]
        if not words:
            return docs[:top_k]
        counts = {w: sum(1 for d in docs if w in d["text"].lower()) for w in words}
        import math
        scored = []
        for d in docs:
            low = d["text"].lower()
            score = sum(math.log(1 + len(docs) / (1 + counts[w])) for w in words if w in low)
            scored.append((score, d))
        scored.sort(key=lambda x: -x[0])
        return [d for score, d in scored[:top_k] if score > 0] or docs[:top_k]

    def query_rag(self, name: str, query: str):
        """Answer a question from the source's most relevant chunks."""
        from .stdlib_builtins import mcn_rag
        hits = self.search(name, str(query))
        return mcn_rag(str(query), [h["text"] for h in hits])


class MCNNaturalLanguage:
    """Turn plain-English instructions into MCN code.

    With an AI key, Claude (or your chosen provider) writes the code and MCN's parser checks
    it. Without one, a few simple sentence patterns still work offline.
    """

    _GUIDE = """Write MCN code for the instruction. MCN rules: statements one per line; blocks are
indented 4 spaces with no braces or colons (`if x > 1`, `for item in items`, `function name(a, b)`);
`var name = value` declares; `log(value)` prints; strings use double quotes; lists [1, 2]; objects
{name: "Ana"}; built-ins include query(sql, params), fetch(url), read_file, write_file, ai(prompt),
classify(text, labels), extract(text, Contract), send_email(to, subject, body), len, sum, map, filter.
Reply with only the code, no explanation and no code fences."""

    def __init__(self, model_registry: MCNModelRegistry):
        self.model_registry = model_registry
        self.patterns = self._init_patterns()

    @staticmethod
    def _init_patterns():
        """Offline sentence patterns, in today's MCN syntax: (regex, function of the groups → code)."""
        v = MCNNaturalLanguage._value
        c = MCNNaturalLanguage._condition
        return [
            (r"create (?:a )?variable (\w+) (?:with value |equal to |= )(.+)",
             lambda n, x: f"var {n} = {MCNNaturalLanguage._literal(x)}"),
            (r"set (\w+) to (.+)", lambda n, x: f"var {n} = {v(x)}"),
            (r"if (.+?) then (?:print|log|show) (.+)", lambda cond, x: f"if {c(cond)}\n    log({v(x)})"),
            (r"for each (\w+) in (\w+)(?: do)? (?:print|log|show) (.+)",
             lambda item, items, x: f"for {item} in {items}\n    log({v(x)})"),
            (r"call (?:function )?(\w+) with (.+)", lambda fn, x: f"{fn}({v(x)})"),
            (r"(?:print|log|show) (.+)", lambda x: f"log({v(x)})"),
            (r"read (?:the )?file (.+)", lambda x: f"read_file({MCNNaturalLanguage._quote(x)})"),
            (r"write (.+) to (?:the )?file (.+)",
             lambda x, f: f"write_file({MCNNaturalLanguage._quote(f)}, {MCNNaturalLanguage._quote(x)})"),
            (r"select (.+) from (\w+)(?: where (.+))?",
             lambda cols, table, where=None: f'query("SELECT {cols} FROM {table}' + (f" WHERE {where}" if where else "") + '")'),
            (r"trigger (?:event )?(\w+)", lambda e: f'trigger("{e}")'),
            (r"send (?:an )?email to (\S+) (?:saying|with) (.+)",
             lambda to, x: f'send_email({MCNNaturalLanguage._quote(to)}, "Message", {MCNNaturalLanguage._quote(x)})'),
        ]

    @staticmethod
    def _condition(text: str) -> str:
        words = [(r"\s+is greater than or equal to\s+", " >= "), (r"\s+is less than or equal to\s+", " <= "),
                 (r"\s+is greater than\s+", " > "), (r"\s+is less than\s+", " < "),
                 (r"\s+is not equal to\s+", " != "), (r"\s+(?:is equal to|equals|is)\s+", " == ")]
        out = text.strip()
        for pattern, op in words:
            out = re.sub(pattern, op, out, flags=re.I)
        return out

    @staticmethod
    def _parses(code: str) -> Optional[str]:
        """A problem with the code, or None. Blocks must be indented, not braced (old MCN syntax)."""
        if re.search(r"\{\s*$", code, re.M) and re.search(r"^\s*\}\s*$", code, re.M):
            return "blocks use braces; indent them by 4 spaces instead"
        try:
            from .lexer import Lexer
            from .parser import Parser
            parser = Parser(Lexer(code).tokenize())
            parser.parse()
            return str(parser.errors[0]) if getattr(parser, "errors", None) else None
        except Exception as exc:
            return str(exc)

    def _pattern(self, natural_text: str) -> Optional[str]:
        lines = []
        for line in [l.strip().rstrip(".") for l in natural_text.strip().splitlines() if l.strip()]:
            for pattern, build in self.patterns:
                match = re.fullmatch(pattern, line, re.I)
                if match:
                    lines.append(build(*[g for g in match.groups() if g is not None]))
                    break
            else:
                return None
        return "\n".join(lines) if lines else None

    @staticmethod
    def _literal(text: str) -> str:
        """A number, true/false/null or quoted text, never a variable name."""
        text = text.strip().strip(".")
        if re.fullmatch(r"-?\d+(\.\d+)?|true|false|null", text):
            return text
        return MCNNaturalLanguage._quote(text)

    @staticmethod
    def _quote(text: str) -> str:
        """Always a string literal."""
        text = text.strip().strip(".")
        if len(text) >= 2 and text[0] == text[-1] == '"':
            return text
        return '"' + text.replace('"', '\\"') + '"'

    @staticmethod
    def _value(text: str) -> str:
        """A number, true/false/null, a variable name or quoted text; anything else becomes text."""
        text = text.strip().strip(".")
        if re.fullmatch(r"-?\d+(\.\d+)?|true|false|null|\".*\"", text):
            return text
        if re.fullmatch(r"[a-z_]\w*(\.\w+)*", text):         # lowercase: a variable; Capitalised: text
            return text
        return MCNNaturalLanguage._quote(text)

    def translate(self, natural_text: str) -> str:
        from .ai_builtins import _get_provider, mcn_ai
        import os
        has_ai = bool(os.getenv("ANTHROPIC_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("OLLAMA_URL"))
        if has_ai:
            prompt = natural_text
            for _ in range(2):
                code = mcn_ai(prompt, {**self.model_registry.options_for(self.model_registry.active_model),
                                       "system": self._GUIDE, "temperature": 0, "max_tokens": 2048})
                code = re.sub(r"^```\w*\n|\n```$", "", code.strip())
                problem = self._parses(code)
                if not problem:
                    return code
                prompt = f"{natural_text}\n\nYour last answer didn't parse ({problem}):\n{code}"
            raise Exception(f"Couldn't turn that into valid MCN: {problem}")
        code = self._pattern(natural_text)
        if code and not self._parses(code):
            return code
        # Mock mode: like ai(), keep running without a key, and say what's missing
        safe = natural_text.strip().replace("\n", " ")[:200]
        return f"// translate() needs an AI key (ANTHROPIC_API_KEY or OPENAI_API_KEY) for: {safe}"


# Integration functions for MCN core
def create_v3_ai_package(model_registry: MCNModelRegistry):
    """Enhanced AI package with v3.0 features"""
    
    def run_model(model_name: str, prompt: str = None, **kwargs):
        """Run a model by name (a provider model, or one made with fine_tune()); with only a prompt, the active model"""
        from .ai_builtins import mcn_llm, mcn_ai
        if prompt is None:
            prompt, model_name = model_name, model_registry.active_model
        if not model_name:
            return mcn_ai(str(prompt))
        return mcn_llm(str(model_name), str(prompt), kwargs or None)

    def train_model(base_model: str, dataset: str, new_name: str, params: dict = None):
        """Fine-tune a model on your examples (the same as fine_tune())"""
        from .fine_tuning import fine_tune
        return fine_tune(base_model, dataset, new_name, params)
    
    def set_model(model_name: str):
        """Set active model"""
        return model_registry.set_active_model(model_name)
    
    def register_model(name: str, provider: str, config: dict = None, **kwargs):
        """Register new model"""
        cfg = config or {}
        if kwargs:
            cfg.update(kwargs)
        return model_registry.register_model(name, provider, **cfg)
    
    return {
        "run": run_model,
        "train": train_model,
        "set_model": set_model,
        "register": register_model
    }


def create_v3_iot_package(iot_connector: MCNIoTConnector):
    """IoT and device integration package"""
    
    def register_device(device_id: str, device_type: str, connection_info: dict = None, **kwargs):
        """Register IoT device"""
        info = connection_info or {}
        if kwargs:
            info.update(kwargs)
        return iot_connector.register_device(device_id, device_type, info)
    
    def read_sensor(device_id: str):
        """Read from sensor"""
        return iot_connector.read_device(device_id)
    
    def send_command(device_id: str, command: str, params: dict = None, **kwargs):
        """Send command to device"""
        p = params or {}
        if kwargs:
            p.update(kwargs)
        return iot_connector.send_command(device_id, command, p)
    
    return {
        "register": register_device,
        "read": read_sensor,
        "command": send_command
    }


def create_v3_event_package(event_system: MCNEventSystem):
    """Event-driven programming package"""
    
    def on_event(event_name: str, handler_func: Any):
        """Register event handler"""
        if callable(handler_func):
            event_system.on_event(event_name, handler_func)
        else:
            def handler(data):
                print(f"Event {event_name} triggered with data: {data}")
            event_system.on_event(event_name, handler)
        return f"Handler registered for event '{event_name}'"
    
    def trigger_event(event_name: str, data: dict = None, **kwargs):
        """Trigger an event"""
        payload = {}
        if isinstance(data, dict):
            payload.update(data)
        elif data is not None:
            payload["value"] = data
        if kwargs:
            payload.update(kwargs)
        return event_system.trigger_event(event_name, payload)
    
    return {
        "on": on_event,
        "trigger": trigger_event
    }


def create_v3_agent_package(agent_system: MCNAgentSystem):
    """Autonomous agent package"""
    
    def create_agent(name: str, prompt: str, model: str = None, tools: List[str] = None):
        """Create autonomous agent"""
        return agent_system.create_agent(name, prompt, model, tools)
    
    def activate_agent(name: str):
        """Activate agent"""
        return agent_system.activate_agent(name)
    
    def agent_think(name: str, input_data: str):
        """Make agent process input"""
        return agent_system.agent_think(name, input_data)
    
    return {
        "create": create_agent,
        "activate": activate_agent,
        "think": agent_think
    }


def create_v3_pipeline_package(pipeline_system: MCNDataPipeline):
    """Data pipeline package"""
    
    def create_pipeline(name: str, *steps):
        """Create data pipeline"""
        step_list = []
        for step in steps:
            if isinstance(step, str):
                step_list.append({"type": step, "params": {}})
            elif isinstance(step, dict):
                step_list.append(step)
        
        return pipeline_system.create_pipeline(name, step_list)
    
    def run_pipeline(name: str, data: Any):
        """Run data pipeline"""
        return pipeline_system.run_pipeline(name, data)
    
    return {
        "create": create_pipeline,
        "run": run_pipeline
    }


def create_v3_nl_package(nl_system: MCNNaturalLanguage, interpreter=None):
    """Natural language programming package"""

    def run(code: str):
        # In the program's own scope, so variables it creates are visible afterwards
        if interpreter is not None:
            return interpreter.execute(code, quiet=True)
        from .mcn_interpreter import MCNInterpreter
        return MCNInterpreter().execute(code, quiet=True)

    def translate_code(natural_text: str, execute: bool = False):
        """Translate natural language to MCN code; with execute=true, also run it"""
        code = nl_system.translate(natural_text)
        return run(code) if execute else code

    def execute_natural(natural_text: str, *_):
        """Translate natural language to MCN code and run it"""
        return run(nl_system.translate(natural_text))
    
    return {
        "translate": translate_code,
        "execute": execute_natural
    }