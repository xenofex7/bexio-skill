# bexio-mcp

An MCP server that exposes the bexio REST API as tools over Streamable HTTP. Run it as a remote connector so Claude (web and the iOS app) can drive bexio - the same capabilities as the skill, but available anywhere instead of only inside Claude Code.

## Features

- Contacts - search, get, create, update, delete
- Articles - search, get
- Invoices - list, get, create, issue, send by mail, PDF
- Quotes - list, get, create, issue, accept, reject, PDF
- Reference helpers - users, taxes, accounts, units (to resolve ids)
- Token pass-through - the bexio token comes from the client per request; nothing is stored on the server

## Authentication

The server holds **no secret**. The bexio API token is sent by the client as `Authorization: Bearer <token>` on every request (configured once in the Claude connector). The server forwards it to bexio for that request and never persists it. Anyone without a valid bexio token just gets bexio's own 401.

Optional: set `BEXIO_API_TOKEN` on the server as a single-user fallback used when a request carries no Authorization header.

## Requirements

- Docker and Docker Compose v2
- A bexio API token (kept on the client side)
- A reverse proxy with TLS for public exposure (e.g. Nginx Proxy Manager)

## Installation

```bash
cd mcp
docker compose up -d --build
```

The server listens on `http://localhost:8080/mcp`. Put it behind your reverse proxy with TLS and expose it as `https://bexio-mcp.example.ch/mcp`. No secrets to configure.

## Configuration

| Variable          | Default | Description                                                              |
|-------------------|---------|--------------------------------------------------------------------------|
| `BEXIO_API_TOKEN` | -       | Optional server-side fallback token (used only when no header is sent)   |
| `PORT`            | `8080`  | Port the server listens on                                               |

## Usage

Add it as a custom connector in Claude (Settings -> Connectors):

- URL: `https://bexio-mcp.example.ch/mcp`
- Auth: your **bexio API token** as the bearer token

Then ask Claude in natural language - "search the contact Muster", "create a draft invoice for contact 123 over 1000 CHF", "issue invoice 5". Resolve ids first via the reference tools (`list_users`, `list_taxes`, `list_accounts`, `list_units`).

Sending and issuing act on live data and, for `send_invoice`, send a real e-mail - confirm before triggering those.

## Troubleshooting

### bexio HTTP 401 unauthorized

No bearer token reached the server, or the token is invalid/expired. Check the connector's auth token (your bexio token).

### bexio HTTP 403 on projects

The bexio token lacks permission for that module. Use a token with the needed scope.

## License

MIT, see [LICENSE](../LICENSE).
