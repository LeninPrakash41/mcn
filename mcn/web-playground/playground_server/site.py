"""IDE page, marketing website and health check."""
import os
from flask import Blueprint, redirect
from .core import (
    _AUTH_AVAILABLE,
    _ROOT_DIR,
    _THIS_DIR,
    is_hosted,
    jsonify,
    send_from_directory,
    studio_mode,
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


@bp.route("/admin")
@bp.route("/admin/")
def admin_page():
    if not is_hosted():
        return _LOCAL_ADMIN_PAGE, 200, {"Content-Type": "text/html; charset=utf-8"}
    return send_from_directory(_THIS_DIR, "admin.html", max_age=0)


_LOCAL_ADMIN_PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>MCN Admin</title>
<style>body{font:15px/1.6 system-ui,sans-serif;max-width:560px;margin:12vh auto;padding:0 20px;color:#1f2937}
code{background:#f3f4f6;padding:2px 6px;border-radius:4px}a{color:#4f46e5}</style></head><body>
<h1>Admin lives on your account server</h1>
<p>This Studio runs on your own computer, so it has no users to manage. Users, roles and
signed-in computers are managed in the admin panel of your hosted MCN Studio, at
<code>https://&lt;your-account-server&gt;/admin</code>.</p>
<p>To run one, start Studio with <code>MCN_STUDIO_MODE=hosted</code>.
<a href="/docs/#/guide/accounts">How accounts work</a></p>
<p><a href="/">Back to Studio</a></p></body></html>"""


@bp.route("/api/studio/mode")
def studio_mode_info():
    """Which kind of Studio this is, so the page shows the right sign-in."""
    info = {"mode": studio_mode()}
    if not is_hosted():
        try:
            from mcn.core_engine.account import account_url
        except ImportError:  # pragma: no cover
            from core_engine.account import account_url  # type: ignore
        info["account_url"] = account_url()
    return jsonify(info)


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
    return jsonify({"status": "ok", "version": _version(), "auth": _AUTH_AVAILABLE, "mode": studio_mode()})
