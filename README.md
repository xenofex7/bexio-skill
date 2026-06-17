# bexio

<p align="center">
  <a href="https://github.com/xenofex7/bexio-skill/blob/main/LICENSE"><img src="https://img.shields.io/github/license/xenofex7/bexio-skill" alt="license"></a>
  <img src="https://img.shields.io/badge/python-3.8+-blue?logo=python&logoColor=white" alt="python">
  <img src="https://img.shields.io/github/last-commit/xenofex7/bexio-skill" alt="last commit">
</p>

Two ways to control [bexio](https://www.bexio.com) (Swiss business software) with Claude through its REST API - contacts, articles, invoices and quotes. Both share the same endpoint knowledge; pick the one that fits where you work.

## Components

| | [`skill/`](skill/) | [`mcp/`](mcp/) |
|---|---|---|
| **What** | Claude Code skill (CLI + reference docs) | MCP server over HTTP |
| **Runs in** | Claude Code (terminal, desktop, web) | Anywhere - Claude web and iOS app, via a connector |
| **Setup** | Symlink into `~/.claude/skills`, token in `~/.zshenv` | Docker container behind a reverse proxy |
| **Auth** | Local env var | Static bearer token |

- **[skill/](skill/)** - lightweight, no dependencies, ideal on your own machine. See [skill/README.md](skill/README.md).
- **[mcp/](mcp/)** - dockerised remote server so Claude on mobile/web can reach bexio. See [mcp/README.md](mcp/README.md).

## License

MIT, see [LICENSE](LICENSE).
