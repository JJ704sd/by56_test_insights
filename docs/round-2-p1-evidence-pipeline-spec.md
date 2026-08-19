# qualityctl Round 2 P1 Execution Spec：影子证据流水线与 G1–G3 决策

| 项目 | 内容 |
| --- | --- |
| 文档版本 | v0.1 Draft |
| 状态 | 待评审；`BLOCKED_BY_R2_G0` |
| 日期 | 2026-08-18 |
| 仓库基线 | `codex/record-desktop-inline-proof@ff11ddb`，`qualityctl 0.1.0` |
| 上位文档 | [Round 2 真实业务影子试点 Spec](round-2-shadow-pilot-spec.md) |
| 入场门禁 | [R2-G0 Execution Spec](round-2-g0-execution-spec.md) |
| 执行手册 | [非阻塞影子运行手册](round-2-pilot/shadow-runbook.md) |
| 当前工程增量 | [P1b 证据完整性与冻结迭代汇总](round-2-p1b-iteration-summary-spec.md) |
| 覆盖 Gate | `R2-G1 HEALTHY → R2-G2 ITERATION_VALIDATED → R2-G3 DECISION_READY` |
| 最终决策 | `GO_LIMITED_GATE / ADJUST_AND_REPEAT / STOP` |

## 1. 执行摘要

Round 1 已提供版本化输入 Schema、确定性规则核心、CLI、五个 MCP 工具和 Windows
CI 基线。Round 2 P0/G0 已准备章程、RACI、数据控制、运行手册和模板，但当前
`R2-G0` 仍是 `REMAIN_BLOCKED`，8 周影子时钟未启动。本 Spec 可在阻塞期评审和用脱敏
fixture 验证，但只有 `R2-G0_READY` 且完成签署后才能消费真实业务证据。

现有核心能计算单次风险、回归选集、Agent 评测和建议性 Gate，但不能机器化证明：

- 人工范围确实早于工具运行和解盲冻结；
- 原始输入、首次失败、全部重跑和裁决记录未被覆盖；
- 变更是否有资格进入主分母，差异是否完整裁决；
- 迭代指标和 ROI 是否能从原始证据复算；
- 阶段决策是否满足样本、时间、安全、ROI 和签署条件。

本 Spec 用一个深的、确定性的 **Pilot Evidence Pipeline** 填补缺口：现有
manifest/catalog/agent 输入和规则结果仍是原始证据；新模块只增加 Pilot Evidence v1
包装、单变更验证、差异裁决、迭代聚合和阶段建议。流水线不持有发布、审批、
回滚、生产写入或策略修改权限；所有产物的 `formal_release_effect` 恒为 `NONE`。

## 2. 当前事实、问题与激活条件

### 2.1 已验证基线

- `risk.py`、`selection.py`、`agent_eval.py` 分别计算风险状态、回归选集和 Agent 失败域；
- `gate.py` 从原始 manifest/catalog/Agent 证据重算建议性 Gate，不接受调用方自填状态；
- v1 JSON Schema/Pydantic 对三类主输入和 Agent run 做结构校验；
- 五个 MCP 工具、三个 CLI 子命令、单元测试和 stdio smoke 可运行；
- 当前基线为 Python 3.14.6 下 `124/124` 单元测试通过；支持契约仍为 Python 3.10+，
  CI 仍以 Python 3.11 为必验环境。

上述事实只证明仓库规则与示例传输链路可运行，不是真实业务试点证据。

### 2.2 已确认实现缺口

| 缺口 | 当前行为 | P1 要求 |
| --- | --- | --- |
| 证据覆盖 | `io.write_json` 直接覆盖已有路径 | P1 writer 必须 exclusive-create，冲突时失败且原字节不变 |
| 版本兼容 | 输入结构层接受任意非空 `schema_version` | P1 分母只接受批准矩阵；未知 major fail-closed |
| Catalog 准入 | v1 可允许缺业务 Oracle、来源和评审信息的条目 | 增加 pilot catalog readiness，不把“30–50 条 + Schema 通过”当质量证明 |
| Agent 失败 | 现有 v1 reader 接受非 `ok` run 同时携带 stale `output` | P1 verifier 将该形状阻塞在分母外；不就地改写 v1 旧契约 |
| CLI 错误 | 结构校验为 JSON，文件/JSON 读取失败为自由文本 | P1 新入口的全部失败使用稳定结构与退出码 |
| 证据链 | 只有 manifest/catalog/agent 输入 Schema | 增加 pilot/change/run、freeze、execution、adjudication、iteration 和 stage 契约 |
| 完整性 | Agent fingerprint 由调用方声明 | 从 canonical bytes 重算 artifact/packet/decision digest |
| 汇总 | 迭代和最终报告是人工 `TBD` 模板 | 从冻结索引确定性聚合，零分母不得补零 |

