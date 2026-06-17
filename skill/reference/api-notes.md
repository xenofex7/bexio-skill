# bexio API - Referenz

Offizielle Doku: **https://docs.bexio.com/** (massgebliche Quelle für alle Endpunkte).

Basis-URL: `https://api.bexio.com`. Auth: `Authorization: Bearer <token>`.
Die meisten Ressourcen liegen unter `/2.0/...`, einige neuere (z.B. Steuern) unter
`/3.0/...`. Bei einem 404 die andere Version probieren bzw. auf docs.bexio.com nachsehen.

Endpunkte hier wurden am 17.06.2026 verifiziert (live gegen die API + Abgleich mit
dem Client `codebar-ag/laravel-bexio`). Einzige Ausnahme: `POST /2.0/kb_invoice/{id}/send`
ist laut bexio-Doku korrekt, liess sich aber nicht ohne echten Mail-Versand gegenprüfen.

## Discovery-Endpoints (IDs auflösen)

| Zweck | Endpoint |
|---|---|
| Benutzer (`user_id`, `owner_id`) | `GET /3.0/users` |
| MwSt-Sätze (`tax_id`) | `GET /3.0/taxes` |
| Kontenplan (`account_id`) | `GET /2.0/accounts` |
| Einheiten (`unit_id`, z.B. Stk/h) | `GET /2.0/unit` |
| Währungen (`currency_id`) | `GET /2.0/currency` |
| Zahlungskonditionen (`payment_type_id`) | `GET /2.0/payment_type` |
| Sprachen (`language_id`) | `GET /2.0/language` |
| Länder (`country_id`) | `GET /2.0/country` |
| Artikel (`article_id`) | `GET /2.0/article` (siehe eigener Abschnitt) |
| Projekte (`project_id`) | `GET /2.0/pr_project` (braucht Projekt-Berechtigung, sonst 403) |
| Kontaktgruppen | `GET /2.0/contact_group` |

## Suche

`POST /2.0/<res>/search` mit einem Array von Bedingungen (UND-verknüpft):

```json
[{ "field": "name_1", "value": "Muster AG", "criteria": "like" }]
```

`criteria`: `=`, `equal`, `not_equal`, `greater_than`, `less_than`, `greater_equal`,
`less_equal`, `like`, `not_like`, `is_null`, `not_null`, `in`, `not_in`.
Das CLI hat dafür `bexio.py search <res> <field> <value> [--criteria ...]`.

## Kontakt (`/2.0/contact`)

Felder beim Erstellen (`POST /2.0/contact`):

| Feld | Hinweis |
|---|---|
| `contact_type_id` | **Pflicht.** 1 = Firma, 2 = Person |
| `name_1` | **Pflicht.** Firmenname bzw. Nachname |
| `name_2` | Zusatz bzw. Vorname |
| `user_id` | **Pflicht.** Verantwortlicher (aus `/3.0/users`) |
| `owner_id` | **Pflicht.** Eigentümer (aus `/3.0/users`) |
| `street_name`, `house_number` | Strasse + Nr. **getrennt.** Das kombinierte `address` ist **read-only** (wird daraus berechnet) - beim Schreiben ignoriert bzw. abgelehnt |
| `address_addition`, `postcode`, `city` | Adresszusatz, PLZ, Ort |
| `country_id` | aus `/2.0/country` (Schweiz finden, nicht raten) |
| `mail`, `phone_fixed`, `phone_mobile` | Kontaktdaten |
| `language_id`, `salutation_id`, `contact_group_ids` | optional |

Beispiel:

```json
{
  "contact_type_id": 2,
  "name_1": "Muster",
  "name_2": "Hans",
  "mail": "hans@example.ch",
  "street_name": "Musterweg",
  "house_number": "1",
  "postcode": "8000",
  "city": "Zürich",
  "country_id": 1,
  "user_id": 1,
  "owner_id": 1
}
```

Ändern: `POST /2.0/contact/{id}` mit den zu ändernden Feldern (bexio erwartet beim
Edit i.d.R. das ganze Objekt - erst `GET` holen, anpassen, zurückschicken).

## Telefonbuch-Suche (tel.search.ch)

Externe API, um neue Kontakte im Schweizer Telefonbuch zu finden, wenn sie in
bexio noch fehlen. Eigener Client `scripts/searchch.py`, Key in `SEARCHCH_API_KEY`.
Doku: https://search.ch/tel/api/help. Antwort ist ein Atom/XML-Feed; das Script
parst ihn und gibt die Treffer direkt mit bexio-Contact-Feldnamen aus.

```bash
python3 scripts/searchch.py "Hans Muster" --wo Zürich   # was + wo
python3 scripts/searchch.py "Muster AG" --wo 8000 --firma --max 5
```

Mapping search.ch (tel:-Feld) → bexio-Contact:

| search.ch | bexio | Hinweis |
|---|---|---|
| `type` = organisation/person | `contact_type_id` | 1 = Firma, 2 = Person |
| `org` (Firma) / `name` (Person) | `name_1` | Firmenname bzw. Nachname |
| `firstname` | `name_2` | nur Person |
| `street` | `street_name` | bexio: `address` ist read-only, Strasse getrennt schreiben |
| `streetno` | `house_number` | |
| `zip` | `postcode` | |
| `city` | `city` | |
| `phone` | `phone_fixed` | |
| `extra type=email` | `mail` | |
| `extra type=website` | `url` | |
| `canton`, `occupation` | - | nur Info, **nicht** in den POST-Body |

Für `country_id` ist kein search.ch-Wert vorhanden - bei Bedarf Schweiz über
`/2.0/country` auflösen. `user_id`/`owner_id` wie üblich vor dem Anlegen setzen.

