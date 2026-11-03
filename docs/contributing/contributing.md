# Contributing

## Set up

```bash
git clone https://github.com/LeninPrakash41/mcn
cd mcn
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python -m pytest
```

## The test suite

| File | Covers |
|---|---|
| `tests/test_regressions.py` | Parser, evaluator and compiler cases, one per fixed bug |
| `tests/test_diagnostics.py` | Error messages, hints and the type-checker table |
| `tests/test_developer_tools.py` | `mcn init`, `check`, `serve`, tasks and methods |
| `tests/test_examples_run.py` | Every script in `examples/` and `use-cases/` runs twice and passes `mcn check` |
| `tests/test_templates_e2e.py` | Every Studio template runs, parses and builds for React and Flutter |
| `tests/test_pilot.py` | The student pilot solutions and exercise 3's error sequence |
| `tests/test_features.py` | IoT, AI trace, telemetry and packages |
| `tests/test_website_docs.py` | The website docs data is up to date and every MCN sample in them passes `mcn check` |
| `mcn/web-playground/test_playground.py` | Studio's API |

Slower checks are opt-in, and CI turns them on:

```bash
MCN_E2E_REACT=1 MCN_E2E_FLUTTER=1 python -m pytest tests/test_templates_e2e.py
```

`MCN_E2E_REACT` needs Node.js and runs `tsc --noEmit` on every generated React app; `MCN_E2E_FLUTTER` needs Flutter and runs `flutter analyze`.

## Making a change

1. Write the test first, in the file that matches the area.
2. Keep error messages friendly: say what's wrong in plain words, and add a hint to `diagnostics._HINTS` if the fix isn't obvious.
3. If you change behaviour users see, update the user docs in `website/docs/pages/` and run `python website/build_docs.py`. Implementation notes like these live in `docs/contributing/`.
4. Run `python -m pytest` and open a pull request.

## Editing the docs

The docs are Markdown in `website/docs/pages/`, ordered by `_nav.json`. `build_docs.py` bundles them into `pages.js` (and generates the built-in reference from the interpreter). Conventions:

- Start a page with `# Title` and a one-paragraph summary.
- ` ```mcn ` blocks must pass `mcn check`; mark partial snippets ` ```mcn fragment `.
- `> **Note**`, `> **Tip**` and `> **Warning**` render as callouts; `<!-- cards -->` before a list of links renders it as cards.

Preview locally with `python -m http.server -d website` and open http://localhost:8000.