### 2.3 唯一激活条件

P1 只能在以下条件同时成立后从 `BLOCKED_BY_R2_G0` 转为 `SHADOW_RUNNING`：

1. `R2-G0` 九项条件均为 `READY`；
2. 项目、测试和业务/产品三方完成启动签署；
3. Charter 记录不可回写的实际开始时间与首个计划变更；
4. P1 契约、验证器和不覆盖 writer 通过脱敏 fixture 验证；
5. 已批准受控存储将新契约纳入 writer/reader 兼容矩阵。

任一条不成立时，只允许文档、单元测试、脱敏 fixture 和非分母 dry-run；不得创建
真实主分母或启动 8 周时钟。

## 3. 目标与非目标

### 3.1 目标

1. 为每个 eligible change 生成不可覆盖、可定位、可复算的完整证据包。
2. 验证人工冻结、工具运行、解盲、裁决和正式结果的顺序。
3. 把 eligible、excluded、out-of-plan 和全部 rerun 纳入同一冻结索引。
4. 从原始证据生成差异草稿，由授权责任人完成语义裁决。
5. 聚合安全、效率、质量和 ROI 指标，保留公式、分母和原始引用。
6. 在第 2 周、首个完整迭代和 8 周期末分别产出 G1、G2、G3 可审计结论。
7. 最终只产出三种允许决策之一的建议；签署前不声称已批准。

### 3.2 非目标

- 不替代或补录 `R2-G0` 业务输入、owner、RACI、数据控制或审批；
- 不让影子 Gate 成为 required check，不自动发布、豁免、回滚、改范围或写生产；
- 不建设远程证据服务、策略注册中心、测试管理平台或新 Agent runner 平台；
- 不扩展 Embedded UI、Fullscreen、Desktop Inline、remote MCP 或视觉体验；
- 不用 LLM 判断风险接受、业务 Oracle、裁决分类、安全事件或最终批准；
- 不在 8 周、2 迭代和 8 合格变更之前声称 ROI、高风险召回或阶段成功；
- 不提前设计 Round 3 硬门禁；只有批准 `GO_LIMITED_GATE` 后才能另立 Spec。

## 4. 权威、边界与不变量

| 信息 | 权威方 | Pipeline 可执行 | Pipeline 不得执行 |
| --- | --- | --- | --- |
| 原始变更、构建和正式结果 | 现有开发/测试/发布系统 | 验证引用、时间和摘要 | 触发、更改或伪造结果 |
| 人工范围 | 测试负责人 | 验证冻结时序和引用 | 根据工具结果回写原范围 |
| 风险/回归/Agent 状态 | 现有确定性规则核心 | 从原始输入重算 | 接受调用方自填 `PASS` |
| 差异分类 | Charter/RACI 指定的裁决人 | 生成差异草稿、验证完整性 | 代替人完成语义裁决 |
| 阈值、ROI 和风险接受 | 已批准的策略来源与责任人 | 验证版本/批准并计算 | 补默认值、放宽安全门槛 |
| 阶段批准 | 项目、测试、业务/产品三方 | 给出建议和阻塞原因 | 把建议当成已批准决定 |

全阶段保持以下不变量：

1. `formal_release_effect = NONE`，与 raw Gate 的 `release_allowed` 值无关。
2. 证据包 append-only；修正、重跑、解盲和裁决只能增加新文件/新版本。
3. 人工冻结时间必须早于工具首次运行和结果展示时间。
4. 所有 eligible、excluded、out-of-plan 变更和 attempt 均进入冻结台账。
5. 分母为零、证据缺失、版本不兼容或策略未批准时，结果是 `BLOCKED/null`，不是 `0/PASS`。
6. 原始规则结果、业务裁决和证据资格是三个独立状态轴。
7. 安全停止红线优先于进度、样本、效率和 ROI。

