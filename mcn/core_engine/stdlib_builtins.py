"""
MCN Standard Library Built-ins

Registers all missing language primitives so MCN scripts can do:

  Session:       session_set / session_get / session_delete / session_clear / session_all
  Cache (TTL):   cache_set / cache_get / cache_delete / cache_clear
  Memory:        memory_store / memory_get / memory_search / memory_clear / memory_all
  Vector Store:  vector_upsert / vector_search / vector_delete / vector_clear
  RAG:           rag(query, docs)  →  grounded AI answer
  Auth:          auth_hash / auth_verify_hash / auth_create_token / auth_verify_token
  Data:          parse_csv / parse_json / to_json
  Strings:       split / join / upper / lower / trim / replace / contains /
                 starts_with / ends_with / str_len / pad_left / pad_right / substring
  Arrays:        first / last / flatten / unique / sort_list / reverse_list /
                 slice_list / push / pop / array_contains / zip_lists / group_by
  Math:          abs_val / round_val / floor_val / ceil_val / min_val / max_val /
                 sum_list / average / random_float / random_int
  Queue:         queue_push / queue_pop / queue_size / queue_clear
  Crypto/UUID:   uuid / sha256 / md5
"""

from __future__ import annotations

import csv
import hashlib
import hmac
import io
import json
import math
import os
import random
import re
import time
import uuid as _uuid_mod
from typing import Any, Callable, Dict, List, Optional


# ── Shared in-memory stores (per-process, singleton) ─────────────────────────

_SESSION:      Dict[str, Any]                          = {}
_CACHE:        Dict[str, tuple]                        = {}   # key → (value, expires_at)
_MEMORY:       List[Dict[str, Any]]                    = []   # [{id, text, metadata, embedding}]
_VECTOR_STORE: Dict[str, Dict[str, Any]]               = {}   # id → {text, metadata, embedding}
_QUEUES:       Dict[str, List[Any]]                    = {}


# ─────────────────────────────────────────────────────────────────────────────
# SESSION
# ─────────────────────────────────────────────────────────────────────────────

def mcn_session_set(key: str, value: Any) -> None:
    _SESSION[str(key)] = value

def mcn_session_get(key: str, default: Any = None) -> Any:
    return _SESSION.get(str(key), default)

def mcn_session_delete(key: str) -> None:
    _SESSION.pop(str(key), None)

def mcn_session_clear() -> None:
    _SESSION.clear()

def mcn_session_all() -> Dict[str, Any]:
    return dict(_SESSION)


# ─────────────────────────────────────────────────────────────────────────────
# CACHE  (TTL in seconds, 0 = no expiry)
# ─────────────────────────────────────────────────────────────────────────────

def mcn_cache_set(key: str, value: Any, ttl: int = 300) -> None:
    expires = time.time() + int(ttl) if ttl else 0
    _CACHE[str(key)] = (value, expires)

def mcn_cache_get(key: str, default: Any = None) -> Any:
    entry = _CACHE.get(str(key))
    if entry is None:
        return default
    value, expires = entry
    if expires and time.time() > expires:
        del _CACHE[str(key)]
        return default
    return value

def mcn_cache_delete(key: str) -> None:
    _CACHE.pop(str(key), None)

def mcn_cache_clear() -> None:
    _CACHE.clear()


# ─────────────────────────────────────────────────────────────────────────────
# AGENT MEMORY  (searchable key-value; full-text substring search fallback)
# ─────────────────────────────────────────────────────────────────────────────

def mcn_memory_store(text: str, metadata: Any = None) -> str:
    """Store a piece of text with optional metadata. Returns the memory id."""
    mem_id = str(_uuid_mod.uuid4())[:8]
    entry  = {"id": mem_id, "text": str(text), "metadata": metadata or {}, "ts": time.time()}
    # Optionally store embedding if embed() is available globally (injected later)
    _MEMORY.append(entry)
    return mem_id

def mcn_memory_get(mem_id: str) -> Optional[Dict]:
    for m in _MEMORY:
        if m["id"] == mem_id:
            return m
    return None

