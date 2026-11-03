"""Load the playground server once, against an isolated temp workspace."""
import contextlib
import importlib.util
import io
import sys
import tempfile
from functools import lru_cache
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


@lru_cache(maxsize=1)
def load():
    """Return (server_module, test_client)."""
    home = Path(tempfile.mkdtemp(prefix="mcn_tests_"))
    with patch("pathlib.Path.home", return_value=home), contextlib.redirect_stdout(io.StringIO()):
        spec = importlib.util.spec_from_file_location("pg_tests", ROOT / "mcn" / "web-playground" / "server.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    module.app.config["TESTING"] = True
    module.app.config["WORKSPACE"] = home / ".mcn" / "playground"
    return module, module.app.test_client()


def quiet(fn, *args, **kwargs):
    """Call fn with stdout silenced (the compilers print every file they write)."""
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args, **kwargs)