## 5. 设计选择与推荐契约

| 方案 | 优点 | 主要缺点 | 结论 |
| --- | --- | --- | --- |
| A. 继续手册 + Markdown/CSV | 无新代码 | 不能可靠保证不覆盖、顺序、分母和复算 | 拒绝作为 P1 目标设计 |
| B. 一个 `pilot-run` 编排所有系统 | 常见路径简单 | 把存储、Secret scanner、人工审批和发布权限混入核心 | 拒绝 |
| C. 深证据核心 + 薄 CLI | 权限小、可测、可复算，不复制现有规则 | 需新契约和聚合代码 | **推荐** |

推荐的最小公共接口：

```text
verify_change_bundle(bundle) -> ChangeEvidenceReport
compare_scopes(manual_scope, tool_scope) -> DifferenceDraft
validate_adjudication(record) -> AdjudicationStatus
summarize_iteration(frozen_index, evidence_reports, policy) -> IterationSummary
decide_round2(iteration_summaries, policy, approvals) -> StageRecommendation
```

接口只接受已解析的域数据；不连接远程存储、Git、Secret scanner、发布平台或 Embedded UI。
外部系统只能通过带 `source_ref/version/digest/status/approved_by` 的 attestation 输入。

```text
CLI / optional MCP adapter
        |
        v
Pilot Evidence Core
        +--> existing validation/risk/selection/agent/gate core
        +--> canonical digest + iteration/stage aggregation

Approved storage / scanner / release system --> versioned attestations only
```

建议的薄 CLI：

```text
qualityctl evidence verify-change <bundle-index.json> --output <new-report.json>
qualityctl evidence draft-diff <bundle-index.json> --output <new-draft.json>
qualityctl evidence validate-adjudication <adjudication.json> --output <new-status.json>
qualityctl evidence summarize-iteration <iteration-index.json> --output <new-summary.json>
qualityctl evidence decide-round2 <stage-index.json> --output <new-recommendation.json>
```

所有 `--output` 使用 exclusive-create；路径存在时返回结构化错误和 exit `2`，不改写原文件。

## 6. Pilot Evidence v1 数据契约

| 契约 | 作用 |
| --- | --- |
| `pilot-evidence-bundle@1.0` | 引用单个 pilot/change/run 的原始输入、时序和 attestation |
| `difference-draft@1.0` | 机器生成人工/工具范围差集，不填语义分类 |
| `adjudication@1.0` | 保留授权人的分类、证据、状态和时间 |
| `change-evidence-report@1.0` | 计算单变更资格、阻塞、停止触发和 digest |
| `iteration-summary@1.0` | 从冻结 change index 聚合迭代指标 |
| `round2-recommendation@1.0` | 计算 G1/G2/G3 和 Round 2 建议，不等于批准 |

`pilot-evidence-bundle@1.0` 至少包含：

- identity：`pilot_id/iteration_id/change_id/run_id/change_ref/version_type`；
- versions：core commit/version、Python、输入 Schema、catalog/mapping/policy/Agent fingerprint 版本；
- freeze：人工范围引用/digest、owner、`manual_frozen_at`；
- tool run：每次命令/工具的 request/response/stdout/stderr/exit code/start/end/ref/digest；
- ordering：`tool_started_at/tool_result_visible_at/unblinded_at/adjudicated_at`；
- attempts：首次 attempt、全部 rerun、out-of-plan 标记和各自 digest；
- attestations：Secret 扫描、受控存储、正式执行/发布结果、最小权限隔离引用；
- adjudication：difference draft、全部裁决版本、高风险关闭证明。

时间使用带时区 RFC 3339；时区缺失、格式非法或顺序无法证明时不进入主分母。

### 6.1 单变更状态

