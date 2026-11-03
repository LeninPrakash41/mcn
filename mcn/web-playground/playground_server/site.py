"""IDE page, marketing website and health check."""
import os
from flask import Blueprint
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

@bp.route("/")
@bp.route("/ide")
@bp.route("/playground")
def index():
    return send_from_directory(_THIS_DIR, "index.html", max_age=0)


@bp.route("/website")
@bp.route("/website/")
def website_index():
    return send_from_directory(_WEBSITE_DIR, "index.html")


@bp.route("/website/<path:filename>")
def website_static(filename):
    return send_from_directory(_WEBSITE_DIR, filename)


@bp.route("/api/health")
def health():
    return jsonify({"status": "ok", "version": "2.2", "auth": _AUTH_AVAILABLE})
