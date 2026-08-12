# Quality Gatekeeper Desktop Inline validation

Date: 2026-08-12

Branch: `agent/quality-ui-desktop-inline-validation`

Status: **single-proof Inline VERIFIED; ten-run stability gate incomplete; stop visual expansion**

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

## 2026-08-12 Inline-only continuation

Task: `019ff50e-6d38-72b2-9020-945af83539b4` (`验证 Quality Gatekeeper Inline 渲染`)

This continuation kept the same Inline-only gate. It did not change plugin content, the MCP
contract, the component, or deterministic quality behavior. Fullscreen, bridge, renderer-cache,
accessibility, and user-value experiments remained out of scope.

### Current official boundary

The current official OpenAI documentation establishes three different levels of support:

- ChatGPT explicitly runs MCP UI resources in an iframe and exposes the MCP Apps bridge plus
  optional ChatGPT `window.openai` extensions.
- The open MCP Apps contract can run in compatible hosts, but compatibility is a host capability;
  it is not evidence that every host renders a component.
- Codex in the ChatGPT desktop app supports plugins and MCP tools. The plugin architecture also
  warns that individual capabilities can be surface-specific. The official Codex/Desktop pages
  do not publish a task-surface DOM inspector, iframe inspector, or DevTools workflow, and do not
  explicitly guarantee that the Codex task surface renders MCP Apps UI.

Official sources:

- <https://developers.openai.com/plugins/build/chatgpt-ui>
- <https://developers.openai.com/plugins/concepts/plugins>
- <https://learn.chatgpt.com/docs/plugins>
- <https://learn.chatgpt.com/docs/windows/windows-app>

ChatGPT iframe support and generic MCP Apps portability therefore remain useful contract evidence,
but neither is counted as Codex Desktop Inline evidence.

### Observation -> hypothesis -> experiment evidence graph

| observation | falsifiable hypothesis | one-variable experiment | result |
|---|---|---|---|
| The validation Inspector is exposed in this real Desktop task. | The plugin or MCP server is not actually loaded. | Invoke the canonical Inspector once with the unchanged PASS fixture. | Rejected: `isError=false`, Gate `PASS`, verified release basis, effective release allowed, and the stable decision digest were returned. |
| The real call exposes model-readable `content` and `structuredContent`, but no inspectable component metadata or DOM to this agent. | The installed descriptor/resource is stale, missing, or malformed. | List and read the canonical resource through the task's live MCP server without changing the tool input. | Rejected for the resource path: v1 and v2 are listed with `text/html;profile=mcp-app`, app visibility, empty CSP allowlists, and the canonical v1 HTML contains the component canary DOM plus both official envelope readers. This is resource evidence, not render evidence. |
| Installed plugin version and workspace source can be confused. | Desktop loaded a different server or UI copy than the reported version. | Compare the installed cache manifest and `.mcp.json` with the live child-process command and workspace resource. | Rejected: installed cache manifest is `0.1.0+codex.20260812070059`; its `.mcp.json` starts the absolute workspace `host_validation_server.py`, which reads the workspace UI resource. |
| The in-app Browser has no controlled or user-claimable tabs for the Codex task surface. | A rendered component exists and can be inspected through the Browser DOM. | Bind the Codex in-app Browser and enumerate its controlled and open tabs, without opening a standalone page. | Rejected for this inspection path: both lists were empty; the main task surface is not a Browser tab. |
| The current task is active in the app, while the foreground main window remained on another task. | The supported task navigation API can expose the active task for a bound screenshot/DOM check during the running turn. | Navigate to the exact current task ID, then capture only the ChatGPT/Codex main window. | Not established: two captures still showed the other task, so both were invalid and excluded. After two rounds with no new Inline evidence, retries stopped. |

The remaining leading explanations cannot be distinguished with the current host surface:

1. the Codex task renderer consumes the tool result but does not mount the MCP UI resource; or
2. a component is mounted, but the running task surface is not exposed to the available Browser,
   DOM, or reliable task-bound capture interface.

No observed envelope, resource URI, `window.openai`, or `_meta` shape contradicted the component's
current compatibility contract. Consequently there was no evidence-based contract expansion and
no regression-fix/TDD cycle.

### Gate result

- Inline: **0/10**
- Valid Inline denominator: **0**
- Failure rate: **N/A**
- Component-only canary in a real Desktop Inline DOM: **NOT_VERIFIED**
- Minimum host capability gap: a supported way to expose the active Codex task surface for
  iframe/DOM inspection or a reliable task-bound screenshot that shows the real Inspector call and
  component together.

The consecutive ten-call denominator remains prohibited until one valid Desktop Inline call is
visibly and inspectably bound to its component.

## 2026-08-12 task-surface observability resolution

This section supersedes the current-state Inline conclusion above. It does not reinterpret any
historical tool-only call or invalid screenshot as Inline success.

### Root cause and minimum operational fix

The plugin, installed descriptor, server, resource, and result envelope were not the cause. The
actual blockers were the observation path and the host-turn shape:

- the in-app Browser exposed no controlled or user tabs for the Codex task surface;
- the Windows foreground window was WeChat while the Codex main window was minimized to a
  `160x28` shell, so foreground and off-screen captures initially had no task DOM;
