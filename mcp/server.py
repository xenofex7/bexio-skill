"""bexio MCP server.

Exposes the bexio REST API as MCP tools over Streamable HTTP, so Claude
(web, iOS app, or any MCP client) can drive bexio as a remote connector.

Auth model:
- BEXIO_API_TOKEN  - server-side bearer token for the bexio API itself
- MCP_AUTH_TOKEN   - shared secret clients must send as `Authorization: Bearer <token>`
                     (omit to disable the gate, e.g. behind a private network)
"""
import json
import os
import urllib.error
import urllib.parse
import urllib.request

import uvicorn
from mcp.server.fastmcp import FastMCP
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

BASE_URL = "https://api.bexio.com"
BEXIO_API_TOKEN = os.environ.get("BEXIO_API_TOKEN")
MCP_AUTH_TOKEN = os.environ.get("MCP_AUTH_TOKEN")
PORT = int(os.environ.get("PORT", "8080"))

mcp = FastMCP("bexio", host="0.0.0.0", port=PORT)


def _request(method: str, path: str, body=None, query=None):
    """Authenticated call against the bexio API. Returns parsed JSON or raises."""
    if not BEXIO_API_TOKEN:
        raise RuntimeError("BEXIO_API_TOKEN is not set on the server")
    url = BASE_URL + path
    if query:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(query)
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {BEXIO_API_TOKEN}")
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
                   mail: str = "", address: str = "", postcode: str = "",
                   city: str = "", phone_mobile: str = "",
                   user_id: int = 1, owner_id: int = 1) -> dict:
    """Create a contact. contact_type_id: 1=company, 2=person.
    name_1 is the company name or last name; name_2 the first name/addition."""
    body = {"contact_type_id": contact_type_id, "name_1": name_1,
            "name_2": name_2, "mail": mail, "address": address,
            "postcode": postcode, "city": city, "phone_mobile": phone_mobile,
            "user_id": user_id, "owner_id": owner_id}
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
    body = {"contact_id": contact_id, "user_id": user_id, "title": title,
            "mwst_type": mwst_type, "mwst_is_net": mwst_is_net,
            "positions": positions}
    if is_valid_from:
        body["is_valid_from"] = is_valid_from
    if header:
        body["header"] = header
    if footer:
        body["footer"] = footer
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
    body = {"contact_id": contact_id, "user_id": user_id, "title": title,
            "mwst_type": mwst_type, "mwst_is_net": mwst_is_net,
            "positions": positions}
    if is_valid_from:
        body["is_valid_from"] = is_valid_from
    if header:
        body["header"] = header
    if footer:
        body["footer"] = footer
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


# --- ASGI app with optional bearer gate ---

class BearerAuth(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if MCP_AUTH_TOKEN and request.headers.get("authorization") != f"Bearer {MCP_AUTH_TOKEN}":
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        return await call_next(request)


app = mcp.streamable_http_app()
app.add_middleware(BearerAuth)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