## Artikel (`/2.0/article`)

Produkte und Dienstleistungen. CRUD + `search` wie bei Kontakten
(`GET/POST /2.0/article`, `POST /2.0/article/search`, `GET/POST/DELETE /2.0/article/{id}`).

Felder beim Erstellen (`POST /2.0/article`):

| Feld | Hinweis |
|---|---|
| `user_id` | **Pflicht.** aus `/3.0/users` |
| `intern_name` | **Pflicht.** Bezeichnung des Artikels |
| `article_type_id` | 1 = physisches Produkt (lagerbar), 2 = Dienstleistung |
| `intern_code` | Artikelnummer (eindeutig) |
| `intern_description` | Beschreibung |
| `purchase_price` | Einkaufspreis (String) |
| `sale_price` | Verkaufspreis (String) |
| `currency_id` | aus `/2.0/currency` |
| `tax_income_id` | MwSt beim Verkauf, aus `/3.0/taxes` |
| `tax_id` | MwSt beim Einkauf (optional) |
| `unit_id` | Einheit, aus `/2.0/unit` |
| `is_stock` | `true` = Lagerbewirtschaftung aktiv |
| `stock_id`, `stock_place_id` | Lager/Lagerplatz (wenn `is_stock`) |
| `stock_nr`, `stock_min_nr` | Bestand / Mindestbestand |
| `contact_id` | Lieferant (optional) |
| `width`, `height`, `depth`, `weight`, `volume` | Masse (optional) |

Beispiel (Dienstleistung):

```json
{
  "user_id": 1,
  "intern_name": "Beratung pro Stunde",
  "article_type_id": 2,
  "intern_code": "BER-001",
  "sale_price": "150.00",
  "tax_income_id": 1,
  "unit_id": 1,
  "is_stock": false
}
```

Lagerartikel zusätzlich mit `"article_type_id": 1`, `"is_stock": true` und
`stock_id`/`stock_nr`. Lagerorte und Lager: `GET /2.0/stock_area` bzw.
`GET /2.0/stock_location`. Artikel lassen sich als Position per
`KbPositionArticle` (Feld `article_id`) direkt in Rechnungen/Offerten ziehen.

## Rechnung (`/2.0/kb_invoice`) und Offerte (`/2.0/kb_offer`)

Beide haben dieselbe Struktur. Kopf-Felder beim Erstellen:

| Feld | Hinweis |
|---|---|
| `contact_id` | **Pflicht.** Empfänger (per `search` finden) |
| `user_id` | **Pflicht.** aus `/3.0/users` |
| `title` | Titel des Dokuments |
| `contact_sub_id` | Ansprechpartner (optional) |
| `project_id` | Projektzuordnung (optional) |
| `language_id`, `currency_id`, `payment_type_id`, `bank_account_id` | optional, sonst Defaults |
| `header`, `footer` | Frei-Text oben/unten |
| `mwst_type` | 0 = inkl. MwSt, 1 = exkl. MwSt, 2 = MwSt-frei/0% |
| `mwst_is_net` | `true` = Positionspreise sind netto |
| `is_valid_from` | Datum `YYYY-MM-DD` (Rechnungs-/Offertdatum) |
| `is_valid_to` | Fälligkeits-/Gültigkeitsdatum `YYYY-MM-DD` |
| `reference` | Referenz/Betreff |
| `positions` | Array (siehe unten) |

### Positions-Typen (`type`)

```json
{ "type": "KbPositionCustom", "amount": "2", "unit_id": 1, "unit_price": "150.00",
  "account_id": 1, "tax_id": 1, "text": "Beratung", "discount_in_percent": "0" }

{ "type": "KbPositionArticle", "amount": "1", "article_id": 7, "unit_price": "99.00",
  "account_id": 1, "tax_id": 1, "text": "Optionaler Zusatztext" }

{ "type": "KbPositionText",     "text": "Zwischenüberschrift", "show_pos_nr": false }
{ "type": "KbPositionSubtotal", "text": "Zwischensumme" }
{ "type": "KbPositionDiscount", "text": "Rabatt", "value": "10", "discount_in_percent": true }
{ "type": "KbPositionPagebreak" }
```

`amount`, `unit_price`, `value` als Strings übergeben (bexio-Konvention).
`account_id` und `tax_id` aus den Discovery-Endpoints - **nicht raten**.

### Aktionen nach dem Erstellen

Beim Erstellen entsteht ein **Entwurf**. Danach:

| Aktion | Rechnung | Offerte |
|---|---|---|
| Ausstellen | `POST /2.0/kb_invoice/{id}/issue` | `POST /2.0/kb_offer/{id}/issue` |
| PDF holen | `GET /2.0/kb_invoice/{id}/pdf` | `GET /2.0/kb_offer/{id}/pdf` |
| Per Mail senden | `POST /2.0/kb_invoice/{id}/send` | `POST /2.0/kb_offer/{id}/send` |
| Zahlung erfassen | `POST /2.0/kb_invoice/{id}/payment` | - |
| Annehmen/Ablehnen | - | `POST /2.0/kb_offer/{id}/accept` bzw. `/reject` |
| Stornieren | `POST /2.0/kb_invoice/{id}/cancel` | - |

`send` verschickt eine echte Mail an den Kunden - immer vorher bestätigen lassen.

### Minimal-Beispiel Rechnung

```json
{
  "title": "Rechnung",
  "contact_id": 123,
  "user_id": 1,
  "mwst_type": 0,
  "mwst_is_net": true,
  "is_valid_from": "2026-06-16",
  "positions": [
    { "type": "KbPositionCustom", "amount": "1", "unit_price": "1000.00",
      "account_id": 1, "tax_id": 1, "text": "Dienstleistung" }
  ]
}
```
