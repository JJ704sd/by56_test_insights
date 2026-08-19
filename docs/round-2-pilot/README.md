# Round 2 P0 试点脚手架

本目录是 `docs/round-2-shadow-pilot-spec.md` 的 P0 启动材料；具体工作包、依赖、验收
证据和可拆票执行清单见 [`R2-G0 Execution Spec`](../round-2-g0-execution-spec.md)。它只
包含模板、流程和当前启动审计，不包含真实业务输入、业务结果、审批签名或生产凭据。所有 `TBD`、空表
和 `PENDING_APPROVAL` 都必须在责任人批准后替换；在替换前不得作为试点证据使用。

当前状态：`R2-G0 BLOCKED`；本次阶段输出为 `REMAIN_BLOCKED`，8 周影子时钟未启动。

## 当前事实

- 仓库基线：`qualityctl 0.1.0`，当前分支提交由启动审计记录；Python 3.10+ 契约和
  Windows Python 3.11 CI 仍是项目支持边界。
- 当前工作区验证：Python 3.14.6 下 `100/100` 单元测试通过，现有 stdio smoke 通过。
- 这些结果只证明仓库和示例数据可运行，不证明任何真实业务模块的风险召回、ROI 或
  试点 Gate。
- 本次业务输入复核没有提供候选模块、责任人、受控证据存储或 Agent 适用性批准；相关字段
  继续保持 `TBD/MISSING`，不得用仓库信息推断。
- Round 2 继续复用现有 `qualityctl` CLI、v1 JSON Schema 和五个 MCP 工具；本目录不
  重复实现规则核心。
- Embedded UI 不在 Round 2 扩展；若需要展示结果，默认使用现有静态 HTML/结构化 MCP
  输出，且不增加审批、发布或写回入口。

## 文件索引

| 文件 | 用途 |
| --- | --- |
| [`../round-2-g0-execution-spec.md`](../round-2-g0-execution-spec.md) | R2-G0 工作包、依赖、验收合同和可拆票执行清单 |
| [`../round-2-p1-evidence-pipeline-spec.md`](../round-2-p1-evidence-pipeline-spec.md) | `R2-G0_READY` 后的影子证据流水线、G1–G3 执行与决策契约；当前未激活 |
| [`pilot-charter.md`](pilot-charter.md) | 试点信息、范围、目标、硬门槛和签署页 |
| [`owner-raci.md`](owner-raci.md) | Owner/RACI、升级和停止责任 |
| [`decisions-to-approve.md`](decisions-to-approve.md) | 集中列出需要责任人批准的决策 |
| [`data-control-plan.md`](data-control-plan.md) | 受控存储、脱敏、权限、保留和删除计划 |
| [`r2-g0-audit.md`](r2-g0-audit.md) | 当前 R2-G0 逐项审计结果 |
| [`shadow-runbook.md`](shadow-runbook.md) | 人工先冻结、再解盲、旁路运行和留证手册 |
| [`templates/test-catalog.template.json`](templates/test-catalog.template.json) | v1 catalog 的 fail-closed 空模板 |
| [`templates/test-catalog.template.md`](templates/test-catalog.template.md) | 测试目录来源、30–50 条门槛和校验说明 |
| [`templates/component-dependency-map.template.csv`](templates/component-dependency-map.template.csv) | 组件、上游、下游、历史逃逸映射 |
| [`templates/component-dependency-map.template.md`](templates/component-dependency-map.template.md) | 映射来源、评审和版本规则 |
| [`templates/manual-baseline.template.csv`](templates/manual-baseline.template.csv) | 人工耗时和基线资格采集表 |
| [`templates/manual-baseline.template.md`](templates/manual-baseline.template.md) | 人工基线冻结、资格和采集顺序说明 |
| [`templates/agent-applicability.template.md`](templates/agent-applicability.template.md) | Agent 适用性及 `NOT_APPLICABLE` 依据 |
| [`templates/threshold-profile.template.md`](templates/threshold-profile.template.md) | 阈值、来源、版本和批准记录 |
| [`templates/roi-policy.template.md`](templates/roi-policy.template.md) | ROI policy 和最长回本周期 |
| [`templates/manual-scope.template.md`](templates/manual-scope.template.md) | 单个变更的人工范围冻结记录 |
| [`templates/adjudication.template.md`](templates/adjudication.template.md) | 人工与工具差异裁决记录 |
| [`templates/iteration-summary.template.md`](templates/iteration-summary.template.md) | 迭代汇总和可复算指标 |
| [`templates/final-report.template.md`](templates/final-report.template.md) | Round 2 最终报告 |

## P0 执行顺序

P0 只定义可审计的执行顺序，不替试点填写业务字段。未完成批准前，所有业务字段继续保留
为 `TBD` 或 `PENDING_APPROVAL`，不能把模板、`examples/`、仓库测试或示例工具输出放入
真实试点分母。

1. 由责任人补齐并批准 charter、RACI、数据控制、Agent 适用性、阈值和 ROI policy。
2. 在批准的受控存储中建立唯一 `pilot_id/change_id/run_id`；目标目录已存在时停止，改用
   新的 `run_id`，不得覆盖已有输入、输出、重跑、差异或裁决。
3. 在任何工具结果展示或运行前，测试负责人冻结人工风险范围、人工回归范围和人工耗时，
   并把冻结记录写入 `manual-scope` 和人工基线。
4. 冻结后才运行现有 `qualityctl` CLI 和五个 MCP 工具；原始请求、响应、退出码、时间、
   版本和校验摘要追加保存。
5. 解盲后由授权责任人完成差异裁决；工具选集不等于已执行测试，影子 Gate 不等于正式
   发布结论。
6. 每个迭代生成可复算汇总；完成 8 周、2 个完整迭代和 8 个合格变更后，才编写最终报告。

状态使用约定：`TBD` 表示尚未提供的业务输入，`PENDING_APPROVAL` 表示内容已准备但尚未
获批准，`READY` 只表示有当前可定位证据且该项完成；任何模板空值都不是启动授权。

## 使用边界

1. 真实证据放在已批准的受控存储位置，不放在仓库的 `docs/`、`examples/` 或普通日志中。
2. 变更目录必须唯一；若目标目录已存在，停止并创建新的重跑目录，不覆盖旧输入、输出、
   日志、裁决或摘要。
3. 每次变更必须先完成人工范围冻结，再展示或运行工具结果；没有冻结时间戳和操作者的
   记录不得进入主分母。
4. `qualityctl` 只提供影子建议和证据。正式发布仍由现有发布流程决定；本脚手架没有生产
   发布、放量、回滚、审批或写回权限。
5. 只有在 `r2-g0-audit.md` 的所有条件均为 `READY`、并取得签署后，才可填写影子开始时间。
