# Quality Gatekeeper Desktop Inline validation

Date: 2026-08-12

Branch: `agent/quality-ui-desktop-inline-validation`

Status: **BLOCKED_BY_ENVIRONMENT for Inline; stop visual expansion**

This report supersedes only the current-state claims in the historical
`embedded-ui-real-host-pilot.md`. The earlier pilot remains an accurate record of that run.

## Scope and invariant

This round stopped after the Inline gate. It did not execute Fullscreen, bridge, accessibility,
cache-renderer, or user-value experiments. The deterministic core files and the production five
tools were not changed. The Inspector remains read-only and fail-closed for unverified reports.

## Host and installation evidence

- Desktop AppX: `OpenAI.Codex_26.803.10989.0_x64__2p2nqsd0c76g0` (`26.803.10989.0`),
  Store package status `Ok`.
- Bundled CLI: `C:\Program Files\WindowsApps\OpenAI.Codex_26.803.10989.0_x64__2p2nqsd0c76g0\app\resources\codex.exe`.
  Its OpenAI Authenticode signature is valid.
- Direct `codex.exe --version` process creation failed `3/3` under the sandbox identity; an
  approved external Administrator comparison also failed with `Access is denied`. The same file
  was already running the Desktop app server from package context. This supports a Store/AppX
  process-identity boundary, not file corruption; no ACL or executable was changed or copied.
- The repository marketplace is `quality-gatekeeper-host-validation`. The validation plugin was
  updated with the repository Plugin Creator helper, uninstalled through Desktop Plugin
  Management, and reinstalled from the application plugin page.
- Final installed manifest version: `0.1.0+codex.20260812070059`; the config entry is enabled.
- Desktop exposed the validation Inspector in both the current task and a newly created task.
  Desktop-owned validation-server child processes and successful calls establish plugin loading
  and MCP startup as `VERIFIED`.
- Loading is mixed by design: discovery and `.mcp.json` come from the installed cache copy, while
  `.mcp.json` starts the validation server at an absolute path in this checkout. The server reads
  the workspace UI resources. Do not describe this as an entirely cached or entirely source-loaded
  runtime.

## Real Desktop task calls

The new Desktop task was `019ff4bc-4b73-7163-a7d0-bd213416434d`. Times are UTC.

| fixture | call start | call end | raw Gate | release basis | effective release allowed | tool error |
|---|---|---|---|---|---:|---|
| PASS | 06:51:13.005 | 06:51:13.040 | PASS | VERIFIED | true | none |
| FAIL | 06:53:18.734 | 06:53:18.770 | FAIL | VERIFIED | false | none |
| BLOCKED | 06:53:18.771 | 06:53:18.805 | BLOCKED | VERIFIED | false | none |
| REVIEW_REQUIRED | 06:53:18.805 | 06:53:18.839 | REVIEW_REQUIRED | VERIFIED | false | none |
| UNSUPPORTED_SCHEMA | 06:53:18.839 | 06:53:18.873 | PASS | NOT_VERIFIED | false | none |

The same task read `ui://quality-gatekeeper/report/v2-host-validation.html` successfully at
06:53:59.954-06:53:59.978. The intentional missing URI
`ui://quality-gatekeeper/report/missing-host-validation.html` failed at
06:53:59.979-06:54:00.001 with MCP `-32603`. The next canonical Inspector call in the same
Desktop task succeeded at 07:04:29.486-07:04:29.525 with `isError=false`, Gate `PASS`, verified
release basis, effective release allowed, and the unchanged digest
`sha256:05598552f173e628a58b01fdba35d5605f95d3d0d6a1cf6c56eb3a8208e56b3e`. This is Desktop
resource/tool isolation evidence, not Inline rendering evidence.

After the final `0.1.0+codex.20260812070059` reinstall, a second new Desktop task
(`019ff4c7-c0cc-78f2-9385-d9d9297eba46`) exposed the canonical Inspector and completed a normal
call at 07:03:53.037-07:03:53.072 with Gate `PASS`, verified release basis, effective release
allowed, and `isError=false`. This establishes final-version pickup and tool availability in a
new task. It did not expose a visible component DOM or canary and is not Inline evidence.

## Inline result

- Inline: **0/10**
- Valid Inline denominator: **0**
- Failure rate: **N/A**
- Reason: no valid visible Inline denominator.

The calls returned model-readable `content` and `structuredContent`, but neither the task tool
result nor the available in-app Browser surface exposed the conversation iframe DOM. The resource
URI, component-only canary, Inline readability, and stale-render state therefore remain
`NOT_VERIFIED`. Tool success is not counted as Inline success, and the five calls above are not a
partial `5/10` denominator.

## Verified compatibility defect and minimum repair

Official OpenAI UI documentation defines `window.openai.toolResponseMetadata` as an envelope that
preserves the MCP result in `mcp_tool_result` / `call_tool_result`, including hidden `_meta`. The
component previously read only top-level `toolResponseMetadata.qualityReport`. That shape could
leave a real component without its report even when the host supplied the official envelope.

A regression test first failed on the missing envelope readers. The component now unwraps
`mcp_tool_result._meta` and `call_tool_result._meta`, while preserving the portable notification
shapes already supported. The application Browser host-contract probe delivered both envelopes,
verified both component-only canaries, and ended in `PASS`. This is a component contract repair;
it does not upgrade Desktop Inline to `VERIFIED`.

Official sources:

- <https://developers.openai.com/plugins/build/chatgpt-ui>
- <https://developers.openai.com/plugins/reference>

The repository `cachebuster` suffix is a local development/reinstall mechanism. It is not an
official OpenAI manifest field. The official cache contract uses resource URIs as cache keys.

## Next gate

Do not continue visual expansion. Re-run from a Desktop surface that exposes the actual
conversation component or supported host instrumentation. Only then begin the cold-start/new-task
and consecutive ten-call Inline denominator. Fullscreen, bridge, cache-renderer, accessibility,
and user-value work remain gated on stable, visible Inline evidence.

User-value experiment: participants `0`; status `BLOCKED_BY_ENVIRONMENT`. Agent self-testing was
not counted as a participant.
