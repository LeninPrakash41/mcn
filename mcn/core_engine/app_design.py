"""
An app's design settings: one line each in the app block.

    app Pulse
        brand "violet"        // a colour name or "#7c3aed": buttons, links, charts, accents
        font "Poppins"        // any Google Font, or "system"
        corners "round"       // sharp | soft | round | extra
        buttons "pill"        // rounded | pill | square
        mode "auto"           // auto (follows the device) | light | dark

    and for the phone app (Flutter):
        navbar "floating"     // bar | floating | icons | drawer
        header "large"        // standard | large | centered
        cards "elevated"      // outlined | elevated | flat
        toasts "top"          // bottom | top

The web compiler turns them into theme variables, the Flutter compiler into the
app's theme, and Studio's Design panel reads and writes these lines.
"""
from __future__ import annotations

import re
import urllib.parse
from typing import Dict, Optional

# Phone app (Flutter) settings: value → what Studio calls it
MOBILE = {
    "navbar": ("bar", "floating", "icons", "drawer"),
    "header": ("standard", "large", "centered"),
    "cards":  ("outlined", "elevated", "flat"),
    "toasts": ("bottom", "top"),
}
KEYS = ("brand", "font", "corners", "buttons", "mode") + tuple(MOBILE)

CORNERS = {"sharp": "0.3rem", "soft": "0.55rem", "round": "0.8rem", "extra": "1.25rem"}
CORNERS_PX = {"sharp": 5, "soft": 10, "round": 16, "extra": 24}
BUTTONS = {"rounded": "calc(var(--radius) - 2px)", "pill": "999px", "square": "0.25rem"}
BUTTONS_PX = {"rounded": None, "pill": 999, "square": 4}
MODES = ("auto", "light", "dark")
DEFAULTS = {"brand": "", "font": "Inter", "corners": "round", "buttons": "rounded", "mode": "auto",
            **{key: values[0] for key, values in MOBILE.items()}}

# A short list Studio offers; any Google Font name works in code
FONTS = ["Inter", "Poppins", "Manrope", "DM Sans", "Plus Jakarta Sans", "Space Grotesk", "Outfit",
         "Nunito", "Work Sans", "IBM Plex Sans", "Merriweather", "Playfair Display", "system"]


def clean(design: Dict[str, str]) -> Dict[str, str]:
    """The settings with unknown values replaced by the defaults."""
    out = dict(DEFAULTS)
    for key in KEYS:
        value = str((design or {}).get(key) or "").strip()
        if not value:
            continue
        if key == "corners" and value.lower() not in CORNERS:
            continue
        if key == "buttons" and value.lower() not in BUTTONS:
            continue
        if key == "mode" and value.lower() not in MODES:
            continue
        if key in MOBILE and value.lower() not in MOBILE[key]:
            continue
        out[key] = value if key in ("brand", "font") else value.lower()
    return out


def of_app(app) -> Dict[str, str]:
    return clean({k: getattr(app, k, "") for k in KEYS} if app is not None else {})


def font_stack(font: str) -> str:
    if not font or font.lower() == "system":
        return 'ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif'
    serif = font in ("Merriweather", "Playfair Display", "Lora", "Source Serif 4")
    return f'"{font}", ' + ("Georgia, serif" if serif else 'ui-sans-serif, system-ui, sans-serif')


def google_font_url(font: str) -> Optional[str]:
    if not font or font.lower() == "system":
        return None
    family = urllib.parse.quote_plus(font)
    return f"https://fonts.googleapis.com/css2?family={family}:wght@400;500;600;700;800&display=swap"


def css_vars(design: Dict[str, str]) -> Dict[str, str]:
    """Theme variables for the web app (the brand colour is handled with the colour theme)."""
    d = clean(design)
    return {"--radius": CORNERS[d["corners"]], "--button-radius": BUTTONS[d["buttons"]],
            "--font-sans": font_stack(d["font"]), "--font-name": f'"{d["font"]}"', "--mcn-mode": d["mode"]}


# ── Reading and writing the lines in a ui/app.mcn ────────────────────────────

_APP = re.compile(r"^app\s+\w+[^\n]*$", re.M)


def _block(text: str):
    """(start, end, indent) of the app block's body, or None when there's no app block."""
    m = _APP.search(text)
    if not m:
        return None
    start = m.end() + 1
    pos, indent, end = start, None, len(text)
    for line in text[start:].splitlines(keepends=True):
        stripped = line.strip()
        if stripped and not line[:1].isspace():
            end = pos
            break
        if stripped and indent is None:
            indent = line[: len(line) - len(line.lstrip())]
        pos += len(line)
    return start, end, indent or "    "


def read(text: str) -> Dict[str, str]:
    """The design settings written in a ui/app.mcn (missing ones are the defaults)."""
    block = _block(text)
    found: Dict[str, str] = {}
    if block:
        body = text[block[0]:block[1]]
        for key in KEYS:
            m = re.search(rf'^\s+{key}\s+"([^"]*)"', body, re.M)
            if m:
                found[key] = m.group(1)
    return {**clean(found), "brand": found.get("brand", "")}


def write(text: str, values: Dict[str, str]) -> str:
    """Set design lines in the app block: replace existing ones, add missing ones after `title`,
    and remove a line set back to its default (or to "")."""
    block = _block(text)
    if not block:
        raise ValueError("ui/app.mcn has no app block to put the design in")
    start, end, indent = block
    body = text[start:end]
    for key, value in values.items():
        if key not in KEYS:
            continue
        value = str(value or "").strip()
        line_re = re.compile(rf'^[ \t]+{key}\s+"[^"]*"[^\n]*\n?', re.M)
        drop = not value or (key != "brand" and value.lower() == DEFAULTS[key].lower())
        new_line = f'{indent}{key} "{value}"\n'
        if line_re.search(body):
            body = line_re.sub("" if drop else new_line, body, count=1)
        elif not drop:
            # After the title and any design lines already there, so they stay in order
            anchors = list(re.finditer(r'^[ \t]+(?:title|logo|theme|' + "|".join(KEYS) + r')\s+"[^"]*"[^\n]*\n', body, re.M))
            at = anchors[-1].end() if anchors else 0
            body = body[:at] + new_line + body[at:]
    return text[:start] + body + text[end:]
