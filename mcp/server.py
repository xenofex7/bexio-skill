"""bexio MCP server.

Exposes the bexio REST API as MCP tools over Streamable HTTP, so Claude
(web, iOS app, or any MCP client) can drive bexio as a remote connector.

Auth model - token pass-through (no secret stored on the server):
The client sends the bexio API token as `Authorization: Bearer <token>` on every
request (configured once in the Claude connector). The server forwards it to bexio
and never persists it. BEXIO_API_TOKEN may be set as an optional server-side
fallback for single-user self-hosting.
"""
import contextvars
import json
import os
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

import uvicorn
from mcp.server.fastmcp import FastMCP
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

import auth as oauth

BASE_URL = "https://api.bexio.com"
BEXIO_API_TOKEN = os.environ.get("BEXIO_API_TOKEN")  # optional fallback
SEARCHCH_API_KEY = os.environ.get("SEARCHCH_API_KEY")  # for the phonebook tool
API_URL_TEL = "https://search.ch/tel/api/"
PORT = int(os.environ.get("PORT", "8080"))

# Per-request bexio token, set by the TokenForward middleware from the incoming
# Authorization header. Held only for the duration of the request, never stored.
_request_token = contextvars.ContextVar("bexio_token", default=None)


def _token():
    token = _request_token.get() or BEXIO_API_TOKEN
    if not token:
        raise RuntimeError(
            "No bexio token: send it as 'Authorization: Bearer <token>' "
            "or set BEXIO_API_TOKEN on the server")
    return token

mcp = FastMCP("bexio", host="0.0.0.0", port=PORT)


def _request(method: str, path: str, body=None, query=None):
    """Authenticated call against the bexio API. Returns parsed JSON or raises."""
    url = BASE_URL + path
    if query:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(query)
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {_token()}")
    req.add_header("Accept", "application/json")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read().decode()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")
        raise RuntimeError(f"bexio HTTP {e.code} {e.reason} at {method} {path}: {detail}")


# --- Reference / discovery (resolve ids before creating documents) ---

@mcp.tool()
def list_users() -> list:
    """List bexio users. Use the returned id for user_id / owner_id."""
    return _request("GET", "/3.0/users")


@mcp.tool()
def list_taxes() -> list:
    """List VAT/tax rates. Use the returned id for tax_id on positions."""
    return _request("GET", "/3.0/taxes")


@mcp.tool()
def list_accounts() -> list:
    """List the chart of accounts. Use the returned id for account_id on positions."""
    return _request("GET", "/2.0/accounts")


@mcp.tool()
def list_units() -> list:
    """List units (Stk, h, ...). Use the returned id for unit_id on positions."""
    return _request("GET", "/2.0/unit")


@mcp.tool()
def list_countries() -> list:
    """List countries. Use the returned id for country_id on contacts
    (Switzerland is id 1)."""
    return _request("GET", "/2.0/country")


# --- Contacts ---

@mcp.tool()
def search_contacts(query: str, field: str = "name_1") -> list:
    """Search contacts by a field (default name_1) using a 'like' match.
    Other useful fields: name_2, mail, nr, city, postcode."""
    return _request("POST", "/2.0/contact/search",
                    body=[{"field": field, "value": query, "criteria": "like"}])


@mcp.tool()
def get_contact(contact_id: int) -> dict:
    """Fetch a single contact by id."""
    return _request("GET", f"/2.0/contact/{contact_id}")


