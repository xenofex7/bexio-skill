# bexio-skill

<p align="center">
  <a href="https://github.com/xenofex7/bexio-skill/tags"><img src="https://img.shields.io/github/v/tag/xenofex7/bexio-skill?sort=semver&label=version" alt="latest tag"></a>
  <a href="https://github.com/xenofex7/bexio-skill/blob/main/LICENSE"><img src="https://img.shields.io/github/license/xenofex7/bexio-skill" alt="license"></a>
  <img src="https://img.shields.io/badge/python-3.8+-blue?logo=python&logoColor=white" alt="python">
  <img src="https://img.shields.io/github/last-commit/xenofex7/bexio-skill" alt="last commit">
  <img src="https://img.shields.io/github/commit-activity/y/xenofex7/bexio-skill" alt="commit activity">
</p>

A Claude Code skill that controls [bexio](https://www.bexio.com) (Swiss business software) through its REST API. It lets Claude search, create and edit contacts and articles, and create, issue, fetch as PDF and send invoices and quotes - all from natural-language requests. The skill ships a dependency-free Python CLI plus reference docs that map the relevant endpoints and payloads.

## Features

- Manage contacts - search, create, edit, delete
- Manage articles (products and services), usable directly as invoice positions
- Create invoices and quotes with custom, article, text, subtotal and discount positions
- Issue documents, fetch the PDF, send by mail, record payments
- Reach any bexio endpoint via a generic `get` / `post` / `delete` / `search` CLI
- No dependencies - pure Python standard library, bearer-token auth

## Requirements

- Python 3.8+
- A bexio account with an API token (Settings -> API/Developer)
- Claude Code, to use it as a skill

## Installation

```bash
git clone https://github.com/xenofex7/bexio-skill.git
cd bexio-skill/skill

# 1. Set your bexio API token. Use ~/.zshenv (not ~/.zshrc) so it is
#    available to non-interactive shells too - that is what the skill runs in.
echo 'export BEXIO_API_TOKEN="your-token"' >> ~/.zshenv && source ~/.zshenv

# 2. Make the skill available to Claude Code
ln -s "$(pwd)" ~/.claude/skills/bexio
```

Verify the connection:

```bash
python3 scripts/bexio.py get /3.0/users
```

This prints the list of bexio users when the token and connection are valid.

## Configuration

| Variable            | Default | Description                                          |
|---------------------|---------|------------------------------------------------------|
| `BEXIO_API_TOKEN` * | -       | Bearer token for the bexio API, sent on every call   |

`*` required. Store it in `~/.zshenv` (not `~/.zshrc`) so it is available to non-interactive shells too, which is what the skill runs in.

## Usage

Once installed as a skill, just ask Claude in natural language - "create a contact for ...", "draft a quote for customer X over ...", "show me the open invoices". Claude drives the CLI under the hood and confirms any writing or sending action first.

Direct CLI use:

```bash
python3 scripts/bexio.py get    /2.0/contact --limit 5      # list (one page)
python3 scripts/bexio.py get    /2.0/contact --all          # all pages
python3 scripts/bexio.py search contact name_1 Muster       # search
python3 scripts/bexio.py post   /2.0/contact --data '{...}' # create / edit
python3 scripts/bexio.py delete /2.0/contact/42             # delete
```

See [SKILL.md](SKILL.md) for the workflow and [reference/api-notes.md](reference/api-notes.md) for fields, position types and action endpoints.

## Development

The client is a single standard-library file, [scripts/bexio.py](scripts/bexio.py) - no build step, no dependencies. Edit it directly.

Commit style: prefixes Add, Fix, Update, Remove, Refactor, Polish, imperative mood.

## Troubleshooting

### HTTP 404 on an endpoint that should exist

bexio splits its API across `/2.0/` and `/3.0/`. Most resources live under `/2.0/`, some newer ones (users, taxes) under `/3.0/`. Try the other version.

### HTTP 401 Unauthorized

The token is missing, invalid or expired. Check it with `echo "${BEXIO_API_TOKEN:+set}"` and regenerate it in bexio if needed.

## License

MIT, see [LICENSE](../LICENSE).
