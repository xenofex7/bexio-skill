# bexio-mcp

An MCP server that exposes the bexio REST API as tools over Streamable HTTP. Run it as a remote connector so Claude (web and the iOS app) can drive bexio - the same capabilities as the skill, but available anywhere instead of only inside Claude Code.

## Features

- Contacts - search, get, create, update, delete
- Articles - search, get
- Invoices - list, get, create, issue, send by mail, PDF
- Quotes - list, get, create, issue, accept, reject, PDF
- Reference helpers - users, taxes, accounts, units (to resolve ids)
- Static bearer-token gate in front of the endpoint

## Requirements

- Docker and Docker Compose v2
- A bexio API token
- A reverse proxy with TLS for public exposure (e.g. Nginx Proxy Manager)

## Installation

```bash
cd mcp
cp .env.example .env   # fill in BEXIO_API_TOKEN and a strong MCP_AUTH_TOKEN
docker compose up -d --build
```

The server now listens on `http://localhost:8080/mcp`. Put it behind your reverse proxy with TLS and expose it as `https://bexio-mcp.example.ch/mcp`.

## Configuration

| Variable           | Default | Description                                                           |
|--------------------|---------|-----------------------------------------------------------------------|
| `BEXIO_API_TOKEN` *| -       | Bearer token the server uses to call the bexio API                    |
| `MCP_AUTH_TOKEN`   | -       | Shared secret clients must send as `Authorization: Bearer <token>`    |
| `PORT`             | `8080`  | Port the server listens on                                            |

`*` required. With `MCP_AUTH_TOKEN` empty the endpoint is unauthenticated - only do that on a private network.

## Usage

Add it as a custom connector in Claude (Settings -> Connectors):

- URL: `https://bexio-mcp.example.ch/mcp`
- Auth: the `MCP_AUTH_TOKEN` value as a bearer token

Then ask Claude in natural language - "search the contact Muster", "create a draft invoice for contact 123 over 1000 CHF", "issue invoice 5". Resolve ids first via the reference tools (`list_users`, `list_taxes`, `list_accounts`, `list_units`).

Sending and issuing act on live data and, for `send_invoice`, send a real e-mail - confirm before triggering those.

## Troubleshooting

### 401 unauthorized

The `Authorization: Bearer <MCP_AUTH_TOKEN>` header is missing or wrong. Check the connector's auth token matches the server's `MCP_AUTH_TOKEN`.

### bexio HTTP 403 on projects

The bexio token lacks permission for that module. Use a token with the needed scope.

## License

MIT, see [LICENSE](../LICENSE).