@mcp.tool()
def create_contact(name_1: str, contact_type_id: int = 2, name_2: str = "",
                   mail: str = "", street_name: str = "", house_number: str = "",
                   postcode: str = "", city: str = "", country_id: int = 1,
                   phone_fixed: str = "", phone_mobile: str = "", url: str = "",
                   user_id: int = 1, owner_id: int = 1) -> dict:
    """Create a contact. contact_type_id: 1=company, 2=person.
    name_1 is the company name or last name; name_2 the first name/addition.
    The street goes in street_name + house_number (the combined `address` field
    is read-only in bexio - sending it returns HTTP 422). country_id defaults to
    1 (Switzerland); resolve others via list_countries. Maps 1:1 to the fields
    from search_phonebook. Only non-empty optional fields are sent."""
    body = {"contact_type_id": contact_type_id, "name_1": name_1,
            "country_id": country_id, "user_id": user_id, "owner_id": owner_id}
    optional = {"name_2": name_2, "mail": mail, "street_name": street_name,
                "house_number": house_number, "postcode": postcode, "city": city,
                "phone_fixed": phone_fixed, "phone_mobile": phone_mobile, "url": url}
    body.update({k: v for k, v in optional.items() if v})
    return _request("POST", "/2.0/contact", body=body)


@mcp.tool()
def update_contact(contact_id: int, fields: dict) -> dict:
    """Update a contact. bexio expects the full object - fetch with get_contact,
    merge your changes into `fields`, then pass it here."""
    return _request("POST", f"/2.0/contact/{contact_id}", body=fields)


@mcp.tool()
def delete_contact(contact_id: int) -> dict:
    """Delete a contact by id. Irreversible."""
    return _request("DELETE", f"/2.0/contact/{contact_id}")


# --- Articles ---

@mcp.tool()
def search_articles(query: str, field: str = "intern_name") -> list:
    """Search articles (products/services) by a field using a 'like' match."""
    return _request("POST", "/2.0/article/search",
                    body=[{"field": field, "value": query, "criteria": "like"}])


@mcp.tool()
def get_article(article_id: int) -> dict:
    """Fetch a single article by id."""
    return _request("GET", f"/2.0/article/{article_id}")


# --- Phonebook lookup (tel.search.ch) ---

def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _entry_to_contact(entry) -> dict:
    """Map an Atom <entry> from tel.search.ch onto bexio contact fields."""
    f, extras = {}, {}
    for child in entry:
        name = _local(child.tag)
        if name == "extra":
            etype = next((v for k, v in child.attrib.items()
                          if _local(k) == "type"), "extra")
            extras[etype] = (child.text or "").strip()
        elif child.text and child.text.strip():
            f[name] = child.text.strip()
    is_org = f.get("type") == "organisation" or ("org" in f and "name" not in f)
    contact = {
        "contact_type_id": 1 if is_org else 2,
        "name_1": f.get("org") if is_org else f.get("name", ""),
        "name_2": "" if is_org else f.get("firstname", ""),
        "street_name": f.get("street", ""),     # bexio: address is read-only,
        "house_number": f.get("streetno", ""),  # write street via these two
        "postcode": f.get("zip", ""),
        "city": f.get("city", ""), "canton": f.get("canton", ""),
        "phone_fixed": f.get("phone", ""), "mail": extras.get("email", ""),
        "url": extras.get("website", ""), "occupation": f.get("occupation", ""),
    }
    return {k: v for k, v in contact.items() if v not in ("", None)}


@mcp.tool()
def search_phonebook(query: str, where: str = "", only: str = "") -> list:
    """Look up a person or company in the Swiss phone book (tel.search.ch).
    Use this AFTER search_contacts returns nothing, to find a new contact's
    address and phone. query: name, company or phone number; where: city, zip,
    street or canton; only: '' (both), 'privat' or 'firma'. Returns candidates
    with bexio-ready fields (name_1, name_2, address, postcode, city,
    phone_fixed, mail, ...) - confirm one, then pass its fields to create_contact."""
    if not SEARCHCH_API_KEY:
        raise RuntimeError("Set SEARCHCH_API_KEY on the server to use search_phonebook.")
    params = {"was": query, "key": SEARCHCH_API_KEY, "maxnum": 10, "lang": "de"}
    if where:
        params["wo"] = where
    if only in ("privat", "firma"):
        params[only] = "1"
    url = API_URL_TEL + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Accept": "application/xml"})
    try:
        with urllib.request.urlopen(req) as resp:
            xml = resp.read().decode()
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"search.ch HTTP {e.code} {e.reason}: {e.read().decode(errors='replace')}")
    root = ET.fromstring(xml)
    return [_entry_to_contact(e) for e in root.iter() if _local(e.tag) == "entry"]


