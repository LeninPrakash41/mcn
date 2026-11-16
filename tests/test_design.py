"""
Design settings: brand, font, corners, buttons and mode, one line each in the app block,
applied to the web and Flutter apps, and read and written by Studio's Design panel.
"""
import contextlib
import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mcn.core_engine import app_design  # noqa: E402
from mcn.core_engine.lexer import Lexer  # noqa: E402
from mcn.core_engine.parser import Parser  # noqa: E402

UI = '''component Home
    render
        h1 "Hello"
        button "Go"

app Shop
    title "Shop"
    brand "teal"
    font "Poppins"
    corners "extra"
    buttons "pill"
    mode "dark"
    layout
        sidebar
            nav "Home" Home
'''


def _app(src):
    return next(s for s in Parser(Lexer(src).tokenize()).parse().body if type(s).__name__ == "AppDecl")


def _compile(src, tmp_path):
    from mcn.core_engine.mcn_interpreter import MCNInterpreter
    from mcn.core_engine.ui_compiler import UICompiler
    from mcn.fullstack.flutter_compiler import FlutterCompiler
    interp = MCNInterpreter()
    with contextlib.redirect_stdout(io.StringIO()):
        interp.execute(src, quiet=True)
        UICompiler(output_dir=tmp_path / "web", endpoints={}).compile(interp._evaluator)
        FlutterCompiler({}).compile(interp._evaluator, tmp_path / "mobile", "a")


def test_design_lines_are_parsed_and_printed_back():
    from mcn.core_engine.unparse import to_source
    app = _app(UI)
    assert (app.brand, app.font, app.corners, app.buttons, app.mode) == ("teal", "Poppins", "extra", "pill", "dark")
    assert 'font "Poppins"' in to_source(Parser(Lexer(UI).tokenize()).parse())


def test_unknown_values_fall_back_to_the_defaults():
    d = app_design.clean({"corners": "blobby", "buttons": "pill", "mode": "night", "font": "Manrope"})
    assert d == {"brand": "", "font": "Manrope", "corners": "round", "buttons": "pill", "mode": "auto", "navbar": "bar", "header": "standard", "cards": "outlined", "toasts": "bottom"}


def test_web_app_gets_the_design(tmp_path):
    _compile(UI, tmp_path)
    css = (tmp_path / "web/src/globals.css").read_text()
    assert "--radius: 1.25rem" in css and "--button-radius: 999px" in css and "--mcn-mode: dark" in css
    assert '--font-sans: "Poppins"' in css and "font-family: var(--font-sans)" in css
    html = (tmp_path / "web/index.html").read_text()
    assert "fonts.googleapis.com/css2?family=Poppins" in html
    button = (ROOT / "mcn/ui-kit/react/src/components/ui/button.tsx").read_text()
    assert "rounded-[var(--button-radius" in button


def test_corners_are_left_to_the_theme_unless_set(tmp_path):
    _compile(UI.replace('    corners "extra"\n', '').replace('    brand "teal"\n', '    theme "minimal"\n'), tmp_path)
    css = (tmp_path / "web/src/globals.css").read_text()
    assert "--radius: 0.5rem" in css                       # the minimal theme's corners


def test_flutter_app_gets_the_design(tmp_path):
    _compile(UI, tmp_path)
    main = (tmp_path / "mobile/lib/main.dart").read_text()
    for arg in ("brand: '#0d9488'", "font: 'Poppins'", "corners: 'extra'", "buttons: 'pill'", "mode: 'dark'"):
        assert arg in main, arg
    runtime = (ROOT / "mcn/fullstack/flutter_runtime.dart").read_text()
    assert "this.font, this.corners, this.buttons, this.mode" in runtime


