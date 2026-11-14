# Phone calls and voice agents

MCN apps can answer and make phone calls through [Twilio](https://www.twilio.com). An endpoint answers a call with a few words of MCN; Twilio turns them into speech, listens to the caller, and posts what they said back to your app. Put `ai()` in between and you have an AI phone agent.

The **Voice Agent Builder** template in Studio is a complete app built this way: phone agents with their own number, greeting, instructions and voice, a call simulator, transfers to a person, and a log of every call with its transcript.

## Answering a call

```mcn fragment
service phone
    auth "token"
    public voice_incoming, voice_turn

    endpoint voice_incoming(CallSid: str, From: str = "", To: str = "")
        if not twilio_request_ok()
            return respond("Forbidden", "text/plain", 403)
        return voice_say("Thanks for calling. How can I help?")

    endpoint voice_turn(CallSid: str, SpeechResult: str = "")
        if not twilio_request_ok()
            return respond("Forbidden", "text/plain", 403)
        if contains(lower(SpeechResult), "bye")
            return voice_hangup("Thanks for calling. Goodbye!")
        var reply = ai("A caller said: " + SpeechResult, {system: "You answer the phone for a bakery. Reply in one short sentence."})
        return voice_say(reply)
```

Twilio posts form fields named `CallSid`, `From`, `To` and, after the caller speaks, `SpeechResult`. Endpoint parameters with those names receive them; MCN reads form-encoded requests as well as JSON. Put parameters Twilio may leave out (such as `SpeechResult`) last, with a default.

| Built-in | Answers with |
|---|---|
| `voice_say(text, options)` | Says `text`, then listens. What the caller says is posted to `options.action` (default `voice_turn`); if they say nothing, the same endpoint is called without `SpeechResult` |
| `voice_hangup(text, options)` | Says `text`, then ends the call |
| `voice_transfer(text, number, options)` | Says `text`, then connects the caller to `number`. If nobody answers in `options.timeout` seconds (default 20), says `options.no_answer` and hangs up |

Options: `voice` (default `Polly.Joanna`; any [Twilio voice](https://www.twilio.com/docs/voice/twiml/say/text-speech)), `language` (default `en-US`), `hints` (words to listen for, a list), `timeout`, `action`. The replies are TwiML, the XML Twilio expects; text is escaped for you.

## Checking requests come from Twilio

Voice webhooks have to be `public`, so anyone could post to them. `twilio_request_ok()` checks the request's `X-Twilio-Signature` against your `TWILIO_AUTH_TOKEN`, using `MCN_PUBLIC_URL` as the address Twilio called. It returns false for unsigned or forged requests and when the token isn't set. In tests and the call simulator there's no HTTP request, so it returns true.

## Making a call

```mcn fragment
var result = twilio_call("+15551234567", "voice_outbound", {status_callback: "voice_status"})
if not result.success
    log(result.error)
```

Twilio calls the number, and when it's answered fetches the first words from your `voice_outbound` endpoint. `status_callback` is told when the call ends (with `CallStatus` and `CallDuration`). The result has `sid` and `status`, or `error`, which explains what's missing when Twilio isn't set up.

## Setting up Twilio

| Variable | |
|---|---|
| `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN` | Your Twilio account (Console → Account info) |
| `TWILIO_FROM_NUMBER` | A Twilio number to call from |
| `MCN_PUBLIC_URL` | The address Twilio can reach your app at: your [deployed](#/guide/deploy) URL, or a tunnel such as ngrok while you develop |
| `ANTHROPIC_API_KEY` | For `ai()` replies |

On the number's page in the Twilio console, set **A call comes in** to `MCN_PUBLIC_URL/voice_incoming` (HTTP POST) and **Call status changes** to `MCN_PUBLIC_URL/voice_status`. Twilio is reached through its REST API; there's nothing extra to install.

## Other replies: `respond()`

Any endpoint can answer with something other than JSON:

```mcn fragment
endpoint badge(name: str)
    return respond("<svg ...>" + name + "</svg>", "image/svg+xml")
```

`respond(body, content_type, status)` sets the body, its content type (default `text/plain`) and the status code (default 200). In MCN code and tests the result is an object with `body`, `content_type` and `status`.