| 状态 | 含义 | 进入主分母 |
| --- | --- | --- |
| `ELIGIBLE` | 身份、冻结、版本、原始证据、时序、裁决和正式结果完整 | 是 |
| `EXCLUDED` | 存在预定义、可审计排除原因，原记录仍保留 | 否 |
| `BLOCKED` | 证据缺失/不一致/不兼容、策略未批准或高风险差异未关闭 | 否 |
| `STOP_TRIGGERED` | 符合 Round 2 停止红线 | 否；立即停止和隔离 |

`ELIGIBLE` 只表示样本有资格进主分母，不表示工具、测试或发布通过。

```text
if safety_stop_trigger:
    STOP_TRIGGERED
elif identity_or_contract_invalid:
    BLOCKED
elif manual_frozen_at >= first_tool_started_at:
    EXCLUDED(reason = EXCLUDED_PRE_FREEZE)
elif evidence_missing_or_digest_mismatch:
    BLOCKED
elif difference_unadjudicated or high_risk_difference_open:
    BLOCKED
elif approved_exclusion_reason:
    EXCLUDED
else:
    ELIGIBLE
```

高风险漏选、错误 `PASS`、Secret/未脱敏数据事件、未授权自动放行和原始证据覆盖
优先为 `STOP_TRIGGERED`，不得改成 `EXCLUDED` 规避停止。

### 6.2 Digest 和幂等

- artifact 按原始 bytes 计算 `sha256`，index 保留路径、媒体类型、大小和 digest；
- packet/decision digest 使用明确版本的 canonical JSON 规则；
- `generated_at`、本地根目录和显示文本不进入 decision digest；
- 同输入、策略、core 和 canonicalization 版本必须产生同 decision digest；
- 同 `pilot_id/change_id/run_id` 或同 evidence digest 不得重复计入分母；
- 重试是新 attempt，不是原 attempt 的覆盖或别名。

## 7. 兼容矩阵与演进

| 生产者/读取者 | 当前形态 | P1 目标 | 兼容要求 |
| --- | --- | --- | --- |
| manifest/catalog/agent producer | v1 输入 | 不改字段 | P1 只在外层引用，不改写输入 |
| 现有 CLI/MCP reader | v1 + 现有语义 | 继续可用 | 现有签名和状态不变 |
| Pilot Evidence writer | 不存在 | bundle/report 1.0 | 只增 index/report，不双写或转换 raw |
| Pilot Evidence reader | 不存在 | 严格读 1.0 | 未知 major 为 `BLOCKED`，未批准 minor 不默认兼容 |
| Embedded UI | 独立 spike | 不是 P1 reader | 不依赖 UI 的 compatibility/digest 实现 |
| 受控存储 | 待 G0 批准 | append-only raw + 新包装 | 唯一 ID、exclusive-create、审计、保留/删除 |
| 影子部署 | 非 required 手册/MCP | 非 required 薄 CLI | 无发布凭据；失败不阻塞正式路径 |

P1 分母的 pinned matrix 为 manifest/catalog/agent spec `1.0`、Pilot Evidence `1.0`、
`qualityctl 0.1.x` 中经 P1 签署的具体 commit。Agent run 仍通过冻结 spec 和重算 digest 绑定。

1. **Expand readers**：新增 Schema、验证器、canonical digest 和 exclusive-create writer；不改旧签名。
2. **Migrate writers**：通过 fixture 和双人审计后，只在新真实 `run_id` 写 index/report。G0 演练不迁入分母。
3. **Observe**：至少 2 个候选合格变更同时保留 verifier 和两名授权人独立复算；任何差异使 G1 保持未通过。
4. **Contract**：Round 2 内不删当前模板、v1 输入、旧 CLI/MCP 或 headless fallback；G3 后另立改版 Spec。

回退时停止新 writer、保留已写入记录、回到手册和正式人工流程；不删除或改写已有证据。

## 8. 端到端工作流

```mermaid
flowchart LR
    A["G0 签署 + Day 0"] --> B["eligible change 台账"]
    B --> C["人工范围冻结"]
    C --> D["输入/策略冻结"]
    D --> E["旁路运行现有 core"]
    E --> F["不可覆盖 bundle/report"]
    F --> G["解盲 + 差异草稿"]
    G --> H["授权人裁决"]
    H --> I["正式流程执行/发布"]
    I --> J["结果/成本 attestation"]
    J --> K["资格与迭代复算"]
    K --> L["G1/G2/G3 审计"]
```

