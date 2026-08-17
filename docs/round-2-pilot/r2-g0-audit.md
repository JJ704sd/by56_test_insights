# R2-G0 启动条件审计

审计日期：2026-08-17<br>
审计分支：`codex/record-desktop-inline-proof`  书面基线：`origin/main@ddad399`<br>
当前提交：`dc3c63d51c56ece88ab6ce883b2d99a26f6cfaac`<br>
与 `origin/main`：ahead `1`、behind `0`；merge-base `ddad39909d3d27248b1622ad113a3325f83c1f6c`<br>
当前状态：**`BLOCKED`；本次阶段输出为 `REMAIN_BLOCKED`，不得宣称试点已启动，8 周影子时钟未开始。**

本次输入复核：候选模块、所有业务/项目/测试/研发/发布/安全责任人、受控证据存储和计划
复核日期均未提供；Agent 适用性仍为“未决定”。本次只读取规范、模板和仓库状态，没有访问
或写入真实业务证据，也没有创建受控证据目录。
本次状态登记的责任角色仍待业务指定；批准来源为“无”，不能把本审计文件本身视为批准。

## 状态口径

- `READY`：有当前、可定位的证据，且该项要求已完成。
- `MISSING`：所需业务输入、批准、演练或责任人记录尚未提供。
- `BLOCKED`：由于缺少前置条件或仅有模板/示例，当前不能安全地把该项视为完成。

## A. 仓库和当前基线预检

| 检查项 | 状态 | 证据/说明 |
| --- | --- | --- |
| 仓库、README、MVP Spec、插件 MVP Spec、开发者指南已检查 | `READY` | 本审计及对应文档；未把文档声明当作业务证据 |
| `qualityctl` CLI 与示例入口已检查 | `READY` | `src/qualityctl/cli.py`；当前 CLI 子命令为 `risk-check`、`select`、`agent-eval`，三组 examples 分别返回 `READY`、`READY`、`PASS` |
| 版本化 JSON Schema 与 Pydantic 校验器存在 | `READY` | `src/qualityctl/schemas/v1/` 的 manifest/catalog/agent_spec/agent_run schema 与 `src/qualityctl/validation.py` |
| 五个 MCP 工具注册与边界校验 | `READY` | 单元测试验证五个工具注册/输入 schema；stdio smoke 列出 `validate_change_risks`、`select_regression_scope`、`evaluate_agent_evidence`、`assess_automation_roi`、`decide_release_gate` |
| 单元测试当前状态 | `READY` | Python 3.14.6：`Ran 100 tests ... OK`（100/100）；这是仓库基线，不是试点结果 |
| MCP smoke 当前状态 | `READY` | 真实 stdio 握手通过；现有 smoke 实际调用 ROI 与示例最终 Gate，二者均为 `PASS`；本次另用同一 stdio server 对五个工具逐一调用，全部 `OK`；全部仅使用 examples |
| 生产发布/写入权限 | `READY` | 当前脚手架未增加权限、发布动作或写回入口；仍需试点 owner 书面确认 |
| Embedded UI 范围 | `READY` | Round 2 不扩展；静态 HTML/结构化 MCP 输出保持默认方案 |
| `origin/main` 关系与工作区保护 | `READY` | `git rev-list --left-right --count origin/main...HEAD` 为 `1 0`；当前用户改动已保留，未执行 reset/checkout/清理/提交/推送 |
| R2-G0 所需模板可填写性 | `READY`（预检） | `templates/` 下 catalog、mapping、Agent、threshold、ROI、baseline、manual-scope、adjudication、iteration-summary、final-report 均存在；空模板仍是 fail-closed，不是业务证据 |
| 业务输入和候选模块 | `MISSING` | 本次输入为占位/空值；没有候选频率、目录、Oracle、隔离环境、人工流程或责任人事实 |

## B. R2-G0 逐项审计

| # | 启动条件（Spec §5.2） | 状态 | 当前证据与缺口 | 责任人批准后动作 |
| --- | --- | --- | --- | --- |
| 1 | 试点章程、范围、owner 和升级路径已批准 | `MISSING` | [Charter](pilot-charter.md) 和 [RACI](owner-raci.md) 仍为 `TBD/MISSING`；没有业务模块、owner 或可执行通道；对应 `R2-G0-DEC-001/002` | 填写并批准候选、charter、RACI、升级通道 |
| 2 | 测试目录 30–50 条唯一 ID，Schema 校验通过 | `BLOCKED` | 只有 [`test-catalog.template.json`](templates/test-catalog.template.json) fail-closed 空模板，尚无真实目录；examples 不能替代试点目录 | 提供 30–50 条脱敏目录，冻结版本并运行 `qualityctl select`/Schema 校验 |
| 3 | 八维风险清单模板和组件/依赖映射已评审 | `MISSING` | 模板已创建，但真实组件、上游、下游、历史逃逸、八维口径和双人评审记录缺失 | 完成映射、八维风险评审并保存批准证据 |
| 4 | Agent 适用性、阈值和 ROI policy 来源/审批已冻结 | `MISSING` | Agent 输入为“未决定”；权威来源、阈值、ROI policy、最长回本周期均未提供；对应 `R2-G0-DEC-003/005/006/007` | 填写对应模板，批准版本和来源；若不适用必须有 `NOT_APPLICABLE` 依据 |
| 5 | 至少两个历史或前置迭代的人工基线可用 | `MISSING` | 尚无试点模块、变更台账或人工基线记录；不得用 examples/推测数据补齐；受控存储前置也未满足 | 选择合格历史记录，或前瞻采集至少两个迭代 |
| 6 | 人工耗时采集方式通过一次演练 | `MISSING` | 采集表已创建但没有实际演练和复核证据 | 用一个非分母演练变更完成采集，确认冻结/解盲顺序 |
| 7 | 影子 CI/运行手册已演练且不阻塞正式发布 | `MISSING` | 非阻塞手册已创建但尚未在真实隔离流程中演练；现有 CI 未改为 required shadow check；对应 `R2-G0-DEC-008` | 运行演练，验证只读、独立、非 required、失败不改变发布结论 |
| 8 | 证据存储、权限、脱敏、保留周期已批准 | `MISSING` | [数据控制计划](data-control-plan.md) 的受控位置、访问组、数据级别、保留和删除责任均为 `TBD`；对应 `R2-G0-DEC-004/009` | 完成数据控制审批并记录存储回执 |
| 9 | 回退和紧急停止责任人明确 | `MISSING` | RACI 角色存在模板但没有姓名、值班/升级通道或正式确认；对应 `R2-G0-DEC-010` | 指定停止/回退 owner，演练通知和恢复流程 |

