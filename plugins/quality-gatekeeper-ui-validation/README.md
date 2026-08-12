# Quality Gatekeeper UI host-validation plugin

This plugin is intentionally isolated from the production
`plugins/quality-gatekeeper` entry. It launches only the synthetic-fixture
host-validation MCP server and never replaces the production five-tool server.

The absolute Windows path in `.mcp.json` is local-validation wiring for the
workspace named in the validation protocol. Re-run the Plugin Creator
cachebuster/reinstall flow after changing the embedded resource. Do not publish
this plugin or treat its component-only canary as a secret.