每个变更必须按顺序执行：入台账 → 冻结人工范围 → 冻结输入/策略 → 运行现有 core →
生成首个 report → 解盲/差异草稿 → 人工裁决 → 现有正式流程 → 回填结果/全成本 →
重算最终资格。迭代结束时从冻结 index 生成 summary，不手工改汇总数字。

## 9. 工作包与可拆票

| 工作包 | 交付物 | 主要依赖 |
| --- | --- | --- |
| `P1-WP01` 契约硬化 | Schema、兼容矩阵、结构化错误、canonical digest | 脱敏 fixtures |
| `P1-WP02` 单变更证据 | verifier、exclusive writer、change report、catalog readiness | `WP01`，G0 用于真实运行 |
| `P1-WP03` 差异与台账 | difference draft、adjudication validator、eligible/excluded/attempt index | `WP02` |
| `P1-WP04` G1 | 至少 2 个候选变更、双复算和 G1 报告 | `WP01–03`，Day 14 |
| `P1-WP05` G2 | 迭代指标/ROI summary、目录修订记录、G2 报告 | G1，首完整迭代 |
| `P1-WP06` G3 | 8 周报告、G3 证据、唯一建议和签署 | G2，8 周/2 迭代/8 变更 |

| Ticket | 内容 | 完成判据 |
| --- | --- | --- |
| `P1-001` | 冻结 Pilot Evidence v1 Schema/错误 | JSON Schema/Pydantic fixtures 一致 |
| `P1-002` | 提取 canonical JSON/digest 到 core | 无 `plugins/.../embedded_ui` 反向依赖，golden digest 稳定 |
| `P1-003` | exclusive-create writer | 已有路径失败、原字节不变 |
| `P1-004` | 兼容和 catalog readiness | 未知 major、数量/质量不合格 fail-closed |
| `P1-005` | Agent 失败形状与输入 digest | Pilot verifier 将非 `ok` + `output` 标为 `BLOCKED`；fingerprint 不覆盖 digest 不一致 |
| `P1-006` | `verify-change` 与结构化 CLI 错误 | 顺序、缺证据、重复、I/O 失败有稳定状态/退出码 |
| `P1-007` | `draft-diff` + adjudication validator | 机器不自填分类；未裁决/高风险未关闭 fail-closed |
| `P1-008` | eligible/exclusion/attempt ledger | 全部候选、排除、重跑可定位，无重复分母 |
| `P1-009` | G1 两变更双复算 | 人工与 verifier 状态、分母、digest 一致 |
| `P1-010` | `summarize-iteration` | 指标从 raw 复算，零分母/缺数据为 `null/BLOCKED` |
| `P1-011` | G2 差异回流 | 目录/mapping/policy 新建版本，原证据不变 |
| `P1-012` | `decide-round2` | 硬门槛、样本、ROI、签署和停止规则可测 |
| `P1-013` | G3 最终包与三方签署 | 唯一决策，报告和状态文档一致 |

代码票可在 G0 阻塞期用脱敏 fixture 完成；`P1-009` 及之后的真实运行必须等待
`R2-G0_READY`。每票必须有 owner、due date、依赖、验收人、证据和回退方式。

## 10. Gate 与决策契约

### 10.1 `R2-G1 HEALTHY`

最早在 Day 14 且至少 2 个 eligible change 时审计。必须同时满足：

- G0 证据、Day 0 和三方签署仍有效；
- 前 2 个候选变更均有台账，不得事后替换“成功样本”；
- 至少 2 个最终为 `ELIGIBLE`，全部排除有预定义原因和证据；
- 人工与 verifier 对资格、分母、安全状态和 digest 的双复算一致；
- 四项安全红线均为 `0`；证据完整率为 `100%`；发生失败/重试时归因率和保留率为
  `100%`，未发生时为 `NOT_OBSERVED` 且计划运行/attempt ledger 能证明非漏采；
- 差异按 SLA 初判，无未关闭高风险差异；影子失败未影响正式路径。

