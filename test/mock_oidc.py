"""A tiny OpenID Connect provider for tests."""
import json, threading, urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

class Provider:
    def __init__(self, users):
        self.users, self.codes = users, {}
        outer = self
        class H(BaseHTTPRequestHandler):
            def log_message(self, *a): pass
            def _json(self, obj, code=200):
                b = json.dumps(obj).encode(); self.send_response(code)
                self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b)))
                self.end_headers(); self.wfile.write(b)
            def do_GET(self):
                u = urllib.parse.urlparse(self.path); q = dict(urllib.parse.parse_qsl(u.query))
                if u.path == "/.well-known/openid-configuration":
                    return self._json({"issuer": outer.base, "authorization_endpoint": outer.base + "/authorize",
                                       "token_endpoint": outer.base + "/token", "userinfo_endpoint": outer.base + "/userinfo"})
                if u.path == "/authorize":     # auto-approve as the user named in login_hint-ish 'as' param
                    who = outer.next_user; code = "code-" + who
                    outer.codes[code] = (who, q["redirect_uri"], q["client_id"])
                    self.send_response(302)
                    self.send_header("Location", f"{q['redirect_uri']}?code={code}&state={urllib.parse.quote(q['state'])}")
                    return self.end_headers()
                if u.path == "/userinfo":
                    tok = self.headers.get("Authorization", "")[7:]
                    return self._json(outer.users[tok.removeprefix("at-")])
                self._json({"error": "not found"}, 404)
            def do_POST(self):
                body = dict(urllib.parse.parse_qsl(self.rfile.read(int(self.headers["Content-Length"])).decode()))
                who, redirect, cid = outer.codes.pop(body.get("code"), (None, None, None))
                if not who or body.get("client_secret") != "s3cret" or body.get("redirect_uri") != redirect:
                    return self._json({"error": "invalid_grant", "error_description": "bad code"}, 400)
                self._json({"access_token": "at-" + who, "token_type": "Bearer"})
        self.httpd = HTTPServer(("127.0.0.1", 0), H)
        self.base = f"http://127.0.0.1:{self.httpd.server_port}"
        self.next_user = None
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