# --- Invoices (kb_invoice) ---

@mcp.tool()
def list_invoices(limit: int = 20) -> list:
    """List invoices (newest first not guaranteed); use limit to cap the page."""
    return _request("GET", "/2.0/kb_invoice", query={"limit": limit})


@mcp.tool()
def get_invoice(invoice_id: int) -> dict:
    """Fetch a single invoice by id."""
    return _request("GET", f"/2.0/kb_invoice/{invoice_id}")


@mcp.tool()
def create_invoice(contact_id: int, positions: list, title: str = "",
                   user_id: int = 1, mwst_type: int = 0, mwst_is_net: bool = True,
                   is_valid_from: str = "", header: str = "", footer: str = "") -> dict:
    """Create an invoice as a draft. positions is a list of position dicts, e.g.
    {"type":"KbPositionCustom","amount":"1","unit_price":"100.00","account_id":<id>,"tax_id":<id>,"text":"..."}.
    Resolve account_id/tax_id/unit_id via the list_* tools first.
    mwst_type: 0=incl. VAT, 1=excl. VAT, 2=VAT-exempt. Returns the created draft."""
    body = {"contact_id": contact_id, "user_id": user_id,
            "mwst_type": mwst_type, "mwst_is_net": mwst_is_net,
            "positions": positions}
    for key, val in (("title", title), ("is_valid_from", is_valid_from),
                     ("header", header), ("footer", footer)):
        if val:
            body[key] = val
    return _request("POST", "/2.0/kb_invoice", body=body)


@mcp.tool()
def issue_invoice(invoice_id: int) -> dict:
    """Issue a draft invoice (sets it to open). Required before sending."""
    return _request("POST", f"/2.0/kb_invoice/{invoice_id}/issue")


@mcp.tool()
def get_invoice_pdf(invoice_id: int) -> dict:
    """Fetch the invoice PDF. Returns metadata plus base64 content."""
    return _request("GET", f"/2.0/kb_invoice/{invoice_id}/pdf")


@mcp.tool()
def send_invoice(invoice_id: int, recipient_email: str = "", subject: str = "",
                 message: str = "", mark_as_open: bool = True) -> dict:
    """Send the invoice to the customer by e-mail. This sends a REAL mail -
    confirm with the user before calling. Empty fields fall back to bexio defaults."""
    body = {"mark_as_open": mark_as_open}
    if recipient_email:
        body["recipient_email"] = recipient_email
    if subject:
        body["subject"] = subject
    if message:
        body["message"] = message
    return _request("POST", f"/2.0/kb_invoice/{invoice_id}/send", body=body)


@mcp.tool()
def update_invoice(invoice_id: int, fields: dict) -> dict:
    """Edit an invoice (usually only sensible while it is a draft). bexio expects
    the full object - fetch with get_invoice, merge your changes into `fields`
    (e.g. a new `positions` list or `is_valid_from`), then pass it here."""
    return _request("POST", f"/2.0/kb_invoice/{invoice_id}", body=fields)


@mcp.tool()
def delete_invoice(invoice_id: int) -> dict:
    """Delete an invoice. Only works while it is still a DRAFT (issued invoices
    must be cancelled instead). Irreversible - confirm with the user first."""
    return _request("DELETE", f"/2.0/kb_invoice/{invoice_id}")


@mcp.tool()
def cancel_invoice(invoice_id: int) -> dict:
    """Cancel an already-issued invoice (sets it to cancelled). Use this instead
    of delete_invoice once an invoice has been issued. Confirm with the user first."""
    return _request("POST", f"/2.0/kb_invoice/{invoice_id}/cancel")


