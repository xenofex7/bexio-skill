#!/usr/bin/env python3
"""tel.search.ch-Client (stdlib only).

Sucht im Schweizer Telefonbuch und gibt Treffer als JSON zurueck - die Felder
sind schon bexio-tauglich benannt (name_1, name_2, address, postcode, city,
phone_fixed, mail, ...), damit sich ein Treffer direkt per
`bexio.py post /2.0/contact` anlegen laesst.

Auth via API-Key aus der Umgebungsvariable SEARCHCH_API_KEY.

Beispiele:
  searchch.py "Hans Muster" --wo Zuerich
  searchch.py "Muster AG" --wo 8000 --firma
  searchch.py "044 123 45 67"
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

API_URL = "https://search.ch/tel/api/"
KEY_ENV = "SEARCHCH_API_KEY"


def _key():
    key = os.environ.get(KEY_ENV)
    if not key:
        sys.exit(
            f"Fehler: Umgebungsvariable {KEY_ENV} ist nicht gesetzt.\n"
            f"API-Key auf https://search.ch/tel/api/help bestellen und setzen:\n"
            f'  export {KEY_ENV}="dein-key"'
        )
    return key


def _local(tag):
    """Lokaler Tag-Name ohne Namespace ('{ns}name' -> 'name')."""
    return tag.rsplit("}", 1)[-1]


def _fetch(query, where, only, maxnum, lang):
    params = {"was": query, "key": _key(), "maxnum": maxnum, "lang": lang}
    if where:
        params["wo"] = where
    if only:  # 'privat' oder 'firma' -> nur diese Kategorie
        params[only] = "1"
    url = API_URL + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Accept": "application/xml"})
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.read().decode()
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")
        sys.exit(f"HTTP {e.code} {e.reason} bei search.ch\n{detail}")
    except urllib.error.URLError as e:
        sys.exit(f"Verbindungsfehler: {e.reason}")


def _entry_to_contact(entry):
    """Ein Atom-<entry> auf bexio-Contact-Felder mappen."""
    f = {}          # rohe tel:-Felder per lokalem Namen
    extras = {}     # tel:extra nach @type (fax, email, website, ...)
    for child in entry:
        name = _local(child.tag)
        if name == "extra":
            etype = next((v for k, v in child.attrib.items()
                          if _local(k) == "type"), "extra")
            extras[etype] = (child.text or "").strip()
        elif child.text and child.text.strip():
            f[name] = child.text.strip()

    is_org = f.get("type") == "organisation" or ("org" in f and "name" not in f)
    street = " ".join(p for p in (f.get("street"), f.get("streetno")) if p)

    contact = {
        "contact_type_id": 1 if is_org else 2,   # 1=Firma, 2=Person
        "name_1": f.get("org") if is_org else f.get("name", ""),
        "name_2": "" if is_org else f.get("firstname", ""),
        "address": street,
        "postcode": f.get("zip", ""),
        "city": f.get("city", ""),
        "canton": f.get("canton", ""),       # kein bexio-Feld, nur zur Info
        "phone_fixed": f.get("phone", ""),
        "mail": extras.get("email", ""),
        "url": extras.get("website", ""),
        "occupation": f.get("occupation", ""),  # nur zur Info
    }
    return {k: v for k, v in contact.items() if v not in ("", None)}


def main():
    p = argparse.ArgumentParser(description="tel.search.ch-Suche")
    p.add_argument("query", help="Name, Firma oder Telefonnummer (Parameter 'was')")
    p.add_argument("--wo", dest="where", help="Ort, PLZ, Strasse oder Kanton")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--privat", action="store_const", const="privat", dest="only",
                   help="nur Privateintraege")
    g.add_argument("--firma", action="store_const", const="firma", dest="only",
                   help="nur Firmeneintraege")
    p.add_argument("--max", type=int, default=10, dest="maxnum",
                   help="max. Treffer (default 10)")
    p.add_argument("--lang", default="de", help="de, fr, it, en (default de)")
    args = p.parse_args()

    xml = _fetch(args.query, args.where, args.only, args.maxnum, args.lang)
    root = ET.fromstring(xml)
    entries = [e for e in root.iter() if _local(e.tag) == "entry"]
    results = [_entry_to_contact(e) for e in entries]
    print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
