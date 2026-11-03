"""IDE page, marketing website and health check."""
import os
from flask import Blueprint, redirect
from .core import (
    _AUTH_AVAILABLE,
    _ROOT_DIR,
    _THIS_DIR,
    jsonify,
    send_from_directory,
)

bp = Blueprint("site", __name__)

# ── Static & Website ──────────────────────────────────────────────────────────

_WEBSITE_DIR = os.path.join(_ROOT_DIR, "website")


def _version() -> str:
    try:
        from mcn.version import __version__
        return __version__
    except ImportError:
        return "dev"

@bp.route("/")
@bp.route("/ide")
@bp.route("/playground")
def index():
    return send_from_directory(_THIS_DIR, "index.html", max_age=0)


@bp.route("/website")
def website_redirect():
    # The site uses relative links, which only resolve under the trailing slash
    return redirect("/website/")


@bp.route("/website/")
def website_index():
    return send_from_directory(_WEBSITE_DIR, "index.html")


@bp.route("/website/<path:filename>")
def website_static(filename):
    if filename.endswith("/") or os.path.isdir(os.path.join(_WEBSITE_DIR, filename)):
        if not filename.endswith("/"):
            return redirect(f"/website/{filename}/")
        filename += "index.html"
    return send_from_directory(_WEBSITE_DIR, filename)


@bp.route("/api/health")
def health():
    return jsonify({"status": "ok", "version": _version(), "auth": _AUTH_AVAILABLE})