唯一 Gate 输出：`R2-G1_HEALTHY / EXTEND_G1 / STOP`。`EXTEND_G1` 保留 Day 0，不补造样本。

### 10.2 `R2-G2 ITERATION_VALIDATED`

G2 只在 G1 通过且首个完整迭代结束后审计。迭代边界/index 必须冻结；每个合格变更
可追溯到 raw/freeze/attempt/adjudication/formal result；指标可独立复算；目录/mapping 缺陷以
新版本回流；高风险差异关闭；安全门槛和非 required 隔离仍成立。

唯一 Gate 输出：`R2-G2_ITERATION_VALIDATED / REPEAT_ITERATION / STOP`。

### 10.3 `R2-G3 DECISION_READY`

G3 只在 G2 通过，且至少 8 个自然日历周、2 个完整迭代和 8 个 eligible change
同时满足后审计。唯一 Gate 输出：`R2-G3_DECISION_READY / CONTINUE_OBSERVATION / STOP`。

`R2-G3_DECISION_READY` 后按上位 Spec 计算且只计算一个建议：

```text
if any_stop_condition:
    STOP
elif sample_or_period_incomplete:
    ADJUST_AND_REPEAT
elif any_safety_threshold_failed:
    STOP
elif any_required_metric_or_roi_threshold_failed:
    ADJUST_AND_REPEAT
elif maintenance_or_approval_capability_incomplete:
    ADJUST_AND_REPEAT
else:
    GO_LIMITED_GATE
```

没有三方签署时，该值仍是 `recommendation`，阶段状态保持 `DECISION_READY`。

## 11. 指标复算契约

| 指标 | 必需口径 | 缺数据行为 |
| --- | --- | --- |
| 证据完整率 | 完整 eligible / 全部 eligible | 分母 0 或报告缺失为 `null/BLOCKED` |
| 运行可用率 | 无 runner/environment 无效的计划运行 / 全部计划运行 | 计划运行未记录为 `BLOCKED` |
| 失败归因率 | 已分域有效失败 / 全部有效失败 | 无失败为 `NOT_OBSERVED`，不伪造 100% |
| 重试保留率 | 完整保留全 attempt 的重试组 / 全重试组 | 无重试为 `NOT_OBSERVED` |
| 工具误报率 | `TOOL_FALSE_POSITIVE` / 工具新增项 | 分母 0 为 `null` |
| 净节省 | 毛节省 - 维护/误报/flaky/runner/LLM/数据成本 | 必需成本缺失为 `BLOCKED` |
| 回本月数 | 一次性建设分钟 / 月净节省 | 净节省 `<= 0` 为 `NOT_COMPUTABLE` |

四项安全硬门槛保持 `0`；“未观测”不等于“观测值 0”，主分母不完整时保持
`PENDING_NOT_STARTED/NOT_OBSERVED`。

## 12. 功能验收场景

| 编号 | 场景 | 预期 |
| --- | --- | --- |
| `P1-AC-001` | G0 阻塞却传入真实包 | `BLOCKED_BY_R2_G0`，不启动时钟 |
| `P1-AC-002` | 输出路径已存在 | exit `2`，原文件字节不变 |
| `P1-AC-003` | 未知 major，raw Gate 为 `PASS` | Pilot report `BLOCKED/UNSUPPORTED_SCHEMA`，`formal_release_effect=NONE` |
| `P1-AC-004` | catalog 为 29/51 条、缺 Oracle/来源/评审或伪造全维覆盖 | catalog readiness 失败，不因 v1 结构通过而准入 |
| `P1-AC-005` | 非 `ok` Agent run 携带 `output` | 现有 v1 reader 行为不变；Pilot report 为 `BLOCKED/INVALID_AGENT_FAILURE_EVIDENCE`，不传播 stale/raw output |
| `P1-AC-006` | fingerprint 一致但冻结内容 digest 不一致 | `BLOCKED`，以重算 digest 为准 |
| `P1-AC-007` | `manual_frozen_at >= tool_started_at` | `EXCLUDED_PRE_FREEZE`，保留但不进分母 |
| `P1-AC-008` | 重跑成功但首次失败缺失/改写 | `STOP_TRIGGERED` |
| `P1-AC-009` | 存在未裁决或未关闭高风险差异 | change `BLOCKED`，G2/G3 不通过 |
| `P1-AC-010` | 重复 change/run ID 或 evidence digest | 不重复计分母，记录冲突 |
| `P1-AC-011` | 分母为 0 | 比率/时间/ROI 为 `null/BLOCKED` |
| `P1-AC-012` | 工具运行失败 | 生成可审计失败报告，不改正式发布结果 |
| `P1-AC-013` | 停止红线任一发生 | `STOP_TRIGGERED`，阶段建议 `STOP` |
| `P1-AC-014` | Day 14 只有 1 个 eligible | `EXTEND_G1`，不复制/拆分样本，不重置 Day 0 |
| `P1-AC-015` | 8 周只有 7 个 eligible | `CONTINUE_OBSERVATION`/`ADJUST_AND_REPEAT`，不声称 G3 完成 |
| `P1-AC-016` | 期间/样本/安全/ROI 全达标 | 只生成 `GO_LIMITED_GATE` 建议；签署前保持 `DECISION_READY` |
| `P1-AC-017` | 只有 `generated_at` 不同 | decision digest 相同 |
| `P1-AC-018` | Pydantic 与 JSON Schema 使用同 fixture | 通过/拒绝结果一致 |

