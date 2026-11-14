"""
Phone calls with Twilio: TwiML replies, respond(), form-encoded webhooks, request
signatures, outgoing calls, and the Voice Agent Builder template over real HTTP.
"""
import contextlib
import io
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mcn.core_engine import voice  # noqa: E402
from mcn.core_engine.voice import signature_for, voice_hangup, voice_say, voice_transfer  # noqa: E402

TEMPLATE = ROOT / "mcn/web-playground/playground_server/templates/voice_agent_builder"


def test_twiml():
    say = voice_say('Hi <there> & "welcome"', {"voice": "Polly.Amy", "language": "en-GB", "hints": ["refund", "order"]})
    assert say["content_type"] == "text/xml" and say["status"] == 200
    assert '<Gather input="speech" action="voice_turn" method="POST" speechTimeout="auto" language="en-GB" hints="refund, order">' in say["body"]
    assert '<Say voice="Polly.Amy" language="en-GB">Hi &lt;there&gt; &amp; "welcome"</Say>' in say["body"]
    assert say["body"].endswith('<Redirect method="POST">voice_turn</Redirect></Response>')
    assert voice_hangup("Bye")["body"].endswith("<Say voice=\"Polly.Joanna\" language=\"en-US\">Bye</Say><Hangup/></Response>")
    assert '<Dial timeout="20">+15551234567</Dial>' in voice_transfer("One moment", "+1 (555) 123-4567")["body"]
    with pytest.raises(ValueError, match="phone number"):
        voice_transfer("x", "call mom")


def test_twilio_call_needs_setup(monkeypatch):
    for name in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_FROM_NUMBER", "MCN_PUBLIC_URL", "PUBLIC_URL"):
        monkeypatch.delenv(name, raising=False)
    assert "TWILIO_ACCOUNT_SID" in voice.twilio_call("+15551234567", "voice_outbound")["error"]
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "AC1")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "t")
    monkeypatch.setenv("TWILIO_FROM_NUMBER", "+15550000000")
    assert "isn't a phone number" in voice.twilio_call("mom", "voice_outbound")["error"]
    assert "MCN_PUBLIC_URL" in voice.twilio_call("+15551234567", "voice_outbound")["error"]


def test_twilio_call_posts_to_the_rest_api(monkeypatch):
    sent = {}

    class Reply:
        status_code, content = 201, b"{}"

        def json(self):
            return {"sid": "CA123", "status": "queued"}

    def post(url, data, auth, timeout):
        sent.update(url=url, data=data, auth=auth)
        return Reply()
    import requests
    monkeypatch.setattr(requests, "post", post)
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "AC1")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "secret")
    monkeypatch.setenv("TWILIO_FROM_NUMBER", "+15550000000")
    monkeypatch.setenv("MCN_PUBLIC_URL", "https://example.ngrok.app/")
    result = voice.twilio_call("+1 555 123 4567", "voice_outbound", {"status_callback": "voice_status"})
    assert result == {"success": True, "sid": "CA123", "status": "queued", "to": "+15551234567"}
    assert sent["url"] == "https://api.twilio.com/2010-04-01/Accounts/AC1/Calls.json"
    assert sent["auth"] == ("AC1", "secret")
    assert sent["data"]["Url"] == "https://example.ngrok.app/voice_outbound"
    assert sent["data"]["StatusCallback"] == "https://example.ngrok.app/voice_status"


def test_signature_matches_twilios_published_example():
    # https://www.twilio.com/docs/usage/security#validating-requests
    params = {"CallSid": "CA1234567890ABCDE", "Caller": "+12349013030", "Digits": "1234", "From": "+12349013030",
              "To": "+18005551212"}
    assert signature_for("https://mycompany.com/myapp.php?foo=1&bar=2", params, "12345") == "0/KCTR6DLpKmkAf8muzZqo1nDgQ="


# ── Over HTTP ────────────────────────────────────────────────────────────────

APP = '''service phone
    auth "token"
    public incoming, echo

    endpoint incoming(CallSid: str, From: str = "", To: str = "")
        if not twilio_request_ok()
            return respond("Forbidden", "text/plain", 403)
        return voice_say("Hello " + From, {action: "turn"})

    endpoint echo(text: str)
        return respond("<b>" + text + "</b>", "text/html")

    endpoint hello()
        return {ok: true}
'''


@pytest.fixture
def client(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from mcn.core_engine.mcn_server import MCNServer
    script = tmp_path / "main.mcn"
    script.write_text(APP)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "tok")
    monkeypatch.setenv("MCN_PUBLIC_URL", "https://calls.example.com")
    with contextlib.redirect_stdout(io.StringIO()):
        server = MCNServer()
        server.load_script(str(script))
    return TestClient(server.app)


def test_a_signed_twilio_webhook_gets_twiml(client):
    form = {"CallSid": "CA1", "From": "+15551112222", "To": "+15553334444"}
    signature = signature_for("https://calls.example.com/incoming", form, "tok")
    r = client.post("/incoming", data=form, headers={"X-Twilio-Signature": signature})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/xml")
    assert "Hello +15551112222" in r.text and 'action="turn"' in r.text


def test_unsigned_or_forged_webhooks_are_refused(client, monkeypatch):
    form = {"CallSid": "CA1", "From": "+15551112222"}
    assert client.post("/incoming", data=form).status_code == 403
    forged = signature_for("https://calls.example.com/incoming", {**form, "From": "+19999999999"}, "tok")
    assert client.post("/incoming", data=form, headers={"X-Twilio-Signature": forged}).status_code == 403
    monkeypatch.delenv("TWILIO_AUTH_TOKEN")
    good = signature_for("https://calls.example.com/incoming", form, "tok")
    assert client.post("/incoming", data=form, headers={"X-Twilio-Signature": good}).status_code == 403


def test_respond_and_json_and_auth_still_work(client):
    r = client.post("/echo", json={"text": "hi"})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/html") and r.text == "<b>hi</b>"
    assert client.get("/echo", params={"text": "yo"}).text == "<b>yo</b>"
    assert client.post("/hello", json={}).status_code == 401               # auth "token" still applies


def test_the_template_answers_a_real_twilio_call(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from mcn.core_engine.mcn_server import MCNServer
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "tok")
    monkeypatch.setenv("MCN_PUBLIC_URL", "https://calls.example.com")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with contextlib.redirect_stdout(io.StringIO()):
        server = MCNServer()
        server.load_script(str(TEMPLATE / "backend" / "main.mcn"))
    http = TestClient(server.app)

    def twilio(path, form):
        sig = signature_for(f"https://calls.example.com{path}", form, "tok")
        return http.post(path, data=form, headers={"X-Twilio-Signature": sig})

    r = twilio("/voice_incoming", {"CallSid": "CAx", "From": "+15551112222", "To": "+15550100001"})
    assert r.status_code == 200 and "Bright Smile Dental" in r.text and "<Gather" in r.text
    r = twilio("/voice_turn", {"CallSid": "CAx", "SpeechResult": "I want to speak to a representative"})
    assert "<Dial" in r.text and "+15550100009" in r.text
    r = twilio("/voice_status", {"CallSid": "CAx", "CallStatus": "completed", "CallDuration": "31"})
    assert r.json() == {"success": True}
    assert http.post("/voice_incoming", data={"CallSid": "CAy", "To": "+15550100001"}).status_code == 403
    assert http.post("/list_calls", json={}).status_code == 401           # the dashboard needs the app's token