## C. 结论

`R2-G0 = REMAIN_BLOCKED`（内部准备状态：`BLOCKED`）。原因不是代码或仓库 smoke 失败，
而是所有真实业务启动前置条件仍缺少批准证据；其中测试目录和真实基线在当前状态下不能
通过任何示例或模板替代。本次未观察到安全事件、未经授权发布影响或其他停止红线，因此不
输出 `STOP_PREPARATION`。

- 不启动 8 周影子时钟。
- 不产生“真实试点已启动”“风险召回”“ROI”“阶段 Gate”或“业务结果”声明。
- 允许的当前动作仅为补齐业务输入、批准、演练和数据控制；不会修改现有发布流程。

## E. 本次 G0 Ticket 处置与责任队列

`G0-001` 至 `G0-003` 已完成依赖核对和缺口登记，但没有达到各自完成判据；Wave B/C
票据因前置条件缺失保持阻塞。`G0-012` 已记录唯一的 `REMAIN_BLOCKED` 结果，但这不是
R2-G0 启动签署，也不允许启动影子时钟。

| Ticket | 当前状态 | 责任角色（身份待提供） | 下一动作 | 必需输出 | 复核日期 |
| --- | --- | --- | --- | --- | --- |
| `G0-001` | `BLOCKED` | 项目负责人、业务 owner | 提供候选模块事实并完成评分/唯一选择 | `R2-G0-DEC-001` 批准记录 | `TBD` |
| `G0-002` | `BLOCKED` | 项目负责人 | 补齐 `pilot_id`、范围、周期、非目标并提交 Charter | `R2-G0-DEC-002` 及 Charter 版本 | `TBD` |
| `G0-003` | `BLOCKED` | 项目负责人、测试负责人 | 补齐角色、联系方式、升级/停止/恢复通道 | 更新 RACI 和 `R2-G0-DEC-002` 证据 | `TBD` |
| `G0-004` | `BLOCKED` | 安全/合规接口人、项目负责人 | 先批准受控存储、数据控制和权限 | `R2-G0-DEC-004/009` 证据包 | `TBD` |
| `G0-005` | `BLOCKED` | 测试负责人、研发负责人 | 受控输入获批后提供 30–50 条唯一目录并校验 | catalog 版本、Schema/CLI 输出、双人评审 | `TBD` |
| `G0-006` | `BLOCKED` | 测试负责人、研发负责人 | 提供组件/依赖/历史逃逸来源并完成八维评审 | mapping 版本、来源、复核记录 | `TBD` |
| `G0-007` | `BLOCKED` | 测试负责人、Agent 负责人/业务裁决人 | 将 Agent“未决定”转成批准值或批准的不适用依据 | `R2-G0-DEC-003/007` 及适用性记录 | `TBD` |
| `G0-008` | `BLOCKED` | 项目负责人、测试负责人、业务裁决人 | 批准 threshold、ROI 和非安全效率口径 | `R2-G0-DEC-003/005/006` 及策略版本 | `TBD` |
| `G0-009` | `BLOCKED` | 测试负责人 | 前置批准后提供两个迭代人工基线 | 两个可复核基线包及排除清单 | `TBD` |
| `G0-010` | `BLOCKED` | 测试负责人、独立复核人 | 完成先冻结后解盲的非分母演练 | 冻结/可见/解盲时间和复核记录 | `TBD` |
| `G0-011` | `BLOCKED` | 发布负责人、项目负责人、安全接口人 | 覆盖正常旁路、BLOCKED、工具失败、停止/恢复 | 非阻塞演练和隔离证明 | `TBD` |
| `G0-012` | `BLOCK_DECISION_RECORDED` | 项目负责人、测试负责人、业务/产品裁决人 | 待 9/9 READY 后完成最终签署；当前只保留阻塞结论 | 最终审计签署，未满足前不得写实际开始时间 | `TBD` |

## D. 启动前安全红线口径

下表是试点期必须满足的门槛，不是仓库或 examples 的结果。由于 `R2-G0` 未通过，当前
没有业务影子分母，不能把“尚未观测”改写为业务 `0`。

| 红线 | 试点门槛 | 当前影子证据 |
| --- | --- | --- |
| 错误 `PASS` | `0` | `PENDING_NOT_STARTED` |
| 确认的高风险漏选 | `0` | `PENDING_NOT_STARTED` |
| 未经授权自动放行 | `0` | `PENDING_NOT_STARTED` |
| 敏感数据事件 | `0` | `PENDING_NOT_STARTED` |

仓库 examples 的 `PASS`、单元测试通过数和 stdio smoke 结果只证明规则/传输基线可运行，
不构成上述四项的真实业务试点证据。