## 13. 非功能与安全要求

| 编号 | 要求 |
| --- | --- |
| `P1-NFR-001` | 同输入、策略、core 和 canonicalization 版本产生同 decision digest |
| `P1-NFR-002` | writer 默认 exclusive-create，不存在 silent overwrite 选项 |
| `P1-NFR-003` | 所有错误包含 `ok/kind/code/message/paths/errors`，不要求解析自由文本 |
| `P1-NFR-004` | Pipeline 只读 raw，只在新目标写 report，不持有发布/回滚/写入凭据 |
| `P1-NFR-005` | 真实证据位于受控存储，仓库只保留 Schema、脱敏 fixture 和模板 |
| `P1-NFR-006` | 单变更和迭代聚合从 raw 重算，不信任调用方自填汇总 |
| `P1-NFR-007` | 时间为带时区 RFC 3339；clock 可在测试中注入固定值 |
| `P1-NFR-008` | 新代码支持 Python 3.10+，至少在 Python 3.11 CI 验证，不降低现有 124 项基线 |
| `P1-NFR-009` | 保留五 MCP 和现有 CLI 兼容性；新错误契约不静默改旧输出 |
| `P1-NFR-010` | 影子任务非 required；资源/运行器失败不延长正式发布关键路径 |
| `P1-NFR-011` | 聚合按稳定 ID 排序；本地路径、时间和并发顺序不引起 digest 漂移 |
| `P1-NFR-012` | 安全扫描为外部 attestation；只保留结果、版本和引用，不传播 Secret 内容 |

## 14. 验证策略

- JSON Schema/Pydantic 对同一组 positive/negative fixture 结果一致；
- 单元测试覆盖状态优先级、时序、digest、零分母、重复、ROI 和签署前后；
- CLI 集成测试覆盖新建、已存在、权限拒绝、坏 JSON、缺文件和中途失败；
- 本地临时目录测试覆盖首次/重跑/裁决/汇总全链路与不覆盖；
- 测试 initial、expanded、observed、Round 2 final 以及 rollback/forward-fix 五种兼容状态；
- 保留现有 risk/selection/agent/gate/MCP/Embedded UI 测试，证明旧契约不变。

必运行基线：

```powershell
python -m unittest discover -s tests -v
python plugins/quality-gatekeeper/scripts/smoke_test.py
python plugins/quality-gatekeeper/embedded_ui/smoke_test.py
git diff --check
```

P1 新 CLI 还必须有一个全脱敏端到端 fixture smoke。Embedded UI smoke 只验证未回归，不将 UI
扩展、Desktop 稳定性或用户价值纳入 P1 交付。

## 15. 运行节奏、暂停和恢复

