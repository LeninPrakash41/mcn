"""
Phone calls with Twilio, and endpoints that answer with something other than JSON.

    respond(body, content_type, status)       any endpoint: reply with text, XML, HTML...
    voice_say(text, options)                  say something, then listen for the caller's answer
    voice_hangup(text, options)               say something, then end the call
    voice_transfer(text, number, options)     say something, then connect the caller to a person
    twilio_call(to, webhook, options)         start an outgoing call
    twilio_request_ok()                       inside an endpoint: did this request really come from Twilio?

voice_* return TwiML, the XML Twilio expects from a voice webhook. When the caller
answers, Twilio posts their words as `SpeechResult` to the `action` endpoint
(default `voice_turn`), with `CallSid`, `From` and `To`.

Twilio is reached through its REST API with TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN and
TWILIO_FROM_NUMBER; there is no extra library to install. MCN_PUBLIC_URL is the address
Twilio uses to reach the app (for example an ngrok or deployed URL), used to make
webhook URLs absolute and to check request signatures.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
from typing import Any, Dict, Optional
from xml.sax.saxutils import escape, quoteattr

DEFAULT_VOICE = "Polly.Joanna"
DEFAULT_LANGUAGE = "en-US"
_PHONE = re.compile(r"\+?[1-9]\d{6,14}")


class MCNResponse(dict):
    """An endpoint reply that isn't JSON. A dict, so MCN code can read .body, .content_type and .status."""


def respond(body: Any, content_type: str = "text/plain", status: int = 200) -> MCNResponse:
    return MCNResponse(body="" if body is None else str(body), content_type=str(content_type or "text/plain"),
                       status=int(status or 200))


# ── TwiML ─────────────────────────────────────────────────────────────────────

def _opts(options: Any) -> Dict[str, Any]:
    return options if isinstance(options, dict) else {}


def _say(text: Any, o: Dict[str, Any]) -> str:
    text = str(text or "").strip()
    if not text:
        return ""
    voice = str(o.get("voice") or DEFAULT_VOICE)
    language = str(o.get("language") or DEFAULT_LANGUAGE)
    return f"<Say voice={quoteattr(voice)} language={quoteattr(language)}>{escape(text)}</Say>"


def _twiml(*verbs: str) -> MCNResponse:
    return respond('<?xml version="1.0" encoding="UTF-8"?><Response>' + "".join(verbs) + "</Response>", "text/xml")


def voice_say(text: Any, options: Any = None) -> MCNResponse:
    """Say `text`, then listen. The caller's words go to options.action (default voice_turn); if they say
    nothing, Twilio posts to the same endpoint without SpeechResult."""
    o = _opts(options)
    action = str(o.get("action") or "voice_turn")
    attrs = {"input": "speech", "action": action, "method": "POST",
             "speechTimeout": str(o.get("speech_timeout") or "auto"),
             "language": str(o.get("language") or DEFAULT_LANGUAGE)}
    if o.get("hints"):
        hints = o["hints"]
        attrs["hints"] = ", ".join(hints) if isinstance(hints, (list, tuple)) else str(hints)
    if o.get("timeout"):
        attrs["timeout"] = str(int(o["timeout"]))
    gather = "<Gather " + " ".join(f"{k}={quoteattr(v)}" for k, v in attrs.items()) + ">" + _say(text, o) + "</Gather>"
    return _twiml(gather, f'<Redirect method="POST">{escape(action)}</Redirect>')


def voice_hangup(text: Any = "", options: Any = None) -> MCNResponse:
    return _twiml(_say(text, _opts(options)), "<Hangup/>")


def voice_transfer(text: Any, number: Any, options: Any = None) -> MCNResponse:
    """Say `text`, then connect the caller to `number`. If nobody answers, say options.no_answer and hang up."""
    o = _opts(options)
    number = re.sub(r"[\s()-]", "", str(number or ""))
    if not _PHONE.fullmatch(number):
        raise ValueError(f"voice_transfer needs a phone number like +15551234567, got '{number}'")
    timeout = int(o.get("timeout") or 20)
    no_answer = o.get("no_answer", "Sorry, nobody is available right now. Please call back later.")
    return _twiml(_say(text, o), f'<Dial timeout="{timeout}">{escape(number)}</Dial>', _say(no_answer, o), "<Hangup/>")


