"""Where MCN keeps its own files, so running a script never litters the project folder."""
import os
from pathlib import Path


def mcn_home(*parts: str) -> Path:
    """~/.mcn/<parts> (or $MCN_HOME/<parts>), created on first use."""
    base = Path(os.environ.get("MCN_HOME") or Path.home() / ".mcn")
    path = base.joinpath(*parts)
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError:          # read-only home (some CI sandboxes): fall back to a temp dir
        import tempfile
        path = Path(tempfile.gettempdir(), "mcn", *parts)
        path.mkdir(parents=True, exist_ok=True)
    return path