- the task database bound `019ff53f-db64-7f01-93e2-25876ca6c65f` to the selected title
  `验证 Inline UI 渲染证据`, while the real Codex window was HWND `0x30A7E`, PID `26968`;
- restoring and activating that exact HWND, then inspecting its Windows UI Automation tree,
  exposed the real sandbox document, component document, Inspector group, digest, and canary;
- ten nested Inspector calls inside one outer `exec` host turn were coalesced into one observable
  component document. A stable Inline denominator therefore requires one Inspector call per outer
  host turn and observation before the next tool event can virtualize the component.

No descriptor, resource URI, envelope, `window.openai`, or `_meta` mismatch was observed. No
plugin-creator, evolving-contracts, or TDD repair was justified, and no plugin or component source
was changed.

### Official capability matrix

| capability | ChatGPT published support | generic MCP Apps | Codex Desktop published support | local observation |
|---|---|---|---|---|
| MCP UI resource and Inline iframe | Explicitly documented | Defined for compatible MCP Apps hosts | Public Codex/Desktop docs do not establish this task-surface capability | VERIFIED for this task |
| `window.openai` extensions | Explicitly documented as ChatGPT host extensions | Not portable core | Public docs do not establish it for Codex Desktop | NOT_INSPECTED |
| tool-result component `_meta` | Component-only result metadata documented | Portable result metadata | Public docs do not establish renderer behavior | VERIFIED in the raw event and component DOM |
| task-surface screenshot/appshot | Not an MCP Apps contract | Not an MCP Apps contract | Public docs do not establish a Codex task appshot API | VERIFIED through task-bound Windows capture, not Browser |
| task DOM/iframe inspection | Browser tooling is documented for web pages and local web apps | Host-specific | Public docs do not establish Codex task DevTools/DOM inspection | Browser unavailable; Windows UI Automation VERIFIED |
| component load telemetry | Host implementation detail | Host-specific | Public docs do not establish it | Resource URI in task event plus rendered component ancestry VERIFIED |

Official sources:

- <https://developers.openai.com/plugins/build/chatgpt-ui>
- <https://learn.chatgpt.com/docs/plugins>
- <https://learn.chatgpt.com/docs/extend/mcp>
- <https://learn.chatgpt.com/docs/browser>
- <https://learn.chatgpt.com/docs/windows/windows-app>

Absence from the public Codex/Desktop documentation is recorded only as “public docs do not
establish this capability”; it is not treated as proof that the product cannot support it.

### Strict single-proof result

The single-proof gate is **VERIFIED**:

1. task `019ff53f-db64-7f01-93e2-25876ca6c65f` completed the real
   `inspect_release_quality` call `exec-2479f48c-318b-4fcf-aa92-a2e2d4c06612` at
   `09:26:10.385Z` with Gate `PASS` and no tool error;
2. the task event declared `ui://quality-gatekeeper/report/v1.html` and preserved hidden result
   `_meta` keys `componentOnlyCanary` and `qualityReport`;
3. the task window rendered a nested sandbox document and `Quality Evidence Inspector` component
   under `Quality Gatekeeper Host Validation MCP Inspect release quality`;
4. that component contained exactly one `AutomationId=component-only-canary` node;
5. the raw canary matched the expected pattern and was absent from serialized `content` plus
   `structuredContent`;
6. the same component contained the call decision digest
   `sha256:5523405b3ad4cc744f0fdf954579f65889b94373f6d635ce5b2d32276d22fe93`, and task ID,
   title, HWND, PID, timestamps, call ID, screenshot hash, resource URI, DOM ancestry, digest, and
   canary check are recorded together.

Evidence:

- [task-surface screenshot](evidence/desktop-inline-20260812/single-proof-task-surface.png)
- [single-proof task/call/DOM record](evidence/desktop-inline-20260812/single-proof.json)
- [configuration freeze and stability attempt](evidence/desktop-inline-20260812/stability-attempt.json)

### Stability result

The frozen configuration is recorded at `09:36:09.5159886Z`. Ten fixed-input Inspector calls all
succeeded with ten distinct call IDs, the same digest, the expected resource URI, hidden canary,
and no model-visible canary. They are **not** counted as ten Inline successes because they were
nested in one outer host turn and produced only one bindable component document.

A subsequent one-call-per-host-turn probe produced one fully bound new component RuntimeId. A
later call had no matching component in its probe, but that negative observation did not retain a
simultaneous task-title or activation binding and is therefore excluded instead of being called an
Inline failure. This is not a completed ten-run gate. Consequently:

- single-proof Inline: **1/1 VERIFIED**;
- consecutive ten-run Inline stability: **INCOMPLETE**;
- completed ten-run denominator: **not established**;
- valid independent-turn denominator: **1**, success **1**, provisional failure rate **0%**;
- excluded unbound negative observations: **1**;
- tool-only batch: **10/10**, excluded from the Inline denominator.

Visual expansion, Fullscreen, real bridge expansion, renderer-cache work, accessibility
experiments, and user-value experiments remain stopped.
