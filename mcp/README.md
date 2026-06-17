# bexio-mcp

An MCP server that exposes the bexio REST API as tools over Streamable HTTP. Run it as a remote connector so Claude can drive bexio anywhere - the claude.ai web app and the iOS app (via OAuth), or Claude Code (via a passed-through token).

## Features

- Contacts - search, get, create, update, delete
- Articles - search, get
- Invoices - list, get, create, issue, send by mail, PDF
- Quotes - list, get, create, issue, accept, reject, PDF
- Reference helpers - users, taxes, accounts, units (to resolve ids)
- Phone-book lookup - find unknown contacts via tel.search.ch (`search_phonebook`)
- Two auth modes: OAuth for claude.ai, bearer pass-through for Claude Code

## Authentication

The server accepts two ways in, decided per request:

- **OAuth (claude.ai web + iOS app)** - claude.ai only supports OAuth for custom connectors. The server runs a minimal single-user OAuth 2.1 flow (dynamic client registration, PKCE, one password). Once logged in, it calls bexio with the server-side `BEXIO_API_TOKEN`. So in this mode the bexio token lives on the server, gated behind your OAuth login and TLS.
- **Pass-through (Claude Code)** - the client sends its own bexio token as `Authorization: Bearer <token>` and the server forwards it, storing nothing. OAuth-issued tokens are prefixed (`mcpat_`) so the two modes never collide.

A request to `/mcp` with no bearer gets a `401` pointing to the OAuth metadata, which is what kicks off the claude.ai login.

## Requirements

- Docker and Docker Compose v2
- A bexio API token
- For OAuth: a public HTTPS URL (reverse proxy with TLS, e.g. Nginx Proxy Manager)

## Installation

```bash
cd mcp
cp .env.example .env   # for OAuth: set BEXIO_API_TOKEN, PUBLIC_URL, OAUTH_PASSWORD
docker compose up -d --build
```

The server listens on `http://localhost:8080/mcp`. Put it behind your reverse proxy with TLS at the `PUBLIC_URL` you configured.

## Configuration

| Variable          | Default | Description                                                          |
|-------------------|---------|----------------------------------------------------------------------|
| `BEXIO_API_TOKEN` | -       | bexio token used in OAuth mode (and as pass-through fallback)        |
| `PUBLIC_URL`      | -       | Public HTTPS base URL, no trailing slash. Required for OAuth         |
| `OAUTH_PASSWORD`  | -       | Password for the OAuth login screen (single user)                   |
| `SEARCHCH_API_KEY`| -       | API key for tel.search.ch; enables the `search_phonebook` tool ([get one](https://search.ch/tel/api/help)) |
| `PORT`            | `8080`  | Port the server listens on                                          |

Pass-through mode (Claude Code) needs none of these - send the bexio token as the bearer.

## Usage

**claude.ai web / iOS app:** add a custom connector (Settings -> Connectors) with URL `https://<PUBLIC_URL>/mcp`. Claude registers itself and opens the login screen; enter `OAUTH_PASSWORD` to authorize.

**Claude Code:** add the server with your bexio token as a bearer header, e.g.

```json
{ "mcpServers": { "bexio": {
  "type": "http",
  "url": "https://<PUBLIC_URL>/mcp",
  "headers": { "Authorization": "Bearer <your-bexio-token>" }
} } }
```

Then ask in natural language - "search the contact Muster", "create a draft invoice for contact 123 over 1000 CHF", "issue invoice 5". Resolve ids first via the reference tools. Issuing and `send_invoice` act on live data (real e-mail) - confirm before triggering.

## Troubleshooting

### claude.ai never shows the login

`PUBLIC_URL` must be the exact public HTTPS URL and reachable. The discovery docs live at `/.well-known/oauth-protected-resource` and `/.well-known/oauth-authorization-server`.

### Re-login needed after a restart

Tokens and registered clients are in memory by design - a container restart clears them, so claude.ai re-registers and you log in again.

### bexio HTTP 403 on projects

The bexio token lacks permission for that module. Use a token with the needed scope.

## License

MIT, see [LICENSE](../LICENSE).
