---
name: bexio
description: Steuert bexio (Schweizer Business-Software) über die REST-API - Kontakte und Artikel suchen/anlegen/ändern und Rechnungen sowie Offerten erstellen, ausstellen, als PDF holen und versenden. Nutze diesen Skill, wenn der Nutzer etwas in bexio tun will (Kontakt, Kunde, Artikel, Produkt, Dienstleistung, Rechnung, Offerte, Quote, Invoice) oder bexio-Daten abfragen möchte.
---

# bexio

Dieser Skill steuert bexio über die REST-API. Auth läuft per API-Token (Bearer).
Alle Calls gehen über das CLI `scripts/bexio.py` - das übernimmt Auth, Basis-URL,
Pagination und Fehlermeldungen.

## Voraussetzung: Token

Der Token muss in der Umgebungsvariable `BEXIO_API_TOKEN` stehen.
Vor dem ersten Call prüfen:

```bash
echo "${BEXIO_API_TOKEN:+gesetzt}"
```

Ist er leer, den Nutzer bitten, in bexio unter **Einstellungen -> API/Entwickler**
einen API-Token zu erstellen und zu setzen:

```bash
export BEXIO_API_TOKEN="..."
```

## Das CLI

```bash
python3 scripts/bexio.py get    /2.0/contact --limit 5      # Liste (Seite)
python3 scripts/bexio.py get    /2.0/contact --all          # alle Seiten
python3 scripts/bexio.py get    /2.0/contact/42             # einzeln
python3 scripts/bexio.py search contact name_1 Muster       # Suche (criteria=like)
python3 scripts/bexio.py post   /2.0/contact --data '{...}' # anlegen/ändern
python3 scripts/bexio.py post   /2.0/kb_invoice --file inv.json # Body aus Datei
python3 scripts/bexio.py delete /2.0/contact/42             # löschen
```

`post` auf `/2.0/<res>/<id>` ist **edit**, auf `/2.0/<res>` ist **create**.
JSON kann inline (`--data`), aus Datei (`--file`) oder über stdin kommen.

## Wichtigste Regel: erst IDs auflösen

bexio-Objekte referenzieren andere per ID (`user_id`, `tax_id`, `account_id`,
`contact_id`, `unit_id` ...). Diese IDs sind pro Mandant unterschiedlich.
**Nie raten** - vor dem Erstellen die nötigen IDs über die Discovery-Endpoints holen
(siehe `reference/api-notes.md`), z.B.:

```bash
python3 scripts/bexio.py get /3.0/users        # user_id / owner_id
python3 scripts/bexio.py get /3.0/taxes       # tax_id (MwSt-Sätze)
python3 scripts/bexio.py get /2.0/accounts    # account_id (Kontenplan)
python3 scripts/bexio.py get /2.0/unit        # unit_id (Einheiten)
```

## Typische Abläufe

**Kontakt anlegen** (Person): `contact_type_id` 1=Firma, 2=Person; `name_1` = Firma
bzw. Nachname; `user_id`/`owner_id` aus `/3.0/users`.

**Artikel anlegen**: `intern_name` + `article_type_id` (1=Produkt, 2=Dienstleistung);
Verkaufspreis `sale_price`, MwSt `tax_income_id` aus `/3.0/taxes`. Artikel lassen sich
per `KbPositionArticle` direkt als Rechnungsposition verwenden.

**Rechnung erstellen** → ausstellen → versenden:
1. `contact_id` per `search` finden, IDs (user/tax/account) auflösen
2. `POST /2.0/kb_invoice` mit `positions`-Array → liefert die neue `id` (Status: Entwurf)
3. `POST /2.0/kb_invoice/{id}/issue` → ausstellen (offen)
4. `GET /2.0/kb_invoice/{id}/pdf` oder `POST /2.0/kb_invoice/{id}/send`

Offerten gehen analog über `/2.0/kb_offer` (zusätzlich `accept`/`reject`).

Genaue Felder, Positions-Typen, MwSt-Logik und Aktions-Endpoints stehen in
[reference/api-notes.md](reference/api-notes.md).

## Sicherheit

- Schreibende und versendende Aktionen (anlegen, ändern, ausstellen, **send**,
  löschen) vor der Ausführung kurz bestätigen lassen - das wirkt nach aussen
  (Kunde bekommt die Rechnung) bzw. ist schwer rückgängig.
- Bei Unsicherheit über eine ID lieber den Discovery-Endpoint abfragen statt raten.