def mcn_memory_search(query: str, top_k: int = 5) -> List[Dict]:
    """Full-text substring search over stored memories (no vector required)."""
    q = str(query).lower()
    scored = []
    for m in _MEMORY:
        text = m["text"].lower()
        # Simple relevance: count query words found in text
        words  = re.findall(r'\w+', q)
        score  = sum(1 for w in words if w in text)
        if score > 0:
            scored.append((score, m))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [m for _, m in scored[:int(top_k)]]

def mcn_memory_all() -> List[Dict]:
    return list(_MEMORY)

def mcn_memory_clear() -> None:
    _MEMORY.clear()


# ─────────────────────────────────────────────────────────────────────────────
# VECTOR STORE  (cosine similarity; falls back to keyword search without embed)
# ─────────────────────────────────────────────────────────────────────────────

def _cosine(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na  = math.sqrt(sum(x * x for x in a))
    nb  = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0

# embed_fn injected at registration time
_embed_fn: Optional[Callable] = None

def mcn_vector_upsert(doc_id: str, text: str, metadata: Any = None) -> str:
    """Upsert a document into the vector store."""
    embedding = _embed_fn(text) if _embed_fn else []
    _VECTOR_STORE[str(doc_id)] = {
        "id": str(doc_id), "text": str(text),
        "metadata": metadata or {}, "embedding": embedding,
    }
    return str(doc_id)

def mcn_vector_search(query: str, top_k: int = 5) -> List[Dict]:
    """Semantic search. Uses embeddings when available, else keyword fallback."""
    k = int(top_k)
    if not _VECTOR_STORE:
        return []

    q_emb = _embed_fn(query) if _embed_fn else []
    scored = []
    for doc in _VECTOR_STORE.values():
        if q_emb and doc["embedding"]:
            score = _cosine(q_emb, doc["embedding"])
        else:
            # keyword fallback
            words = re.findall(r'\w+', query.lower())
            score = sum(1 for w in words if w in doc["text"].lower()) / max(len(words), 1)
        scored.append((score, doc))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [{**doc, "score": round(s, 4)} for s, doc in scored[:k]]

def mcn_vector_delete(doc_id: str) -> None:
    _VECTOR_STORE.pop(str(doc_id), None)

def mcn_vector_clear() -> None:
    _VECTOR_STORE.clear()


# ─────────────────────────────────────────────────────────────────────────────
# RAG  — Retrieval-Augmented Generation
# ─────────────────────────────────────────────────────────────────────────────

# ai_fn injected at registration time
_ai_fn: Optional[Callable] = None

def mcn_rag(query: str, docs: Any = None, prompt_template: str = "") -> str:
    """
    Retrieval-Augmented Generation.

    Usage:
        rag(query)                        # searches vector_store, answers with AI
        rag(query, [doc1, doc2, ...])     # uses provided docs list
        rag(query, docs, template)        # custom prompt template

    `{context}` and `{query}` are replaced in the template.
    """
    # 1. Retrieve context
    if docs is None:
        hits = mcn_vector_search(query, top_k=5)
        context_parts = [h["text"] for h in hits]
    elif isinstance(docs, list):
        # docs can be strings or dicts with a "text" key
        context_parts = [
            d["text"] if isinstance(d, dict) else str(d)
            for d in docs
        ]
    else:
        context_parts = [str(docs)]

    context = "\n\n".join(context_parts) if context_parts else "(no context)"

    # 2. Build prompt
    if prompt_template:
        prompt = prompt_template.replace("{context}", context).replace("{query}", query)
    else:
        prompt = (
            f"Answer the following question using ONLY the provided context.\n\n"
            f"Context:\n{context}\n\n"
            f"Question: {query}\n\n"
            f"Answer:"
        )

    # 3. Call AI
    if _ai_fn:
        return _ai_fn(prompt)
    return f"[RAG] Query: {query} | Context chunks: {len(context_parts)}"


# ─────────────────────────────────────────────────────────────────────────────
# AUTH
# ─────────────────────────────────────────────────────────────────────────────

def mcn_auth_hash(password: str) -> str:
    """Hash a password with PBKDF2-HMAC-SHA256. Returns 'pbkdf2$salt$hash'."""
    salt   = os.urandom(16).hex()
    digest = hashlib.pbkdf2_hmac("sha256", str(password).encode(), salt.encode(), 260000)
    return f"pbkdf2${salt}${digest.hex()}"

def mcn_auth_verify_hash(password: str, stored_hash: str) -> bool:
    """Verify a password against a stored hash produced by auth_hash()."""
    try:
        _, salt, digest = str(stored_hash).split("$")
        new_digest = hashlib.pbkdf2_hmac("sha256", str(password).encode(), salt.encode(), 260000)
        return hmac.compare_digest(new_digest.hex(), digest)
    except Exception:
        return False

def mcn_auth_create_token(payload: Any, secret: str = "", expires_in: int = 3600) -> str:
    """
    Create a signed token (simplified JWT-style: base64(header).base64(payload).sig).
    Not a full RFC 7519 JWT — suitable for server-side session tokens.
    """
    import base64
    if isinstance(payload, dict):
        data = dict(payload)
    else:
        data = {"value": payload}
    data["_exp"] = int(time.time()) + int(expires_in)
    data["_iat"] = int(time.time())

    header  = base64.urlsafe_b64encode(b'{"alg":"HS256"}').decode().rstrip("=")
    body    = base64.urlsafe_b64encode(json.dumps(data).encode()).decode().rstrip("=")
    msg     = f"{header}.{body}"
    key     = str(secret).encode() if secret else b"mcn-default-secret"
    sig     = hmac.new(key, msg.encode(), hashlib.sha256).hexdigest()
    return f"{msg}.{sig}"

def mcn_auth_verify_token(token: str, secret: str = "") -> Optional[Dict]:
    """
    Verify a token created by auth_create_token(). Returns payload dict or null.
    """
    import base64
    try:
        parts = str(token).split(".")
        if len(parts) != 3:
            return None
        header, body, sig = parts
        msg     = f"{header}.{body}"
        key     = str(secret).encode() if secret else b"mcn-default-secret"
        expected = hmac.new(key, msg.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, sig):
            return None
        # pad body
        pad  = "=" * (-len(body) % 4)
        data = json.loads(base64.urlsafe_b64decode(body + pad))
        if data.get("_exp", 0) < time.time():
            return None   # expired
        return data
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# DATA PARSING
# ─────────────────────────────────────────────────────────────────────────────

def mcn_parse_csv(text: str, delimiter: str = ",") -> List[Dict]:
    """Parse a CSV string into a list of dicts (first row = headers)."""
    reader = csv.DictReader(io.StringIO(str(text)), delimiter=str(delimiter))
    return [dict(row) for row in reader]

def mcn_parse_json(text: str) -> Any:
    """Parse a JSON string into a dict or list."""
    return json.loads(str(text))

def mcn_to_json(value: Any, pretty: bool = False) -> str:
    """Serialize a value to a JSON string."""
    indent = 2 if pretty else None
    return json.dumps(value, indent=indent, default=str)


# ─────────────────────────────────────────────────────────────────────────────
# STRING HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def mcn_split(text: str, delimiter: str = " ") -> List[str]:
    return str(text).split(str(delimiter))

def mcn_join(items: List, delimiter: str = "") -> str:
    return str(delimiter).join(str(i) for i in items)

def mcn_upper(text: str) -> str:
    return str(text).upper()

def mcn_lower(text: str) -> str:
    return str(text).lower()

def mcn_trim(text: str) -> str:
    return str(text).strip()

def mcn_replace(text: str, old: str, new: str) -> str:
    return str(text).replace(str(old), str(new))

def mcn_contains(text: str, substr: str) -> bool:
    return str(substr) in str(text)

def mcn_starts_with(text: str, prefix: str) -> bool:
    return str(text).startswith(str(prefix))

def mcn_ends_with(text: str, suffix: str) -> bool:
    return str(text).endswith(str(suffix))

def mcn_str_len(text: str) -> int:
    return len(str(text))

def mcn_pad_left(text: str, width: int, char: str = " ") -> str:
    return str(text).rjust(int(width), str(char)[0])

def mcn_pad_right(text: str, width: int, char: str = " ") -> str:
    return str(text).ljust(int(width), str(char)[0])

def mcn_substring(text: str, start: int, end: int = -1) -> str:
    s = str(text)
    return s[int(start):int(end)] if end != -1 else s[int(start):]

def mcn_regex_match(text: str, pattern: str) -> bool:
    return bool(re.search(str(pattern), str(text)))

def mcn_regex_extract(text: str, pattern: str) -> List[str]:
    return re.findall(str(pattern), str(text))


# ─────────────────────────────────────────────────────────────────────────────
# ARRAY HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def mcn_first(items: List) -> Any:
    return items[0] if items else None

def mcn_last(items: List) -> Any:
    return items[-1] if items else None

def mcn_flatten(items: List) -> List:
    result = []
    for item in items:
        if isinstance(item, list):
            result.extend(item)
        else:
            result.append(item)
    return result

def mcn_unique(items: List) -> List:
    seen, out = set(), []
    for item in items:
        key = json.dumps(item, default=str) if isinstance(item, (dict, list)) else item
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out

def mcn_sort_list(items: List, key: str = "", reverse: bool = False) -> List:
    if key and items and isinstance(items[0], dict):
        return sorted(items, key=lambda x: x.get(key, 0), reverse=bool(reverse))
    return sorted(items, reverse=bool(reverse))

def mcn_reverse_list(items: List) -> List:
    return list(reversed(items))

def mcn_slice_list(items: List, start: int, end: int = -1) -> List:
    return items[int(start):int(end)] if end != -1 else items[int(start):]

def mcn_push(items: List, item: Any) -> List:
    items.append(item)
    return items

def mcn_pop(items: List) -> Any:
    return items.pop() if items else None

def mcn_array_contains(items: List, item: Any) -> bool:
    return item in items

def mcn_zip_lists(a: List, b: List) -> List:
    return [{"first": x, "second": y} for x, y in zip(a, b)]

def mcn_group_by(items: List, key: str) -> Dict[str, List]:
    result: Dict[str, List] = {}
    for item in items:
        k = str(item.get(key, "")) if isinstance(item, dict) else str(item)
        result.setdefault(k, []).append(item)
    return result

def mcn_count(items: Any) -> int:
    """Return length of list, dict, or string."""
    return len(items) if isinstance(items, (list, dict, str)) else 0


# ─────────────────────────────────────────────────────────────────────────────
# MATH HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def mcn_abs(n: Any) -> float:
    return abs(float(n))

def mcn_round(n: Any, digits: int = 0) -> float:
    return round(float(n), int(digits))

def mcn_floor(n: Any) -> int:
    return math.floor(float(n))

def mcn_ceil(n: Any) -> int:
    return math.ceil(float(n))

def mcn_min(*args) -> Any:
    if len(args) == 1 and isinstance(args[0], list):
        return min(args[0])
    return min(args)

def mcn_max(*args) -> Any:
    if len(args) == 1 and isinstance(args[0], list):
        return max(args[0])
    return max(args)

def mcn_sum(items: List) -> float:
    return sum(float(x) for x in items)

def mcn_average(items: List) -> float:
    if not items:
        return 0.0
    return sum(float(x) for x in items) / len(items)

def mcn_random_float() -> float:
    return random.random()

def mcn_random_int(lo: int, hi: int) -> int:
    return random.randint(int(lo), int(hi))

def mcn_clamp(value: float, lo: float, hi: float) -> float:
    return max(float(lo), min(float(hi), float(value)))


# ─────────────────────────────────────────────────────────────────────────────
# QUEUE  (in-memory named queues)
# ─────────────────────────────────────────────────────────────────────────────

def mcn_queue_push(queue_name: str, payload: Any) -> None:
    _QUEUES.setdefault(str(queue_name), []).append(payload)

def mcn_queue_pop(queue_name: str) -> Any:
    q = _QUEUES.get(str(queue_name), [])
    return q.pop(0) if q else None

def mcn_queue_size(queue_name: str) -> int:
    return len(_QUEUES.get(str(queue_name), []))

def mcn_queue_clear(queue_name: str) -> None:
    _QUEUES.pop(str(queue_name), None)


# ─────────────────────────────────────────────────────────────────────────────
# CRYPTO / UUID
# ─────────────────────────────────────────────────────────────────────────────

def mcn_uuid() -> str:
    return str(_uuid_mod.uuid4())

def mcn_sha256(text: str) -> str:
    return hashlib.sha256(str(text).encode()).hexdigest()

def mcn_md5(text: str) -> str:
    return hashlib.md5(str(text).encode()).hexdigest()


# ─────────────────────────────────────────────────────────────────────────────
# JWT FLAT BUILTINS (delegated to auth_primitives to avoid code duplication)
# ─────────────────────────────────────────────────────────────────────────────

def _jwt_sign_builtin(payload: Any, secret: str = "", expires_in: int = 3600) -> str:
    try:
        from .auth_primitives import jwt_sign
    except ImportError:
        from auth_primitives import jwt_sign  # type: ignore
    return jwt_sign(payload, secret=secret, expires_in=expires_in)

def _jwt_verify_builtin(token: str, secret: str = "") -> Optional[Dict]:
    try:
        from .auth_primitives import jwt_verify
    except ImportError:
        from auth_primitives import jwt_verify  # type: ignore
    return jwt_verify(token, secret=secret)


# ─────────────────────────────────────────────────────────────────────────────
# REGISTRATION
# ─────────────────────────────────────────────────────────────────────────────

def register_stdlib_builtins(functions: dict) -> None:
    """Register all stdlib primitives into the interpreter's function table."""
    # Inject ai/embed refs so RAG and vector search work
    global _ai_fn, _embed_fn
    _ai_fn    = functions.get("ai")
    _embed_fn = functions.get("embed")

    functions.update({
        # Session
        "session_set":       mcn_session_set,
        "session_get":       mcn_session_get,
        "session_delete":    mcn_session_delete,
        "session_clear":     mcn_session_clear,
        "session_all":       mcn_session_all,
        # Cache
        "cache_set":         mcn_cache_set,
        "cache_get":         mcn_cache_get,
        "cache_delete":      mcn_cache_delete,
        "cache_clear":       mcn_cache_clear,
        # Memory
        "memory_store":      mcn_memory_store,
        "memory_get":        mcn_memory_get,
        "memory_search":     mcn_memory_search,
        "memory_all":        mcn_memory_all,
        "memory_clear":      mcn_memory_clear,
        # Vector Store
        "vector_upsert":     mcn_vector_upsert,
        "vector_search":     mcn_vector_search,
        "vector_delete":     mcn_vector_delete,
        "vector_clear":      mcn_vector_clear,
        # RAG
        "rag":               mcn_rag,
        # Auth
        "auth_hash":         mcn_auth_hash,
        "auth_verify_hash":  mcn_auth_verify_hash,
        "auth_create_token": mcn_auth_create_token,
        "auth_verify_token": mcn_auth_verify_token,
        # Data
        "parse_csv":         mcn_parse_csv,
        "parse_json":        mcn_parse_json,
        "to_json":           mcn_to_json,
        # Strings
        "split":             mcn_split,
        "join":              mcn_join,
        "upper":             mcn_upper,
        "lower":             mcn_lower,
        "trim":              mcn_trim,
        "replace":           mcn_replace,
        "contains":          mcn_contains,
        "starts_with":       mcn_starts_with,
        "ends_with":         mcn_ends_with,
        "str_len":           mcn_str_len,
        "pad_left":          mcn_pad_left,
        "pad_right":         mcn_pad_right,
        "substring":         mcn_substring,
        "regex_match":       mcn_regex_match,
        "regex_extract":     mcn_regex_extract,
        # Arrays
        "first":             mcn_first,
        "last":              mcn_last,
        "flatten":           mcn_flatten,
        "unique":            mcn_unique,
        "sort_list":         mcn_sort_list,
        "reverse_list":      mcn_reverse_list,
        "slice_list":        mcn_slice_list,
        "push":              mcn_push,
        "pop":               mcn_pop,
        "array_contains":    mcn_array_contains,
        "zip_lists":         mcn_zip_lists,
        "group_by":          mcn_group_by,
        "count":             mcn_count,
        # Math
        "abs_val":           mcn_abs,
        "round_val":         mcn_round,
        "floor_val":         mcn_floor,
        "ceil_val":          mcn_ceil,
        "min_val":           mcn_min,
        "max_val":           mcn_max,
        "sum_list":          mcn_sum,
        "average":           mcn_average,
        "random_float":      mcn_random_float,
        "random_int":        mcn_random_int,
        "clamp":             mcn_clamp,
        # Queue
        "queue_push":        mcn_queue_push,
        "queue_pop":         mcn_queue_pop,
        "queue_size":        mcn_queue_size,
        "queue_clear":       mcn_queue_clear,
        # Crypto / UUID
        "uuid":              mcn_uuid,
        "sha256":            mcn_sha256,
        "md5":               mcn_md5,
        # ── Friendly aliases (match IntelliSense names) ──────────────────────
        # String aliases
        "to_upper":          mcn_upper,
        "to_lower":          mcn_lower,
        "substr":            mcn_substring,
        "str_replace":       mcn_replace,
        "regex_find":        mcn_regex_extract,
        "regex_replace":     lambda s, p, r: __import__('re').sub(str(p), str(r), str(s)),
        "format_str":        lambda tmpl, *args: str(tmpl).format(*args),
        # Type conversion
        "to_str":            lambda v: "" if v is None else str(v),
        "to_int":            lambda v: int(float(str(v))) if v is not None else 0,
        "to_float":          lambda v: float(str(v)) if v is not None else 0.0,
        "to_bool":           lambda v: bool(v),
        # Math aliases
        "abs":               mcn_abs,
        "ceil":              mcn_ceil,
        "floor":             mcn_floor,
        "round":             mcn_round,
        "sqrt":              lambda n: __import__('math').sqrt(float(n)),
        "pow":               lambda b, e: float(b) ** float(e),
        "random":            mcn_random_float,
        "avg":               mcn_average,
        "sum":               mcn_sum,
        "min":               mcn_min,
        "max":               mcn_max,
        # Array aliases
        "sort":              mcn_sort_list,
        "reverse":           mcn_reverse_list,
        "flat":              mcn_flatten,
        "slice":             mcn_slice_list,
        "zip":               mcn_zip_lists,
        "find":              lambda lst, fn: next((x for x in lst if fn(x)), None),
        "filter":            lambda lst, fn: [x for x in lst if fn(x)],
        "map":               lambda lst, fn: [fn(x) for x in lst],
        "reduce":            lambda lst, fn, init=None: __import__('functools').reduce(fn, lst, init) if init is not None else __import__('functools').reduce(fn, lst),
        "len":               lambda v: len(v) if v is not None else 0,
        "shift":             lambda lst: lst.pop(0) if lst else None,
        "unshift":           lambda lst, v: lst.insert(0, v) or lst,
        # Dict aliases
        "keys":              lambda d: list(d.keys()) if isinstance(d, dict) else [],
        "values":            lambda d: list(d.values()) if isinstance(d, dict) else [],
        "has_key":           lambda d, k: k in d if isinstance(d, dict) else False,
        "merge":             lambda a, b: {**a, **b},
        "json_parse":        mcn_parse_json,
        "json_str":          mcn_to_json,
        "pick":              lambda d, ks: {k: d[k] for k in ks if k in d},
        "omit":              lambda d, ks: {k: v for k, v in d.items() if k not in ks},
        # Auth aliases
        "auth_hash_password":    mcn_auth_hash,
        "auth_verify_password":  mcn_auth_verify_hash,
        # JWT flat builtins
        "jwt_sign":   _jwt_sign_builtin,
        "jwt_verify": _jwt_verify_builtin,
        # Crypto aliases
        "hash_sha256":       mcn_sha256,
        "hash_md5":          mcn_md5,
        "base64_encode":     lambda s: __import__('base64').b64encode(str(s).encode()).decode(),
        "base64_decode":     lambda s: __import__('base64').b64decode(str(s).encode()).decode(),
        # Vector aliases
        "vector_add":        mcn_vector_upsert,
        # Memory aliases
        "memory_add":        mcn_memory_store,
        # Queue aliases
        "queue_peek":        lambda name: _QUEUES.get(str(name), [None])[0] if _QUEUES.get(str(name)) else None,
        "queue_len":         lambda name: len(_QUEUES.get(str(name), [])),
    })
