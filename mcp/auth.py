"""Minimal single-user OAuth 2.1 authorization server for the bexio MCP server.

Just enough of the spec for claude.ai's custom-connector flow: discovery,
dynamic client registration, an authorization-code grant with PKCE behind a
single password, and a token endpoint. Tokens live in memory (a restart means
one re-login). Access tokens carry a prefix so the MCP layer can tell an
OAuth-issued token apart from a passed-through bexio token.
"""
import base64
import hashlib
import os
import secrets
import time
import urllib.parse

from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse
from starlette.routing import Route

PUBLIC_URL = os.environ.get("PUBLIC_URL", "").rstrip("/")
OAUTH_PASSWORD = os.environ.get("OAUTH_PASSWORD")

ACCESS_PREFIX = "mcpat_"
REFRESH_PREFIX = "mcprt_"
ACCESS_TTL = 3600
REFRESH_TTL = 60 * 60 * 24 * 30
CODE_TTL = 600

_clients = {}   # client_id -> {"redirect_uris": [...]}
_codes = {}     # code -> {client_id, redirect_uri, code_challenge, exp}
_access = {}    # access_token -> exp
_refresh = {}   # refresh_token -> exp


def _now():
    return int(time.time())


def valid_access_token(token):
    exp = _access.get(token)
    return exp is not None and exp >= _now()


def _esc(v):
    return (v or "").replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")


# --- discovery ---

def _meta_pr(_req):
    return JSONResponse({
        "resource": f"{PUBLIC_URL}/mcp",
        "authorization_servers": [PUBLIC_URL],
    })


def _meta_as(_req):
    return JSONResponse({
        "issuer": PUBLIC_URL,
        "authorization_endpoint": f"{PUBLIC_URL}/authorize",
        "token_endpoint": f"{PUBLIC_URL}/token",
        "registration_endpoint": f"{PUBLIC_URL}/register",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": ["none"],
        "scopes_supported": ["bexio"],
    })


# --- dynamic client registration ---

async def _register(req):
    body = await req.json()
    client_id = "mcpc_" + secrets.token_urlsafe(16)
    redirect_uris = body.get("redirect_uris", [])
    _clients[client_id] = {"redirect_uris": redirect_uris}
    return JSONResponse({
        "client_id": client_id,
        "client_id_issued_at": _now(),
        "redirect_uris": redirect_uris,
        "token_endpoint_auth_method": "none",
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
    }, status_code=201)


# --- authorization endpoint (login + consent) ---

def _login_page(params, error=""):
    hidden = "".join(
        f'<input type="hidden" name="{_esc(k)}" value="{_esc(v)}">'
        for k, v in params.items())
    err = f'<p style="color:#c00">{_esc(error)}</p>' if error else ""
    return HTMLResponse(
        '<!doctype html><html><head><meta name="viewport" '
        'content="width=device-width,initial-scale=1"><title>bexio MCP</title></head>'
        '<body style="font-family:sans-serif;max-width:340px;margin:80px auto;padding:0 16px">'
        f'<h2>bexio MCP login</h2>{err}'
        '<form method="post" action="/authorize">' + hidden +
        '<input type="password" name="password" placeholder="Password" autofocus '
        'style="width:100%;box-sizing:border-box;padding:10px;font-size:16px">'
        '<button type="submit" style="margin-top:12px;padding:10px 18px;font-size:16px">'
        'Authorize</button></form></body></html>')


async def _authorize(req):
    if req.method == "GET":
        params = dict(req.query_params)
        if params.get("response_type") != "code" or not params.get("client_id") \
                or not params.get("redirect_uri") or not params.get("code_challenge"):
            return JSONResponse({"error": "invalid_request"}, status_code=400)
        return _login_page(params)

    form = dict(await req.form())
    password = form.pop("password", "")
    client_id = form.get("client_id")
    redirect_uri = form.get("redirect_uri")
    client = _clients.get(client_id)
    if not client or redirect_uri not in client["redirect_uris"]:
        return JSONResponse({"error": "invalid_client"}, status_code=400)
    if not OAUTH_PASSWORD or not secrets.compare_digest(password, OAUTH_PASSWORD):
        return _login_page(form, "Wrong password")

    code = secrets.token_urlsafe(32)
    _codes[code] = {"client_id": client_id, "redirect_uri": redirect_uri,
                    "code_challenge": form.get("code_challenge", ""), "exp": _now() + CODE_TTL}
    sep = "&" if "?" in redirect_uri else "?"
    url = f"{redirect_uri}{sep}code={urllib.parse.quote(code)}"
    if form.get("state"):
        url += "&state=" + urllib.parse.quote(form["state"])
    return RedirectResponse(url, status_code=302)


# --- token endpoint ---

def _verify_pkce(verifier, challenge):
    digest = hashlib.sha256(verifier.encode()).digest()
    calc = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return secrets.compare_digest(calc, challenge)


def _issue():
    at = ACCESS_PREFIX + secrets.token_urlsafe(32)
    rt = REFRESH_PREFIX + secrets.token_urlsafe(32)
    _access[at] = _now() + ACCESS_TTL
    _refresh[rt] = _now() + REFRESH_TTL
    return JSONResponse({"access_token": at, "token_type": "Bearer",
                         "expires_in": ACCESS_TTL, "refresh_token": rt, "scope": "bexio"})


async def _token(req):
    form = dict(await req.form())
    grant = form.get("grant_type")
    if grant == "authorization_code":
        rec = _codes.pop(form.get("code", ""), None)
        if not rec or rec["exp"] < _now() or rec["redirect_uri"] != form.get("redirect_uri"):
            return JSONResponse({"error": "invalid_grant"}, status_code=400)
        if rec["code_challenge"] and not _verify_pkce(form.get("code_verifier", ""), rec["code_challenge"]):
            return JSONResponse({"error": "invalid_grant"}, status_code=400)
        return _issue()
    if grant == "refresh_token":
        rt = form.get("refresh_token", "")
        if _refresh.pop(rt, 0) < _now():
            return JSONResponse({"error": "invalid_grant"}, status_code=400)
        return _issue()
    return JSONResponse({"error": "unsupported_grant_type"}, status_code=400)


routes = [
    Route("/.well-known/oauth-protected-resource", _meta_pr),
    Route("/.well-known/oauth-protected-resource/mcp", _meta_pr),
    Route("/.well-known/oauth-authorization-server", _meta_as),
    Route("/.well-known/oauth-authorization-server/mcp", _meta_as),
    Route("/register", _register, methods=["POST"]),
    Route("/authorize", _authorize, methods=["GET", "POST"]),
    Route("/token", _token, methods=["POST"]),
]
