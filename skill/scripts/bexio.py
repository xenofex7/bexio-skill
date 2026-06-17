#!/usr/bin/env python3
"""Schlanker bexio-API-Client (stdlib only).

Auth via Bearer-Token aus der Umgebungsvariable BEXIO_API_TOKEN.
Basis-URL: https://api.bexio.com

Beispiele:
  bexio.py get /2.0/contact --limit 5
  bexio.py get /2.0/contact --all
  bexio.py search contact name_1 Muster
  bexio.py post /2.0/contact --data '{"contact_type_id":2,"name_1":"Muster","user_id":1,"owner_id":1}'
  bexio.py post /2.0/kb_invoice --file rechnung.json
  bexio.py delete /2.0/contact/42
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE_URL = "https://api.bexio.com"
TOKEN_ENV = "BEXIO_API_TOKEN"


def _token():
    token = os.environ.get(TOKEN_ENV)
    if not token:
        sys.exit(
            f"Fehler: Umgebungsvariable {TOKEN_ENV} ist nicht gesetzt.\n"
            f"Token aus bexio holen (Einstellungen -> API) und setzen:\n"
            f'  export {TOKEN_ENV}="dein-token"'
        )
    return token


def _request(method, path, body=None, query=None):
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
        sys.exit(f"HTTP {e.code} {e.reason} bei {method} {path}\n{detail}")
    except urllib.error.URLError as e:
        sys.exit(f"Verbindungsfehler: {e.reason}")


def cmd_get(args):
    if args.all:
        results, offset = [], 0
        while True:
            page = _request("GET", args.path, query={"limit": 1000, "offset": offset})
            if not page:
                break
            results.extend(page)
            if len(page) < 1000:
                break
            offset += 1000
        _print(results)
        return
    query = {}
    if args.limit is not None:
        query["limit"] = args.limit
    if args.offset is not None:
        query["offset"] = args.offset
    _print(_request("GET", args.path, query=query or None))


def cmd_post(args):
    _print(_request("POST", args.path, body=_read_body(args)))


def cmd_delete(args):
    _print(_request("DELETE", args.path))


def cmd_search(args):
    path = f"/2.0/{args.resource}/search"
    body = [{"field": args.field, "value": args.value, "criteria": args.criteria}]
    _print(_request("POST", path, body=body))


def _read_body(args):
    if args.data:
        raw = args.data
    elif args.file:
        with open(args.file) as f:
            raw = f.read()
    elif not sys.stdin.isatty():
        raw = sys.stdin.read()
    else:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        sys.exit(f"Ungültiges JSON: {e}")


def _print(obj):
    print(json.dumps(obj, indent=2, ensure_ascii=False))


def main():
    p = argparse.ArgumentParser(description="bexio-API-Client")
    sub = p.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("get", help="GET-Request")
    g.add_argument("path", help="z.B. /2.0/contact")
    g.add_argument("--limit", type=int)
    g.add_argument("--offset", type=int)
    g.add_argument("--all", action="store_true", help="alle Seiten holen")
    g.set_defaults(func=cmd_get)

    po = sub.add_parser("post", help="POST-Request (create/edit/search)")
    po.add_argument("path")
    po.add_argument("--data", help="JSON-Body inline")
    po.add_argument("--file", help="JSON-Body aus Datei")
    po.set_defaults(func=cmd_post)

    d = sub.add_parser("delete", help="DELETE-Request")
    d.add_argument("path")
    d.set_defaults(func=cmd_delete)

    s = sub.add_parser("search", help="Suche auf einer Ressource")
    s.add_argument("resource", help="z.B. contact, kb_invoice, kb_offer")
    s.add_argument("field")
    s.add_argument("value")
    s.add_argument("--criteria", default="like", help="like, =, >, < ... (default: like)")
    s.set_defaults(func=cmd_search)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