def test_default_look_is_violet(tmp_path):
    from mcn.core_engine.ui_compiler import UICompiler
    css = UICompiler(tmp_path)._gen_globals_css("default", "")
    assert re.search(r"--primary: 262\.1 83\.3% 57\.8%", css)
    pro = UICompiler(tmp_path)._gen_globals_css("professional", "")
    assert "--primary: 238.7 83.5% 56.5%" in pro and "--primary: 238.7 83.5% 66.0%" in pro   # indigo, light and dark


def test_reading_and_writing_the_app_block():
    src = 'component A\n    render\n        h1 "x"\n\napp S\n    title "S"\n    layout\n        main\n            A\n'
    out = app_design.write(src, {"brand": "#ff6600", "font": "Outfit", "buttons": "pill"})
    assert out.index('brand "#ff6600"') < out.index('font "Outfit"') < out.index('buttons "pill"') < out.index("layout")
    assert app_design.read(out) == {"brand": "#ff6600", "font": "Outfit", "corners": "round", "buttons": "pill", "mode": "auto", "navbar": "bar", "header": "standard", "cards": "outlined", "toasts": "bottom"}
    back = app_design.write(out, {"font": "Inter", "buttons": "rounded"})       # defaults remove the lines
    assert 'font "' not in back and 'buttons "' not in back and 'brand "#ff6600"' in back
    assert _app(back).brand == "#ff6600"


def test_studio_design_panel_reads_and_writes(tmp_path, monkeypatch):
    from playground_app import load
    _, client = load()
    from playground_server import devserver
    ws = tmp_path / "ws"
    (ws / "ui").mkdir(parents=True)
    (ws / "ui/app.mcn").write_text(UI.replace('    font "Poppins"\n', ''))
    monkeypatch.setattr(devserver, "_request_workspace", lambda: ws)
    d = client.get("/api/design").get_json()
    assert d["design"]["font"] == "Inter" and d["design"]["brand"] == "teal" and "Poppins" in d["fonts"]
    res = client.post("/api/design", json={"font": "Manrope", "mode": "light", "nonsense": "x"}).get_json()
    assert res["design"]["font"] == "Manrope" and res["design"]["mode"] == "light"
    text = (ws / "ui/app.mcn").read_text()
    assert 'font "Manrope"' in text and 'mode "light"' in text and "nonsense" not in text
    assert res["content"] == text


PHONE = UI.replace('    mode "dark"\n', '    mode "dark"\n    navbar "floating"\n    header "large"\n    cards "elevated"\n    toasts "top"\n')


def test_phone_settings_are_parsed_written_and_passed_to_flutter(tmp_path):
    app = _app(PHONE)
    assert (app.navbar, app.header, app.cards, app.toasts) == ("floating", "large", "elevated", "top")
    assert app_design.clean({"navbar": "sideways", "cards": "flat"})["navbar"] == "bar"      # unknown → default
    _compile(PHONE, tmp_path)
    main = (tmp_path / "mobile/lib/main.dart").read_text()
    for arg in ("navbar: 'floating'", "header: 'large'", "cards: 'elevated'", "toasts: 'top'"):
        assert arg in main, arg
    runtime = (ROOT / "mcn/fullstack/flutter_runtime.dart").read_text()
    assert "this.navbar, this.header, this.cards, this.toasts" in runtime
    assert "Widget _floatingBar(" in runtime and "mcnToasts == 'top'" in runtime and "mcnCards == 'elevated'" in runtime


def test_studio_offers_the_phone_settings(tmp_path, monkeypatch):
    from playground_app import load
    _, client = load()
    from playground_server import devserver
    ws = tmp_path / "ws"
    (ws / "ui").mkdir(parents=True)
    (ws / "ui/app.mcn").write_text(UI)
    monkeypatch.setattr(devserver, "_request_workspace", lambda: ws)
    assert client.get("/api/design").get_json()["mobile"]["navbar"] == ["bar", "floating", "icons", "drawer"]
    res = client.post("/api/design", json={"navbar": "icons", "cards": "flat"}).get_json()
    assert res["design"]["navbar"] == "icons" and 'cards "flat"' in (ws / "ui/app.mcn").read_text()
