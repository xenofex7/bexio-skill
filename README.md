# bexio-skill

Ein Claude-Code-Skill, um bexio (Schweizer Business-Software) über die REST-API zu
steuern: Kontakte suchen/anlegen/ändern und Rechnungen sowie Offerten erstellen,
ausstellen, als PDF holen und versenden.

## Aufbau

```
SKILL.md                 Manifest + Anleitung (was Claude liest)
scripts/bexio.py         API-Client (stdlib, kein pip nötig)
reference/api-notes.md   Felder, Positions-Typen, MwSt, Aktions-Endpoints
```

## Einrichtung

1. **API-Token** in bexio erstellen (Einstellungen -> API/Entwickler) und setzen:

   ```bash
   export BEXIO_API_TOKEN="..."
   ```

   Am besten dauerhaft in `~/.zshrc` ablegen.

2. **Skill installieren** - Ordner dorthin verlinken/kopieren, wo Claude Code Skills
   findet (global für alle Projekte):

   ```bash
   ln -s "$(pwd)" ~/.claude/skills/bexio
   ```

   Danach steht der Skill als `/bexio` bzw. automatisch bei bexio-Anfragen bereit.

## Test

```bash
python3 scripts/bexio.py get /2.0/user
```

Liefert die Liste der bexio-Benutzer, wenn Token und Verbindung stimmen.