# ── Twilio REST API ───────────────────────────────────────────────────────────

def public_url() -> str:
    return (os.getenv("MCN_PUBLIC_URL") or os.getenv("PUBLIC_URL") or "").rstrip("/")


def twilio_call(to: Any, webhook: Any, options: Any = None) -> Dict[str, Any]:
    """Start an outgoing call to `to`. When it's answered, Twilio fetches TwiML from `webhook`
    (an endpoint name like "voice_outbound", or a full URL)."""
    import requests
    o = _opts(options)
    sid, token = os.getenv("TWILIO_ACCOUNT_SID", ""), os.getenv("TWILIO_AUTH_TOKEN", "")
    sender = str(o.get("from") or os.getenv("TWILIO_FROM_NUMBER", ""))
    missing = [n for n, v in (("TWILIO_ACCOUNT_SID", sid), ("TWILIO_AUTH_TOKEN", token),
                              ("TWILIO_FROM_NUMBER", sender)) if not v]
    if missing:
        return {"success": False, "error": "Twilio isn't set up: set " + ", ".join(missing)}
    to = re.sub(r"[\s()-]", "", str(to or ""))
    if not _PHONE.fullmatch(to):
        return {"success": False, "error": f"'{to}' isn't a phone number like +15551234567"}
    url = str(webhook or "")
    if not url.startswith(("http://", "https://")):
        if not public_url():
            return {"success": False, "error": "Set MCN_PUBLIC_URL to the address Twilio can reach this app at"}
        url = f"{public_url()}/{url.lstrip('/')}"
    data = {"To": to, "From": sender, "Url": url, "Method": "POST"}
    if o.get("status_callback"):
        cb = str(o["status_callback"])
        data["StatusCallback"] = cb if cb.startswith("http") else f"{public_url()}/{cb.lstrip('/')}"
        data["StatusCallbackEvent"] = "completed"
    try:
        r = requests.post(f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Calls.json",
                          data=data, auth=(sid, token), timeout=20)
        body = r.json() if r.content else {}
    except Exception as exc:
        return {"success": False, "error": f"Couldn't reach Twilio: {exc}"}
    if r.status_code >= 400:
        return {"success": False, "error": body.get("message") or f"Twilio answered {r.status_code}"}
    return {"success": True, "sid": body.get("sid"), "status": body.get("status"), "to": to}


def signature_for(url: str, params: Optional[Dict[str, Any]], token: str) -> str:
    """Twilio's X-Twilio-Signature: HMAC-SHA1 of the URL followed by the sorted POST parameters."""
    data = url + "".join(f"{k}{params[k]}" for k in sorted(params or {}))
    return base64.b64encode(hmac.new(token.encode(), data.encode(), hashlib.sha1).digest()).decode()


def twilio_request_ok() -> bool:
    """True when the current HTTP request carries a valid Twilio signature. Outside an HTTP request
    (tests, the call simulator) there is nothing to check, so it is true. Without TWILIO_AUTH_TOKEN,
    requests can't be checked and are refused."""
    from .security import current_request
    req = current_request()
    if req is None:
        return True
    token = os.getenv("TWILIO_AUTH_TOKEN", "")
    given = (req.get("headers") or {}).get("x-twilio-signature", "")
    if not token or not given:
        return False
    url = req["url"]
    if public_url():                       # what Twilio called, not what the server sees behind a proxy
        url = public_url() + req["path"] + (f"?{req['query']}" if req.get("query") else "")
    expected = signature_for(url, req.get("form"), token)
    return hmac.compare_digest(expected, given)


BUILTINS = {
    "respond": respond,
    "voice_say": voice_say,
    "voice_hangup": voice_hangup,
    "voice_transfer": voice_transfer,
    "twilio_call": twilio_call,
    "twilio_request_ok": twilio_request_ok,
}