| 时点 | 最低动作 | 不得声称 |
| --- | --- | --- |
| G0 阻塞期 | 评审 Spec，用脱敏 fixture 完成 `P1-001`–`P1-008` | 真实试点已启动 |
| Day 0 | 验证 G0 签署、冻结矩阵、写首个计划变更 | G1/G2/G3 已通过 |
| Day 0–14 | 新 run ID 旁路运行，差异 2 工作日内初判 | 样本不足时的收益/召回结论 |
| Day 14+ | G1 审计；未足则延长观测 | 随时间推进自动获得 HEALTHY |
| 每完整迭代 | 冻结 index、聚合指标、关闭高风险差异 | 手工改汇总或回写 raw |
| Day 56+ | 只在 2 迭代/8 eligible 和指标完整时审计 G3 | 时间到即自动 GO |

`PAUSED` 只用于停止新影子采集并处置，不回写 Day 0、删除证据或改正式流程。恢复必须
包含根因、受影响分母、证据隔离、新版本/新 `run_id`、复验和授权批准。停止红线不得降级为
`PAUSED`。

## 16. 风险与缓解

| 风险 | 影响 | 缓解 |
| --- | --- | --- |
| raw `release_allowed=true` 被当正式放行 | 未授权发布 | P1 产物固定 `formal_release_effect=NONE` |
| 未知 Schema 仍 raw PASS | 不兼容数据进分母 | Pilot compatibility 独立 fail-closed，只允许 pinned matrix |
| 覆盖消除首次失败 | 重试偏差、无法审计 | exclusive-create、attempt index、原字节不变测试 |
| 样本事后筛选 | 虚假高召回/低失败 | 变更进入时写 ledger，排除也必须有证据 |
| 计算器自动填裁决 | 权威越界 | 只生成 draft，分类/关闭由 RACI 责任人签署 |
| 人工模板与 summary 漂移 | 不可复算 | 机器 summary 是计算权威，Markdown 只渲染并引用 digest |
| 新模块变成平台/编排器 | 权限和维护面失控 | 纯核心 + 本地薄 CLI，外部系统只用 attestation |
| UI spike 成为核心隐式依赖 | Round 2 被视觉验证阻塞 | 通用算法提取到 core，P1 不 import plugin/UI，UI 冻结 |
| 扫描内容被传播进报告 | 二次泄漏 | 只保留 scanner 结果、版本、digest 和受控引用 |

## 17. Definition of Done

P1 只有在以下条件同时满足时完成：

- `R2-G0_READY` 与 P1 激活证据可定位，Day 0 未被修改；
- Pilot Evidence v1 Schema/Pydantic、canonical digest、exclusive writer 和 CLI 契约已验证；
- 兼容、catalog readiness、Agent 失败形状和全部结构化错误 fail-closed；
- 所有 eligible/excluded/out-of-plan/attempt 进冻结索引，原始证据无覆盖；
- 完成至少 8 周、2 完整迭代和 8 eligible change；
- 每个 eligible 有人工冻结、工具证据、全重跑、差异裁决和正式结果；
- G1/G2/G3 的指标和状态可从 raw 重算；安全硬门槛全满足；
- 维护、误报、flaky、runner、LLM/运行和数据成本均进 ROI；
- 形成且只形成一个允许建议和三方批准记录；
- 新测试、现有 124 项基线、MCP smoke、脱敏 E2E smoke 和格式检查全通过；
- README、Round 2 总体 Spec、P0/G0 状态、迭代 summary 和最终报告与批准事实一致。

`GO_LIMITED_GATE` 仍只授权编写下一个有限硬门禁 Spec，不在 P1 内自动启用硬门禁。

## 18. 待评审决策

1. Pilot Evidence v1 的 owner、版本策略和 writer/reader 矩阵；
2. catalog readiness 中 Oracle、来源、双人评审、维度覆盖和历史逃逸口径；
3. Secret scanner 的权威来源、attestation 形状、有效期和失败处置；
4. 正式执行/发布结果的只读权威来源和引用形状；
5. 受控存储的 exclusive-create/append-only 能力及等价控制；
6. P1 CLI 是否只保留本地适配器，是否需要不扩权的 optional MCP 读取适配器；
7. 至少 2 个变更的双人独立复算责任人和差异升级路径；
8. 最终报告的三方签署载体、批准有效期和状态文档更新责任。