# --- Quotes / offers (kb_offer) ---

@mcp.tool()
def list_quotes(limit: int = 20) -> list:
    """List quotes/offers; use limit to cap the page."""
    return _request("GET", "/2.0/kb_offer", query={"limit": limit})


@mcp.tool()
def get_quote(quote_id: int) -> dict:
    """Fetch a single quote by id."""
    return _request("GET", f"/2.0/kb_offer/{quote_id}")


@mcp.tool()
def create_quote(contact_id: int, positions: list, title: str = "",
                 user_id: int = 1, mwst_type: int = 0, mwst_is_net: bool = True,
                 is_valid_from: str = "", header: str = "", footer: str = "") -> dict:
    """Create a quote/offer as a draft. Same position structure as create_invoice."""
    body = {"contact_id": contact_id, "user_id": user_id,
            "mwst_type": mwst_type, "mwst_is_net": mwst_is_net,
            "positions": positions}
    for key, val in (("title", title), ("is_valid_from", is_valid_from),
                     ("header", header), ("footer", footer)):
        if val:
            body[key] = val
    return _request("POST", "/2.0/kb_offer", body=body)


@mcp.tool()
def issue_quote(quote_id: int) -> dict:
    """Issue a draft quote (sets it to open)."""
    return _request("POST", f"/2.0/kb_offer/{quote_id}/issue")


@mcp.tool()
def accept_quote(quote_id: int) -> dict:
    """Mark a quote as accepted."""
    return _request("POST", f"/2.0/kb_offer/{quote_id}/accept")


@mcp.tool()
def reject_quote(quote_id: int) -> dict:
    """Mark a quote as rejected."""
    return _request("POST", f"/2.0/kb_offer/{quote_id}/reject")


@mcp.tool()
def get_quote_pdf(quote_id: int) -> dict:
    """Fetch the quote PDF. Returns metadata plus base64 content."""
    return _request("GET", f"/2.0/kb_offer/{quote_id}/pdf")


@mcp.tool()
def update_quote(quote_id: int, fields: dict) -> dict:
    """Edit a quote (usually only sensible while it is a draft). bexio expects
    the full object - fetch with get_quote, merge your changes into `fields`
    (e.g. a new `positions` list or `is_valid_from`), then pass it here."""
    return _request("POST", f"/2.0/kb_offer/{quote_id}", body=fields)


@mcp.tool()
def delete_quote(quote_id: int) -> dict:
    """Delete a quote. Best used while it is still a draft. Irreversible -
    confirm with the user first."""
    return _request("DELETE", f"/2.0/kb_offer/{quote_id}")


# --- ASGI app with optional bearer gate ---

def _challenge():
    """401 that tells claude.ai where to start the OAuth flow."""
    return Response(status_code=401, headers={
        "WWW-Authenticate": f'Bearer resource_metadata="{oauth.PUBLIC_URL}'
                            f'/.well-known/oauth-protected-resource"'})


class AuthGate(BaseHTTPMiddleware):
    """Guards the /mcp endpoint. Two ways in:
    - an OAuth access token we issued (claude.ai) -> use the server-side bexio token
    - any other bearer (Claude Code) -> pass it through to bexio as-is
    No token -> 401 with a pointer to the OAuth metadata."""
    async def dispatch(self, request, call_next):
        if request.url.path.startswith("/mcp"):
            header = request.headers.get("authorization", "")
            token = header[7:].strip() if header.lower().startswith("bearer ") else ""
            if not token:
                return _challenge()
            if token.startswith(oauth.ACCESS_PREFIX):
                if not oauth.valid_access_token(token):
                    return _challenge()
                _request_token.set(BEXIO_API_TOKEN)
            else:
                _request_token.set(token)
        return await call_next(request)


app = mcp.streamable_http_app()
app.add_middleware(AuthGate)
for _route in oauth.routes:
    app.router.routes.append(_route)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
