# Contributing to MCN

Thanks for helping build MCN. How the language, Studio and tools are put together is in [`docs/contributing/`](docs/contributing/README.md).

## Set up a development copy

```bash
git clone https://github.com/LeninPrakash41/mcn
cd mcn
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
python -m pytest
```

`pip install -e .` makes the `mcn` command run your working tree, so changes take effect immediately. To try the one-line installer against your changes, see [Installer and runtime](docs/contributing/installer.md#testing-the-installer).

## Making a change

1. Open an issue first for changes to the core language.
2. Write the test first; [the suite](docs/contributing/contributing.md#the-test-suite) has a file for each area.
3. Keep errors friendly: plain words, a hint when the fix isn't obvious.
4. If users will see the change, update the docs in `website/docs/pages/` and run `python website/build_docs.py`.
5. Run `python -m pytest` and open a pull request describing the change.

User-facing text (the website, `mcn` output, Studio, the VS Code extension, generated project files) presents MCN as its own language: give `mcn` commands, never `pip` or interpreter details. See [developer-facing wording](docs/contributing/installer.md#developer-facing-wording).

## Embedding MCN in Python

The interpreter can also be used as a library:

```python
from mcn.plugin.mcn_embedded import MCNEmbedded

mcn = MCNEmbedded()
result = mcn.execute("""
    var total = price * qty
    return {total: total, tax: total * 0.1}
""", context={"price": 9.99, "qty": 3})
```

## Building packages

```bash
pip install build && python3 -m build        # wheel and sdist in dist/
```

## Security

- Never commit API keys or secrets; use environment variables.
- Report vulnerabilities privately through GitHub's security advisories for this repository.

## License

By contributing you agree that your contributions are licensed under the MIT License.
