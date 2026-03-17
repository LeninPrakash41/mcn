"""
MCN Package Registry

The real package system — supports:

  Local packages:
    ~/.mcn/packages/<org>/<name>/<version>/
      mcn_package.json          ← manifest
      index.mcn                 ← MCN-native implementation
      OR index.py               ← Python implementation (MCN_EXPORTS list)

  Namespaced packages:
    use "stripe"                → installs from built-in bundled packages
    use "accenture/healthcare"  → SI domain package
    use "myorg/crm"             → private org package

  mcn_package.json schema:
    {
      "name": "accenture/healthcare",
      "version": "1.0.0",
      "description": "HIPAA-compliant patient flows",
      "author":  "Accenture Digital",
      "mcn_version": ">=2.0",
      "exports": ["admit_patient", "discharge_patient"],
      "dependencies": { "stripe": "^1.0" }
    }

  Python package convention:
    Functions to expose are listed in MCN_EXPORTS = [fn1, fn2, ...]
    OR all public functions are exported if MCN_EXPORTS is absent.

  MCN package convention:
    All top-level `function` declarations become exports.

CLI:
    mcn install stripe
    mcn install accenture/healthcare --path ./my_pkg
    mcn packages list
    mcn packages info stripe
    mcn packages remove stripe
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

# ── Registry root ──────────────────────────────────────────────────────────────

_REGISTRY_DIR = Path.home() / ".mcn" / "packages"
_REGISTRY_DIR.mkdir(parents=True, exist_ok=True)


# ── Bundled (built-in) packages that ship with MCN ────────────────────────────
# These are available without installing; `use "stripe"` just works in dev mode.

def _bundled_stripe() -> Dict[str, Callable]:
    """Stripe integration (mock in dev; real with STRIPE_SECRET_KEY set)."""
    import os as _os

    def charge(amount: float, currency: str = "usd", description: str = "") -> Dict:
        key = _os.getenv("STRIPE_SECRET_KEY")
        if key:
            try:
                import stripe as _stripe  # type: ignore
                _stripe.api_key = key
                intent = _stripe.PaymentIntent.create(
                    amount=int(amount * 100), currency=currency, description=description
                )
                return {"id": intent.id, "status": intent.status, "amount": amount}
            except Exception as e:
                return {"error": str(e)}
        return {"id": "pi_mock_" + str(int(amount)), "status": "mock", "amount": amount}

    def create_customer(email: str, name: str = "") -> Dict:
        key = _os.getenv("STRIPE_SECRET_KEY")
        if key:
            try:
                import stripe as _stripe  # type: ignore
                _stripe.api_key = key
                c = _stripe.Customer.create(email=email, name=name)
                return {"id": c.id, "email": c.email}
            except Exception as e:
                return {"error": str(e)}
        return {"id": "cus_mock_" + email.split("@")[0], "email": email}

    def create_subscription(customer_id: str, price_id: str) -> Dict:
        key = _os.getenv("STRIPE_SECRET_KEY")
        if key:
            try:
                import stripe as _stripe  # type: ignore
                _stripe.api_key = key
                sub = _stripe.Subscription.create(
                    customer=customer_id, items=[{"price": price_id}]
                )
                return {"id": sub.id, "status": sub.status}
            except Exception as e:
                return {"error": str(e)}
        return {"id": "sub_mock", "status": "active", "customer": customer_id}

    return {"charge": charge, "create_customer": create_customer,
            "create_subscription": create_subscription}


def _bundled_twilio() -> Dict[str, Callable]:
    """Twilio SMS/WhatsApp integration."""
    import os as _os

    def send_sms(to: str, body: str, from_: str = "") -> Dict:
        sid  = _os.getenv("TWILIO_ACCOUNT_SID")
        auth = _os.getenv("TWILIO_AUTH_TOKEN")
        frm  = from_ or _os.getenv("TWILIO_FROM_NUMBER", "+15005550006")
        if sid and auth:
            try:
                from twilio.rest import Client as _Client  # type: ignore
                msg = _Client(sid, auth).messages.create(body=body, from_=frm, to=to)
                return {"sid": msg.sid, "status": msg.status}
            except Exception as e:
                return {"error": str(e)}
        return {"sid": "SM_mock", "status": "mock_sent", "to": to, "body": body}

    def send_whatsapp(to: str, body: str) -> Dict:
        return send_sms(f"whatsapp:{to}", body, from_=f"whatsapp:{_os.getenv('TWILIO_FROM_NUMBER','')}")

    return {"send_sms": send_sms, "send_whatsapp": send_whatsapp}


def _bundled_resend() -> Dict[str, Callable]:
    """Resend email API."""
    import os as _os

    def send_email(to: str, subject: str, html: str = "", text: str = "",
                   from_: str = "") -> Dict:
        key  = _os.getenv("RESEND_API_KEY")
        frm  = from_ or _os.getenv("RESEND_FROM", "noreply@example.com")
        if key:
            try:
                import resend as _resend  # type: ignore
                _resend.api_key = key
                r = _resend.Emails.send({"from": frm, "to": to, "subject": subject,
                                          "html": html or f"<p>{text}</p>"})
                return {"id": r["id"], "status": "sent"}
            except Exception as e:
                return {"error": str(e)}
        return {"id": "email_mock", "status": "mock_sent", "to": to, "subject": subject}

    return {"send_email": send_email}


def _bundled_slack() -> Dict[str, Callable]:
    """Slack webhook / API messaging."""
    import os as _os

    def post_message(channel: str, text: str, webhook_url: str = "") -> Dict:
        url    = webhook_url or _os.getenv("SLACK_WEBHOOK_URL", "")
        token  = _os.getenv("SLACK_BOT_TOKEN", "")
        if url:
            try:
                import urllib.request, json as _json
                payload = _json.dumps({"text": text}).encode()
                urllib.request.urlopen(url, data=payload)
                return {"ok": True}
            except Exception as e:
                return {"error": str(e)}
        if token:
            try:
                import urllib.request, urllib.parse, _json  # type: ignore
                data = urllib.parse.urlencode({"channel": channel, "text": text}).encode()
                req  = urllib.request.Request(
                    "https://slack.com/api/chat.postMessage", data=data,
                    headers={"Authorization": f"Bearer {token}"}
                )
                urllib.request.urlopen(req)
                return {"ok": True}
            except Exception as e:
                return {"error": str(e)}
        return {"ok": True, "mock": True, "channel": channel, "text": text}

    return {"post_message": post_message}


def _bundled_openai() -> Dict[str, Callable]:
    """Direct OpenAI API access (complements the built-in ai() function)."""
    import os as _os

    def complete(prompt: str, model: str = "gpt-4o", temperature: float = 0.7) -> str:
        key = _os.getenv("OPENAI_API_KEY")
        if key:
            try:
                from openai import OpenAI as _OAI  # type: ignore
                client = _OAI(api_key=key)
                r = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature
                )
                return r.choices[0].message.content
            except Exception as e:
                return f"[openai error: {e}]"
        return f"[mock openai] {prompt[:60]}..."

    def embed(text: str, model: str = "text-embedding-3-small") -> List[float]:
        key = _os.getenv("OPENAI_API_KEY")
        if key:
            try:
                from openai import OpenAI as _OAI  # type: ignore
                r = _OAI(api_key=key).embeddings.create(input=text, model=model)
                return r.data[0].embedding
            except Exception as e:
                return []
        return [0.0] * 384   # mock embedding

    return {"complete": complete, "embed": embed}


# ── Ollama local LLM package ───────────────────────────────────────────────────

def _bundled_ollama() -> Dict[str, Callable]:
    """
    Local LLM via Ollama (https://ollama.ai/).
    No API key required — just run `ollama serve` and pull models.

    use "ollama"
    var reply = complete("Summarise this report: " + text)
    var reply = complete("Translate to French: " + msg, "mistral")
    var vec   = embed("semantic search query")
    """
    def complete(prompt: str, model: str = "", temperature: float = 0.7,
                 system: str = "") -> str:
        from ..providers.ollama_provider import ollama_complete
        return ollama_complete(str(prompt), model=model, system=system,
                               temperature=temperature)

    def embed(text: str, model: str = "nomic-embed-text") -> List[float]:
        from ..providers.ollama_provider import ollama_embed
        return ollama_embed(str(text), model=model)

    def list_models() -> List[str]:
        """Return available local Ollama models."""
        import os as _os
        import requests as _req
        base = _os.getenv("OLLAMA_URL", "http://localhost:11434").rstrip("/")
        try:
            r = _req.get(f"{base}/api/tags", timeout=5)
            if r.status_code == 200:
                return [m["name"] for m in r.json().get("models", [])]
        except Exception:
            pass
        return []

    return {"complete": complete, "embed": embed, "list_models": list_models}


# ── Healthcare vertical (demo SI package) ─────────────────────────────────────

def _bundled_healthcare() -> Dict[str, Callable]:
    """
    Demo SI package: HIPAA-aware healthcare workflows.
    In production an SI would publish this as 'accenture/healthcare'.
    """
    import time as _time, uuid as _uuid

    def admit_patient(patient_data: Dict) -> Dict:
        """Register a patient and return admission record."""
        record = {
            "admission_id": str(_uuid.uuid4())[:8],
            "patient_id":   patient_data.get("id", str(_uuid.uuid4())[:6]),
            "name":         patient_data.get("name", "Unknown"),
            "admitted_at":  _time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "status":       "admitted",
            "ward":         patient_data.get("ward", "general"),
        }
        return record

    def discharge_patient(admission_id: str, notes: str = "") -> Dict:
        return {
            "admission_id":   admission_id,
            "discharged_at":  _time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "discharge_notes": notes,
            "status":         "discharged",
        }

    def schedule_appointment(patient_id: str, appt_type: str,
                             priority: str = "normal") -> Dict:
        return {
            "appointment_id": str(_uuid.uuid4())[:8],
            "patient_id":     patient_id,
            "type":           appt_type,
            "priority":       priority,
            "scheduled_at":   _time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "status":         "scheduled",
        }

    def check_drug_interactions(drugs: List[str]) -> Dict:
        """Mock drug interaction checker."""
        flagged = []
        risky   = {frozenset(["warfarin", "aspirin"]), frozenset(["ssri", "maoi"])}
        ds      = [d.lower() for d in drugs]
        for pair in risky:
            if pair.issubset(set(ds)):
                flagged.append(list(pair))
        return {"interactions": flagged, "safe": len(flagged) == 0, "checked": drugs}

    def hipaa_audit_log(action: str, user_id: str, patient_id: str,
                        data_accessed: str = "") -> Dict:
        entry = {
            "audit_id":     str(_uuid.uuid4())[:8],
            "action":       action,
            "user_id":      user_id,
            "patient_id":   patient_id,
            "data_accessed": data_accessed,
            "timestamp":    _time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "compliant":    True,
        }
        return entry

    return {
        "admit_patient":        admit_patient,
        "discharge_patient":    discharge_patient,
        "schedule_appointment": schedule_appointment,
        "check_drug_interactions": check_drug_interactions,
        "hipaa_audit_log":      hipaa_audit_log,
    }


# ── Finance vertical (demo SI package) ────────────────────────────────────────

def _bundled_finance() -> Dict[str, Callable]:
    """Demo SI package: KYC, AML, and banking workflow primitives."""
    import uuid as _uuid, time as _time

    def kyc_check(customer_data: Dict) -> Dict:
        """Mock KYC verification."""
        name  = customer_data.get("name", "")
        score = 85 + (len(name) % 15)   # deterministic mock
        return {
            "kyc_id":     str(_uuid.uuid4())[:8],
            "customer":   name,
            "score":      score,
            "status":     "approved" if score >= 70 else "review",
            "verified_at": _time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }

    def aml_screen(transaction: Dict) -> Dict:
        """Mock AML screening."""
        amount = float(transaction.get("amount", 0))
        return {
            "screening_id": str(_uuid.uuid4())[:8],
            "amount":       amount,
            "risk_level":   "high" if amount > 10000 else "low",
            "flagged":      amount > 50000,
            "screened_at":  _time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }

    def calculate_credit_score(data: Dict) -> Dict:
        income  = float(data.get("annual_income", 50000))
        debt    = float(data.get("total_debt", 10000))
        dti     = debt / income if income else 1
        score   = max(300, min(850, int(850 - dti * 400)))
        return {"score": score, "dti_ratio": round(dti, 2),
                "grade": "A" if score > 750 else "B" if score > 650 else "C"}

    def regulatory_report(report_type: str, data: Dict) -> Dict:
        return {
            "report_id":   str(_uuid.uuid4())[:8],
            "type":        report_type,
            "generated_at": _time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "status":      "submitted",
            "records":     len(data) if isinstance(data, list) else 1,
        }

    return {
        "kyc_check":          kyc_check,
        "aml_screen":         aml_screen,
        "calculate_credit_score": calculate_credit_score,
        "regulatory_report":  regulatory_report,
    }


# ── Package registry ───────────────────────────────────────────────────────────

def _bundled_auth() -> Dict[str, Callable]:
    """
    Built-in auth package — SQLite-backed user management + JWT.

    use "auth"
    var user  = auth.create_user("alice@example.com", "s3cur3!")
    var token = auth.login("alice@example.com", "s3cur3!")
    var me    = auth.require(token)
    auth.assign_role(user["id"], "admin")
    auth.require_role(token, "admin")
    """
    try:
        from .auth_primitives import get_auth_package
    except ImportError:
        from auth_primitives import get_auth_package  # type: ignore
    return get_auth_package()


_BUNDLED: Dict[str, Callable[[], Dict]] = {
    "auth":        _bundled_auth,
    "stripe":      _bundled_stripe,
    "twilio":      _bundled_twilio,
    "resend":      _bundled_resend,
    "slack":       _bundled_slack,
    "openai":      _bundled_openai,
    "ollama":      _bundled_ollama,
    "healthcare":  _bundled_healthcare,
    "finance":     _bundled_finance,
}

# Namespace aliases: "accenture/healthcare" → "healthcare" (bundled demo)
_NAMESPACE_ALIASES: Dict[str, str] = {
    "accenture/healthcare": "healthcare",
    "deloitte/finance":     "finance",
}


class MCNPackageRegistry:
    """
    Loads, caches, and exposes MCN packages to the interpreter.

    Resolution order for  use "pkg":
      1. Already loaded (cache)
      2. Bundled packages (_BUNDLED dict above)
      3. Installed on disk: ~/.mcn/packages/<org>/<name>/latest/
      4. Current project: ./mcn_packages/<name>/
    """

    def __init__(self):
        self._loaded: Dict[str, Dict[str, Callable]] = {}

    # ── Public API ──────────────────────────────────────────────────────────────

    def load(self, package_spec: str) -> Dict[str, Callable]:
        """
        Load a package by spec string (e.g. "stripe", "accenture/healthcare").
        Returns a dict of {function_name: callable}.
        Raises PackageNotFoundError if not found.
        """
        spec = _NAMESPACE_ALIASES.get(package_spec, package_spec)

        if spec in self._loaded:
            return self._loaded[spec]

        funcs = (
            self._load_bundled(spec) or
            self._load_from_disk(spec) or
            self._load_from_project(spec)
        )

        if funcs is None:
            raise PackageNotFoundError(
                f"Package '{package_spec}' not found.\n"
                f"  Bundled packages: {', '.join(sorted(_BUNDLED.keys()))}\n"
                f"  Install custom packages into: {_REGISTRY_DIR}"
            )

        self._loaded[spec] = funcs
        return funcs

    def installed_packages(self) -> List[Dict]:
        """List all installed packages (bundled + disk)."""
        result = []
        for name in sorted(_BUNDLED.keys()):
            result.append({"name": name, "version": "bundled", "source": "bundled"})
        for pkg_dir in sorted(_REGISTRY_DIR.rglob("mcn_package.json")):
            try:
                meta = json.loads(pkg_dir.read_text())
                result.append({
                    "name": meta.get("name", pkg_dir.parent.name),
                    "version": meta.get("version", "?"),
                    "description": meta.get("description", ""),
                    "source": str(pkg_dir.parent),
                })
            except Exception:
                pass
        return result

    def install_from_path(self, src_path: str, package_name: Optional[str] = None) -> str:
        """
        Install a package from a local directory into ~/.mcn/packages/.
        Returns the installed package name.
        """
        src = Path(src_path).resolve()
        manifest_path = src / "mcn_package.json"
        if not manifest_path.exists():
            raise PackageError(f"No mcn_package.json found in {src}")

        meta    = json.loads(manifest_path.read_text())
        name    = package_name or meta.get("name", src.name)
        version = meta.get("version", "1.0.0")

        # Destination: ~/.mcn/packages/<org/name>/<version>/
        dest = _REGISTRY_DIR / name / version
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(src, dest)

        # Also write/update a "latest" symlink
        latest = _REGISTRY_DIR / name / "latest"
        if latest.is_symlink():
            latest.unlink()
        latest.symlink_to(dest, target_is_directory=True)

        return name

    def scaffold_package(self, dest_path: str, name: str, author: str = "",
                         description: str = "") -> str:
        """Create a new package scaffold directory for authors."""
        dest = Path(dest_path)
        dest.mkdir(parents=True, exist_ok=True)

        # mcn_package.json
        (dest / "mcn_package.json").write_text(json.dumps({
            "name": name, "version": "0.1.0",
            "description": description or f"{name} package",
            "author": author,
            "mcn_version": ">=2.0",
            "exports": [],
            "dependencies": {},
        }, indent=2))

        # index.py template
        pkg_slug = name.replace("/", "_").replace("-", "_")
        (dest / "index.py").write_text(f'''"""
{name} — MCN Package
{description}
"""
from typing import Any, Dict, List


# ── Exports ───────────────────────────────────────────────────────────────────
# Add your functions here. List them in MCN_EXPORTS so MCN knows what to expose.


def hello(name: str = "world") -> str:
    """Example function. Replace with your domain logic."""
    return f"Hello from {name!r} ({{name}} package)"


# All functions listed here become available in MCN scripts via:
#   use "{name}"
#   hello("MCN")
MCN_EXPORTS = [hello]
''')

        # index.mcn template (alternative pure-MCN implementation)
        (dest / "index.mcn").write_text(f'''// {name} — MCN-native package implementation
// You can use this instead of (or alongside) index.py

function hello(name)
    return "Hello from " + name + " ({name} package)"
''')

        # README
        (dest / "README.md").write_text(f'''# {name}

{description or "A MCN package."}

## Install

```bash
mcn install --path ./path/to/this/package
```

## Usage

```mcn
use "{name}"

var result = hello("World")
log(result)
```

## Functions

| Function | Description |
|----------|-------------|
| `hello(name)` | Example function |
''')
        return str(dest)

    # ── Private loaders ────────────────────────────────────────────────────────

    def _load_bundled(self, name: str) -> Optional[Dict[str, Callable]]:
        if name in _BUNDLED:
            return _BUNDLED[name]()
        return None

    def _load_from_disk(self, spec: str) -> Optional[Dict[str, Callable]]:
        """Load from ~/.mcn/packages/<spec>/latest/ or <spec>/<latest_version>/"""
        pkg_dir = _REGISTRY_DIR / spec / "latest"
        if not pkg_dir.exists():
            # Try versioned directory (take highest version)
            parent = _REGISTRY_DIR / spec
            if parent.exists():
                versions = sorted(
                    (d for d in parent.iterdir() if d.is_dir() and d.name != "latest"),
                    key=lambda p: [int(x) for x in re.findall(r'\d+', p.name)] or [0]
                )
                if versions:
                    pkg_dir = versions[-1]

        if pkg_dir.exists():
            return self._load_from_directory(pkg_dir)
        return None

    def _load_from_project(self, spec: str) -> Optional[Dict[str, Callable]]:
        """Load from ./mcn_packages/<spec>/"""
        pkg_dir = Path("mcn_packages") / spec
        if pkg_dir.exists():
            return self._load_from_directory(pkg_dir)
        return None

    def _load_from_directory(self, pkg_dir: Path) -> Optional[Dict[str, Callable]]:
        """
        Load package from a directory. Tries index.py first, then index.mcn.
        """
        py_index  = pkg_dir / "index.py"
        mcn_index = pkg_dir / "index.mcn"

        if py_index.exists():
            return self._load_python_package(py_index)
        if mcn_index.exists():
            return self._load_mcn_package(mcn_index)
        return None

    def _load_python_package(self, py_path: Path) -> Dict[str, Callable]:
        """Dynamically import a Python package file and extract MCN_EXPORTS."""
        spec = importlib.util.spec_from_file_location("mcn_pkg", py_path)
        mod  = importlib.util.module_from_spec(spec)   # type: ignore
        spec.loader.exec_module(mod)                    # type: ignore

        if hasattr(mod, "MCN_EXPORTS"):
            return {fn.__name__: fn for fn in mod.MCN_EXPORTS}

        # Fall back: export all public callables
        return {
            name: obj for name, obj in vars(mod).items()
            if callable(obj) and not name.startswith("_")
        }

    def _load_mcn_package(self, mcn_path: Path) -> Dict[str, Callable]:
        """
        Execute an MCN file and return its declared functions as callables.
        Each top-level `function` becomes a Python callable wrapping the MCN fn.
        """
        from .mcn_interpreter import MCNInterpreter
        interp = MCNInterpreter()
        interp.execute(mcn_path.read_text())

        # Harvest user-defined functions
        funcs: Dict[str, Callable] = {}
        for name, fn in interp.evaluator.functions.items():
            from .runtime_types import MCNFunction
            if isinstance(fn, MCNFunction):
                # Wrap in a closure that runs the function via the interpreter
                def _make_wrapper(fn_name, _interp=interp):
                    def wrapper(*args):
                        return _interp.evaluator.functions[fn_name](*args)
                    wrapper.__name__ = fn_name
                    return wrapper
                funcs[name] = _make_wrapper(name)
        return funcs


# ── Errors ─────────────────────────────────────────────────────────────────────

class PackageError(Exception):
    pass

class PackageNotFoundError(PackageError):
    pass


# ── Singleton registry (shared across interpreter instances) ───────────────────
_registry: Optional[MCNPackageRegistry] = None

def get_registry() -> MCNPackageRegistry:
    global _registry
    if _registry is None:
        _registry = MCNPackageRegistry()
    return _registry
