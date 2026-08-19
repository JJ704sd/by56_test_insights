# qualityctl Round 3 Execution Spec：受控有限硬门禁 Harness、可信策略与可回退准入

| 项目 | 内容 |
| --- | --- |
| 文档版本 | v0.1 Design Draft |
| 当前状态 | DESIGN_ONLY / NOT_ACTIVATABLE |
| 日期 | 2026-08-19 |
| 仓库基线 | codex/record-desktop-inline-proof@a603f2e501601a3e9ae1494920983de318f1db3a |
| 当前业务状态 | R2-G0 = REMAIN_BLOCKED；0/9 READY；8 周影子时钟未启动 |
| 当前工程状态 | P1b fixture 能力已提交；P1c stage core/CLI 未实现、未获激活许可 |
| 当前实施许可 | 只允许本 Spec 评审和只读 inventory；不授权 fixture core、CI adapter、required check 或 branch protection 变更 |
| 上位文档 | [Round 2 Shadow Pilot Spec](round-2-shadow-pilot-spec.md)、[P1b Spec](round-2-p1b-iteration-summary-spec.md)、[P1c Spec](round-2-p1c-stage-recommendation-harness-spec.md) |
| 参考设计 | DeepSeek Harness 99f6f02；只借鉴约束，不建立源码或运行时依赖 |
| 本阶段候选输出 | limited-gate-index@1.0、limited-gate-policy@1.0、limited-gate-report@1.0、可选 waiver、append-only receipt、薄 CI adapter |
| 明确不含 | 自动发布、自动放行、自动回滚、风险接受、动态插件、通用 Agent runner、远程 MCP、UI 扩展 |

## 1. 结论先行

Round 3 的目标不是把现有 PASS 字段接到 required check，而是为一小组已批准、可重放、
确定性的安全规则建立受控执行边界。推荐设计是：

1. 使用冻结的 limited-gate-index 绑定变更、P1c recommendation、外部三方
   GO_LIMITED_GATE 决定、policy、check profile、证据和目标 CI scope；
2. 使用固定、不可动态扩展的 guarded core，从 raw → iteration → stage 逐层重验；
3. 只允许 input completeness、Schema/compatibility、冻结 identity/fingerprint、
   runner evidence completeness 和已批准的确定性高风险失败进入硬规则 allowlist；
4. STOP、BLOCKED 和 DENY 单调，任何后序检查、skill、LLM 文本、ROI 或多数票都不能将其改写为
   PASS；
5. evaluator 只读、无网络、无模型、无 MCP、无生产或发布凭据；CI 状态发布由隔离的薄
   publisher 完成；
6. 所有输入、报告、waiver 和 receipt 都是版本化、digest-bound、exclusive-create 的追加式
   artifact；修正只能生成新 artifact；
7. 从 DESIGN_ONLY 到 SHADOW、CANARY、LIMITED_ACTIVE 的每次迁移都需要外部授权，不自动晋级；
8. 门禁只能阻止一个批准 scope 内的变更，不能自行发布、部署、回滚或接受风险。

当前不满足 Round 3 激活条件。本稿只定义未来契约和验证路径，不表示 P1c 已完成，
不表示 Round 2 已得到 GO_LIMITED_GATE，也不授权创建 required check。

## 2. 当前事实与缺口

### 2.1 已验证的仓库能力

- 当前 Python API 是确定性风险、选集、Agent 聚合、Gate、证据和迭代汇总核心；
- CLI 已有 risk-check、select、agent-eval，以及五个 evidence 子命令；
- 生产 MCP 恰好为五个工具，面向 LLM 协作，不具备企业认证、签名策略源或 CI 发布权限；
- evidence/iteration 已具备严格 Pydantic 模型、JSON Schema、canonical digest、安全本地
  resolver、identity/digest 交叉核对、attempt 保留和 exclusive-create writer；
- P1b 能从冻结 iteration index 重算 iteration summary，并固定
  formal_release_effect=NONE、formal_release_allowed=false；
- 现有 Agent evaluator 只消费外部已采集的 AgentRun rows，不启动模型、工具、runner 或
  subagent；
- 当前 GitHub Actions 使用 Windows、Python 3.11、contents: read 和固定 action SHA，但安装
  方式仍是 editable checkout，不是已签发且带 hash 的 Gate binary。

这些能力适合成为 Round 3 的只读复算基础，不等于已经具备硬门禁。

### 2.2 不可直接作为 required check 的现有输出

以下信号包含人在环语义、缺少严格输出 envelope，或明确无发布效果，不能直接映射到 required
check：

- agent-eval 的总退出码、Wilson 区间、平均通过率和人工 semantic review；
- decide_release_gate 的整体 release_allowed；
- risk-check 或 select 的整体状态、未知风险、目录缺口和人工排除；
- ROI 的 CANDIDATE、正净收益或回本周期；
- P1/P1b/P1c 的 fixture、examples、单元测试或 CI 绿色状态；
- P1c stage recommendation 本身；
- skill 文本、MCP/LLM tool result、Embedded UI 或 Markdown 报告；
- runner_invalid 或 technical_failure；它们必须解释为证据不足，而不是产品 PASS。

### 2.3 当前硬阻塞

| ID | 阻塞事实 | 关闭证据 |
| --- | --- | --- |
| R3-BLK-001 | R2-G0 为 REMAIN_BLOCKED，0/9 READY | G0 九项全部有未过期批准记录和不可回写 Day 0 |
| R3-BLK-002 | P1B_REAL_SUMMARY_READY 不存在 | 首个真实完整迭代、受控存储、批准 policy、完整 raw、双人复算一致 |
| R3-BLK-003 | P1c stage core/CLI 未实现且激活门槛未批准 | P1c blockers 关闭，P1C_FIXTURE_VERIFIED |
| R3-BLK-004 | P1C_REAL_RECOMMENDATION_READY 不存在 | 真实 G1–G3 recommendation 可从 raw 独立重放 |
| R3-BLK-005 | 没有三方 GO_LIMITED_GATE 决定 | 外部批准载体精确引用 recommendation decision digest |
| R3-BLK-006 | hard-rule allowlist 和 trusted policy source 未批准 | owner、版本、digest、签名/平台身份、有效期与撤销规则 |
| R3-BLK-007 | 目标 CI/branch scope、check identity 和权限未冻结 | repo/branch/cohort/check-name inventory 与最小权限审计 |
| R3-BLK-008 | kill switch、rollback、通知和恢复 owner 未批准 | 演练记录、RTO、责任人、恢复审批 |
| R3-BLK-009 | 当前 compatibility matrix 仍含旧 core commit | exact producer/reader/core/adapter matrix 的批准迁移记录 |

任一阻塞存在时，activation_state 必须保持 NOT_ACTIVATABLE，ci_conclusion 必须为 null。

## 3. 激活公式与分层里程碑

### 3.1 激活公式

    R3_ACTIVATABLE =
        P1C_REAL_RECOMMENDATION_READY
        AND external_decision == GO_LIMITED_GATE
        AND external_decision.recommendation_digest matches recomputed digest
        AND approved_hard_rule_allowlist
        AND approved_policy_and_trust_root
        AND approved_target_ci_scope
        AND security_review_passed
        AND kill_switch_and_rollback_drilled
        AND exact_compatibility_matrix_approved

该公式由确定性 reader 校验，但其中的批准事实必须来自外部权威系统。qualityctl 不生成、
代签或推断任何批准。

### 3.2 四个里程碑

| 里程碑 | 含义 | 当前可达 |
| --- | --- | --- |
| R3_SPEC_REVIEWED | contract owner 关闭本 Spec 的必须决策；仍无代码许可 | 否 |
| R3_FIXTURE_VERIFIED | 仅脱敏 fixture 的 strict contracts、core 和 CLI 全部通过 | 否；需先获明确 fixture 实施许可 |
| R3_CANARY_READY | 真实 activation evidence、shadow parity、权限和回退演练齐全 | 否 |
| R3_LIMITED_GATE_ACTIVE | 显式变更审批后，仅对批准 cohort 启用 required check | 否 |

较早里程碑不能替代较晚里程碑。R3_FIXTURE_VERIFIED 不是业务证据，也不能自动推进到
CANARY 或 ACTIVE。

## 4. 目标与非目标

### 4.1 目标

1. 建立一个小而深的有限硬门禁核心，隐藏重放、身份、完整性、policy、单调状态和 digest。
2. 将进入硬门禁的规则限制在已批准 allowlist，不把整份质量报告变成阻塞条件。
3. 对每次评估记录可独立复算的 ordered check trace 和 source digest chain。
4. 分离 evaluator、publisher 和 branch-protection 配置权限。
5. 定义 SHADOW → CANARY → LIMITED_ACTIVE → PAUSED/ROLLED_BACK 的外部授权状态机。
6. 提供 fail-closed、可停用、可回退且不删除历史证据的运行方式。
7. 保持现有 Python API、旧 CLI、五个 MCP 工具、AgentRunV1 和 Embedded UI 语义不变。

### 4.2 非目标

- 不在本稿状态下创建 workflow required check 或修改 branch protection；
- 不自动发布、部署、合并、放量、回滚、关闭缺陷或接受风险；
- 不用 LLM Judge、semantic review、ROI、置信区间或自然语言决定硬门禁；
- 不启动 DeepSeek Harness、Cordis、Agent loop、subagent、模型或工具执行；
- 不开放动态 plugin、任意 hook、callback、entry point 或配置脚本；
- 不构建通用 Agent execution/trace 平台；
- 不接入远程 MCP、数据库、对象存储、审批 UI 或 Embedded UI；
- 不迁移、覆盖或删除 P1 raw、iteration summary、stage recommendation；
- 不扩大到未批准 repo、branch、组件、规则或 cohort；
- 不从 SHADOW 或 CANARY 自动晋级 ACTIVE；
- 不把 fixture、example、单元测试数量或 CI 绿色状态包装成业务批准。

## 5. DeepSeek Harness 参考基线与取舍

研究基线固定为 DeepSeek Harness
[99f6f02](https://github.com/deepseek-ai/deepseek-harness/tree/99f6f02fecdb7dff40c3fbc9470f5907c29f74ca)。
上游 README 明确其仍为 developer preview，会发生兼容性破坏，因此本项目只借鉴稳定设计
约束，不建立包、进程或运行时依赖。

| 上游设计 | Round 3 采用 | Round 3 不采用 |
| --- | --- | --- |
| model-visible means logged | enforcement-visible means digest-bound and independently reconstructable | 不复制对话 SessionEvent vocabulary |
| durable session/event 与 live agent/* 分离 | 冻结 decision artifacts 与 CI 运行状态分离 | 不建立 Agent live control API |
| pre → monotonic guards → execute → post → immutable result | preflight → auth/policy guards → replay → hard checks → finalizer → receipt | 不允许 post hook 反转拒绝 |
| capability seam 的 Definition/Provider/Consumer 三角色 | 固定 core、local evaluator consumer、隔离 publisher；有真实第二实现后才公开 port | 不为测试或假想 provider 建 registry |
| profile/bundle 的显式组合 | 冻结 check profile、policy、adapter 和 compatibility digest | 不支持用户 patch 或层叠覆盖安全规则 |
| skills catalog 与 durable facts 分离 | skills 只指导人和 Agent 收集/调用；不进入公式 | skill body 不成为批准或证据 |
| 并行执行、确定性提交 | 只可并行纯读取/重算；按冻结 ordinal 稳定提交 | 不让线程完成顺序影响 report digest |
| capability 缺失 fail loud | 未知版本、未签名、过期、缺 publisher contract 全部 fail-closed | 不 silent ignore 或自动降级 |

需要明确保留一个差异：DeepSeek Harness 强调没有 privileged core；质量硬门禁必须保留不可
旁路的 privileged safety core。安全 STOP、证据完整性、非发布效果和 allowlist 不能被插件、
profile、skill 或调用方覆盖。

参考资料：

- [Architecture](https://github.com/deepseek-ai/deepseek-harness/blob/99f6f02fecdb7dff40c3fbc9470f5907c29f74ca/docs/architecture.md)
- [Agent lifecycle](https://github.com/deepseek-ai/deepseek-harness/blob/99f6f02fecdb7dff40c3fbc9470f5907c29f74ca/docs/agent-lifecycle.md)
- [Tool execution pipeline](https://github.com/deepseek-ai/deepseek-harness/blob/99f6f02fecdb7dff40c3fbc9470f5907c29f74ca/docs/tool-execution-pipeline.md)
- [Approval seam](https://github.com/deepseek-ai/deepseek-harness/blob/99f6f02fecdb7dff40c3fbc9470f5907c29f74ca/docs/subsystems/approval.md)
- [Skills subsystem](https://github.com/deepseek-ai/deepseek-harness/blob/99f6f02fecdb7dff40c3fbc9470f5907c29f74ca/docs/subsystems/skills.md)
- [Developer preview notice](https://github.com/deepseek-ai/deepseek-harness/blob/99f6f02fecdb7dff40c3fbc9470f5907c29f74ca/README.md)

## 6. 权威边界与安全不变量

### 6.1 权威矩阵

| 事实 | 权威来源 | Round 3 可以做 | Round 3 不得做 |
| --- | --- | --- | --- |
| raw change/attempt/result | P1 append-only raw | 只读重验、引用 digest | 修改、补造、删除 |
| iteration metrics | 从 index 重算的 P1b summary | 重算并验证 lineage | 信任调用方百分比 |
| G1–G3 recommendation | P1c deterministic core | 重算并核对 digest | 将 recommendation 当批准 |
| GO_LIMITED_GATE | 外部三方批准载体 | 验证身份、签名/平台来源、TTL 和 digest binding | 生成、代签、延长 |
| hard-rule policy | 批准的 trusted policy source | 执行 exact allowlist | 添加默认规则或放宽 STOP |
| waiver | 外部授权载体，若被批准 | 验证精确 scope 和 TTL | 自动生成或适用于不可豁免项 |
| CI check publish | 隔离 publisher | 发布已验证 report 的投影 | 重算规则或改报告 |
| branch protection | 平台治理 owner | 读取 inventory | 自行创建、删除或改 required 状态 |
| skills | 协作说明 | 指导流程和工具调用 | 成为事实、批准或状态源 |

### 6.2 必须始终成立的不变量

1. enforcement-visible 的决定必须可从冻结 input、policy、profile、core 和 cutoff 独立重建。
2. raw、index、report、waiver 和 receipt 全部 exclusive-create；修正使用新 ID 和新 digest。
3. 同 input bytes、policy、profile、core、adapter 和 cutoff 必须得到同 decision digest。
4. generated_at、绝对路径、显示文本、线程完成顺序和 CI run URL 不进入 decision digest。
5. 任一 source bytes、identity、policy、profile order、approval 或 compatibility 改变必须改变
   digest 或使结果 BLOCKED。
6. 状态优先级固定为 STOP > BLOCKED > DENY > PASS；后序结果只能保持或收紧。
7. 未观测不是 0，缺证据不是 PASS，runner invalid/technical failure 不是产品失败也不是 PASS。
8. 未知 Schema、check、profile、policy、签名算法、trust root、adapter 或状态必须 fail loud。
9. fixture 的 activation_state 固定 NOT_ACTIVATABLE，ci_conclusion 固定 null。
10. evaluator 不持 checks write、branch administration、deployment、package publish、OIDC 或业务
    Secret。
11. publisher 不读取 raw、不重算规则，只消费并验证 report bytes/digest 和 activation state。
12. hard gate 只能作用于批准 cohort，不能授予发布、部署、回滚或风险接受权限。

## 7. 设计三次：候选契约

### 7.1 方案 A：直接把现有 Gate/CLI 退出码设为 required

调用路径最短，但现有 Gate 混合语义复核、阈值批准、风险 unknown、目录缺口等人在环事项；
输出没有完整的 schema/core/profile/policy/digest envelope，基础 input validator 也不是 Round 3
所需的 exact compatibility reader。

删除这层脚本不会隐藏复杂度，只会把错误映射散到 workflow。结论：拒绝。

### 7.2 方案 B：复制 DeepSeek 风格通用插件 Harness

建立 event bus、profile、bundle、dynamic plugin、runner、skill、sandbox、remote provider 和
tool pipeline，可以支持大量未来场景，但调用方需要理解庞大运行时和权限面。当前实际变化点只有
“一个批准 scope 的有限硬规则怎样可重放地阻塞”，没有真实第二 runner 或动态 policy provider。

结论：拒绝。上游仍处 developer preview，也不应成为生产 Gate 依赖。

### 7.3 方案 C：冻结 admission + 固定 guarded core + 薄 CI adapter

推荐公共核心保持一个深接口：

    evaluate_limited_gate(
        gate_index: Mapping[str, Any],
        *,
        base_dir: Path,
    ) -> Mapping[str, Any]

core 隐藏 strict validation、safe resolver、逐层重放、identity、approval、policy、check profile、
状态优先级、canonicalization 和 digest。薄 CLI 只做输入/输出/exit mapping；publisher 只发布
最终 report 投影。

优点：

- 旧 API/CLI/MCP 零语义变更；
- 规则不可被动态 hook 改写；
- evaluator 可以完全无网络、无 Secret、无写权限；
- report 可独立复算，publisher 故障不污染决定；
- 回退只需把外部 required 配置切回 shadow，历史 artifact 保留。

### 7.4 比较

| 维度 | A 直接退出码 | B 通用 Harness | C 固定 core + 薄 adapter |
| --- | --- | --- | --- |
| 接口深度 | 低 | 中 | 高 |
| 人在环边界 | 混杂 | 可配置、易漂移 | 固定分离 |
| 可重放 | 不完整 | 可实现但成本高 | 原生要求 |
| 权限面 | 易误扩 | 最大 | 最小 |
| 兼容风险 | 隐蔽 | 高 | 可分阶段 |
| 当前证据支撑 | 不足 | 不足 | 最强 |
| 推荐 | 否 | 否 | 是 |

## 8. 模块与信任边界

    external approval / policy authority
                |
                v
      limited-gate-index@1.0
                |
                v
      strict local reader + resolver
                |
                v
      fixed guarded evaluator core
                |
                v
      limited-gate-report@1.0
          |                 |
          v                 v
    append-only store   isolated publisher
                              |
                              v
                    CI check projection only

边界规则：

- evaluator 读取显式 artifact root 内的冻结本地引用；
- evaluator 不访问网络，不调用 MCP、模型、subprocess 或平台 API；
- publisher 不拥有 core，不读取 policy/raw，不允许改变 decision；
- branch protection 由平台 owner 管理，不是 adapter 功能；
- local resolver 暂时是唯一 provider。出现真实第二存储实现后，才另立 ArtifactReader
  Definition/Provider/Consumer 设计，不预建 registry。

## 9. 版本化契约

所有顶层和嵌套对象默认 additionalProperties=false / extra=forbid。Pydantic 与 JSON Schema
必须对同一 positive/negative fixture 得到一致结果。

### 9.1 limited-gate-index@1.0

index 是冻结引用清单，不是调用方自填结论。至少包含：

| 字段组 | 必需内容 |
| --- | --- |
| identity | repo_id、revision、change_id、pilot_id、cohort_id |
| freeze | frozen_at、frozen_by、freeze projection version、digest |
| activation | requested mode、kill-switch snapshot、target check identity |
| stage | stage index/recommendation refs、bytes digest、decision digest |
| approval | external decision ref、digest、roles、issued/expiry、trust envelope |
| policy | limited-gate-policy ref、bytes digest、policy digest |
| profile | exact ordered check ids/versions、profile digest |
| versions | schema/core/adapter/canonicalization/wheel/hash matrix |
| evidence | manifest/catalog/agent/evidence/iteration refs 和 digest |
| cutoff | evaluation_cutoff_at，带时区并冻结 |
| output | 专用 report directory 和 exclusive-create target |

约束：

1. stage recommendation 必须由 P1c core 从 stage index 重算；
2. approval 必须精确引用重算的 recommendation decision digest；
3. repo/revision/change/pilot/cohort 在所有证据中一致；
4. 绝对路径、..、junction/symlink escape、URL、未知 media type 或 digest mismatch 全部拒绝；
5. 同一 artifact identity 或 bytes digest 不得在不允许的位置重复；
6. evaluation_cutoff_at 进入 decision digest，运行墙钟只用于 generated_at；
7. fixture 和 DESIGN_ONLY index 不能请求真实 publish。

### 9.2 limited-gate-policy@1.0

policy 至少包含：

- policy_id/version/digest；
- owner、批准角色、批准载体、issued_at/expires_at/revoked_at；
- trust root、verification method 和 verifier version；
- target repo/branch/cohort/check identity；
- 固定 hard-rule allowlist、每项 check id/version/severity；
- 不可豁免 code；
- shadow/canary/active 模式与最大 cohort；
- fail-closed、infra outage、timeout 和 cancellation 处理；
- kill-switch owner、RTO、notification route；
- waiver 是否允许、签署角色、最大 TTL 和适用 code；
- audit retention、data classification 和 access group。

policy 不得包含可执行脚本、表达式、任意 callback、插件路径或动态 import。

### 9.3 CheckResultV1

每个 check 使用固定形状：

    {
      "id": "R3-CHECK-...",
      "version": "1.0",
      "status": "PASS | DENY | BLOCKED | STOP",
      "code": "STABLE_MACHINE_CODE",
      "message": "display only",
      "source_refs": [],
      "source_digests": []
    }

check 按 profile ordinal 稳定排序。message 不进入 decision digest；id、version、status、code、
refs 和 digests 必须进入。

### 9.4 limited-gate-report@1.0

至少包含：

- contract/schema_version；
- identity、activation_state、evaluation_mode；
- decision：PASS / DENY / BLOCKED / STOP；
- ci_conclusion：success / failure / null；
- ordered check_results；
- source refs/digests、stage recommendation digest、approval/policy/profile digest；
- core/adapter/canonicalization/wheel/hash identity；
- decision_digest；
- formal_release_effect=NONE；
- formal_release_allowed=false；
- formal_deploy_effect=NONE；
- risk_accepted=false；
- generated_at。

只有 activation_state=LIMITED_ACTIVE 且 report 通过全部 publisher preflight 时，
ci_conclusion 才允许非 null。CANARY 可发布非 required 的观察性状态，但不能伪装成 active。

### 9.5 limited-gate-waiver@1.0

默认不启用 waiver。只有 contract owners 显式批准后，才允许该契约进入实现。它必须：

- 绑定单一 repo/revision/change/cohort、原 decision digest 和可豁免 code；
- 记录外部签署角色、原因、issue/expiry、trust envelope 和 bytes digest；
- TTL 短于 policy 允许上限；
- exclusive-create，不能延长或原地修改；
- 不适用于 STOP、integrity、signature/trust、mixed identity、evidence overwrite、
  unauthorized release、secret event 或 kill switch；
- 只改变 CI projection，不改写原 report/check result。

### 9.6 limited-gate-receipt@1.0

receipt 是 adapter/publisher 的追加式审计产物，不是 core 输入。它至少记录：

- receipt_id、event_kind、previous_receipt_digest；
- report bytes/decision digest；
- adapter/publisher identity；
- target check、CI run/build identity；
- requested/published conclusion；
- platform response ref；
- occurred_at、receipt digest。

允许的 event_kind 为 EVALUATED、PUBLISH_ATTEMPTED、PUBLISHED、PUBLISH_FAILED、PAUSED、
ROLLED_BACK、WAIVER_APPLIED。event chain 断裂、重复或乱序必须被审计工具报告。

### 9.7 Digest 规则

业务 digest 包含 identity、activation mode、cutoff、policy/profile/approval、ordered checks、
source digests、core/adapter/canonicalization identity。它排除 generated_at、message、绝对路径、
CI URL 和平台展示文本。

任一 digest 投影必须有独立 canonical bytes 向量，不能把 artifact 自身 bytes digest 回填到同一
artifact 后再计算自身。

## 10. 硬规则 allowlist

初始 allowlist 只能从以下类别中选择，并逐项获得 owner 批准：

| 类别 | 允许阻塞的事实 | 不允许扩展 |
| --- | --- | --- |
| INPUT_CONTRACT | 缺必需输入、未知/非法 Schema、未知状态 | 业务语义是否合理 |
| COMPATIBILITY | core/adapter/profile/policy/wheel/hash 不在 exact matrix | 自动接受 newer/latest |
| FROZEN_IDENTITY | mixed repo/revision/change/pilot/cohort/fingerprint | 模糊名称相似匹配 |
| ARTIFACT_INTEGRITY | path/media/size/digest/append-only 违反 | 读取未冻结在线数据 |
| EVIDENCE_COMPLETENESS | planned sample/attempt/trace 缺失、重复或额外 | 把少样本平均成 PASS |
| RUNNER_COMPLETENESS | runner_invalid、technical_failure、环境证据缺失 | 将其记作产品失败或成功 |
| DETERMINISTIC_HIGH_RISK | 预先批准的 exact/schema/rule/permission/idempotency 断言失败 | LLM Judge 或人工自由文本 |
| SAFETY_STOP | wrong PASS、确认高风险漏选、敏感数据、未授权放行、证据覆盖 | waiver 或 ROI 覆盖 |
| ACTIVATION_CONTROL | approval 过期/撤销、kill switch、scope 不匹配 | 自动扩大 cohort |

manual semantic review、风险接受、测试排除、阈值争议、ROI、平均分、推荐文案和低风险体验判断
只做 advisory，不得进入初始硬规则 allowlist。

## 11. 固定 Guarded Pipeline

执行顺序固定为：

1. strict parse：只接受 exact contract/version；
2. path/media/size/digest preflight；
3. activation、trust、approval、TTL、kill-switch 和 target scope guards；
4. compatibility、wheel/hash、core/adapter/profile guards；
5. raw → change → iteration → stage 逐层重放；
6. identity/fingerprint/attempt/runner evidence completeness；
7. deterministic high-risk allowlist checks；
8. monotonic status reduction；
9. immutable report finalizer 和 decision digest；
10. exclusive-create report；
11. adapter 外的 publisher 验证并发布 projection；
12. append-only receipt。

约束：

- guard 只能 PASS、DENY、BLOCKED 或 STOP，不能 force allow；
- 任一异常被规范化为稳定 BLOCKED/INTERNAL_EVALUATION_ERROR，不抛出后继续 PASS；
- STOP 后仍可运行只读诊断，但最终状态保持 STOP；
- 若未来并行重放，只允许纯读取/复算并行，结果按冻结 ordinal 提交；
- publisher、skill、UI、日志处理器和 post step 都不能修改 report decision。

## 12. 状态算法与 CI 映射

### 12.1 决定状态

| decision | 含义 | CLI exit | required projection |
| --- | --- | --- | --- |
| PASS | 全部批准硬规则通过 | 0 | success，仅 LIMITED_ACTIVE |
| DENY | 已完整评估且至少一个硬规则失败 | 1 | failure |
| BLOCKED | 无法可信评估、配置/证据/infra 不完整 | 2 | failure |
| STOP | 安全红线、完整性破坏或未授权行为 | 2 | failure，并触发人工暂停流程 |

状态优先级固定为 STOP > BLOCKED > DENY > PASS。

### 12.2 激活状态

| activation_state | ci_conclusion | 说明 |
| --- | --- | --- |
| DESIGN_ONLY | null | 只有设计/fixture catalog |
| SHADOW_ONLY | null | 可运行真实旁路对照，但不能 required |
| CANARY_READY | null 或非 required observation | 等待显式 canary 变更批准 |
| CANARY_ACTIVE | 非 required 或批准的小 cohort required | 只在批准窗口 |
| LIMITED_ACTIVE | success/failure | 仅批准 cohort |
| PAUSED | null | kill switch 或事故后停止发布 |
| ROLLED_BACK | null | required 配置已恢复为 shadow/off |

状态迁移不能由 evaluation result 自动完成。

### 12.3 伪代码

    validate exact contracts and safe artifact refs
    verify activation state, approval, trust, TTL, kill switch and scope
    verify exact compatibility and frozen check profile
    replay raw -> iteration -> stage and bind recommendation digest
    evaluate evidence completeness and approved deterministic hard rules

    if any safety stop or immutable evidence violation:
        decision = STOP
    elif any missing/untrusted/unknown/incompatible evidence:
        decision = BLOCKED
    elif any approved hard rule failed:
        decision = DENY
    else:
        decision = PASS

    if activation_state != LIMITED_ACTIVE:
        ci_conclusion = null
    else:
        ci_conclusion = success only for PASS, otherwise failure

## 13. 薄 CLI 与 publisher 边界

未来经批准后可新增 additive 入口：

    qualityctl ci evaluate <limited-gate-index.json> --output <new-report.json>

该名字在 contract review 时冻结。行为：

- input 只读，output exclusive-create；
- 只调用一次 deterministic core，不复制检查规则；
- stdout/stderr 使用稳定结构化 envelope；
- exit 0/1/2 按第 12 节映射；
- 不改现有命令、旧退出码、五个 MCP 工具或 Python exports；
- 不访问网络、模型、MCP、remote store 或 branch settings；
- 不发布 PR comment、不上传 artifact、不修改 check；
- 任何超时、异常、空输出或部分文件都为 BLOCKED，不能留下可误认的完整 report。

publisher 是独立 job/process：

1. 读取 report bytes；
2. 验证 schema、bytes digest、decision digest、activation state 和 target check；
3. 拒绝 DESIGN_ONLY/SHADOW/PAUSED/ROLLED_BACK；
4. 将 PASS 映射 success，将 DENY/BLOCKED/STOP 映射 failure；
5. 写 append-only receipt；
6. 不读取 raw、不执行 policy、不改变 decision。

生产 MCP 不新增第六个工具。CI 权威入口不能走面向 LLM 的 stdio MCP。

## 14. 认证、可信策略与最小权限

### 14.1 Trust 验证

真实激活必须选择并批准一种可验证的 trust mechanism，例如平台保护环境/审批记录、
签名 envelope 或具有不可伪造 build identity 的 artifact attestation。最终选择是 owner 决策，
不能由实施者默认。

验证器必须：

- 固定算法、trust root、key/platform identity、verifier version 和有效期；
- 检查撤销、expiry、scope、roles 和 digest binding；
- 缺 provider、未知算法、异常或网络不可用时 fail-closed；
- 不把调用方自填 approved=true 当作批准；
- 不在 evaluator 中持签名私钥。

### 14.2 权限

Evaluator job：

- contents: read；
- 工作区和下载 artifact 只读，只有专用 report 目录可写；
- 无 checks/write、pull-requests/write、contents/write、deployments、packages、id-token；
- 无业务 Secret；
- Python 3.11 + pinned wheel/hash + installed-version provenance；
- 不能用 editable checkout 作为 ACTIVE Gate binary。

Publisher job：

- 仅在平台确需时拥有 checks: write 和 contents: read；
- 使用短期、scope 限制的 token；
- 只消费验证通过的 report；
- 无 branch administration、merge、deployment 或 rollback 权限。

Branch protection / required check：

- 只能由治理 owner 通过独立变更单修改；
- adapter 和 publisher 都没有创建、删除或重命名 required check 的权限；
- check identity 必须防止同名非权威 workflow 冒充。

## 15. Waiver、Kill Switch、暂停与恢复

### 15.1 Waiver

默认策略为 no-waiver。若批准 waiver：

- 只能由外部角色签发；
- 只针对明确可豁免 DENY code；
- 不适用于 STOP、BLOCKED 的 trust/integrity/unknown/expired 类错误；
- 绑定单一 decision digest 和短 TTL；
- 原 report 不变，publisher 显示 waiver projection 并记录 receipt；
- 到期后自动失效，但系统不自动延长。

### 15.2 Kill Switch

kill switch 必须位于 evaluator 无权修改的可信控制面。命中后：

- activation_state 立即为 PAUSED；
- ci_conclusion 不再发布；
- required 配置按批准 runbook 转回 shadow/off；
- 保存所有 raw、report、receipt 和平台响应；
- 通知 owner，并按 RTO 完成状态确认。

### 15.3 恢复

恢复必须使用新 approval、新 index、新 report 和新 receipt。不得重写事故前 artifact，也不得
重置 Round 2 Day 0 或删除失败样本。恢复到 LIMITED_ACTIVE 必须有外部变更审批和回退演练复核。

## 16. 生命周期与上线节奏

    OFF / DESIGN_ONLY
          |
          | explicit spec + fixture authorization
          v
    FIXTURE_VERIFIED
          |
          | real Round 2 GO + activation evidence
          v
    SHADOW_ONLY
          |
          | parity + security + rollback approval
          v
    CANARY_READY
          |
          | explicit change approval
          v
    CANARY_ACTIVE
          |
          | observation window + zero wrong-PASS + owner sign-off
          v
    LIMITED_ACTIVE
          |
          +------> PAUSED ------> ROLLED_BACK

规则：

- 每条箭头都需要版本化批准载体；
- 不允许基于测试绿、时间到或样本多数自动晋级；
- canary 只包含批准的 repo/branch/cohort/check；
- 扩大 cohort 是新的变更，不是配置默认；
- PAUSED/ROLLED_BACK 后不自动恢复。

## 17. 兼容矩阵与迁移

### 17.1 Producer / Reader / Storage / Deployment

| 边界 | 当前 | Round 3 目标 | 兼容要求 |
| --- | --- | --- | --- |
| manifest/catalog/agent_spec/run | v1 既有 | 保持 | 不新增必填字段，不改旧 reader |
| P1 raw/report/ledger | strict v1 | 只读复用 | 不覆盖，不 dual-write |
| iteration index/summary | strict v1 | 只读重放 | formal_release_effect 保持 NONE |
| stage index/recommendation | 不存在 | 先由 P1c 实现 | Round 3 不绕过 P1c |
| limited gate index/report | 不存在 | additive sidecar v1 | 未知 version fail-closed |
| MCP | 五个工具 | 保持五个 | 不作为 CI authority |
| CLI | 旧命令 | additive ci 子命令 | 旧签名/exit 不变 |
| CI evaluator | editable checkout tests | pinned wheel/hash | exact installed provenance |
| publisher | 不存在 | 隔离最小权限 | 不拥有 evaluator rules |
| branch protection | 外部未知 | 批准 inventory | 只由治理 owner 修改 |

### 17.2 Expand → Migrate → Observe → Contract

1. Expand：新增 strict sidecar Schema/reader、fixture report 和 compatibility diagnostics；旧入口不变。
2. Migrate：只用脱敏 fixture 产出 DESIGN_ONLY report；没有真实 publisher 或 required check。
3. Observe：在获得真实 GO 后，对同 revision 做 shadow replay，与批准人工流程逐项解释差异。
4. Contract：只有 CANARY_READY、变更审批、权限/回退演练和观察窗口满足后，才让唯一 pinned
   report reader 驱动批准 cohort 的 required check。

不得 dual-write 两个权威状态。raw 仍是事实源；report 是可重建派生产物；平台 check 只是 report
投影。

收缩旧兼容路径的条件：

- consumer inventory 完整；
- 所有支持 reader 理解保留版本；
- 没有真实记录依赖旧 draft；
- replay、downgrade/forward-fix 和 rollback fixture 通过；
- contract owners 显式批准。

## 18. Skills 使用边界

本 Spec 使用 codebase-design 比较 caller-visible contract/seam，并使用 evolving-contracts 固定
producer-reader-storage-deployment 矩阵和 Expand → Migrate → Observe → Contract 过渡。

后续执行应按以下边界使用 skills：

| Skill | 用途 | 不得替代 |
| --- | --- | --- |
| grilling | contract owners 在场时关闭权威来源、allowlist、waiver、scope 和回退决策 | 不查询仓库可发现事实，不代签批准 |
| codebase-design | 复核 core、CLI、publisher 和真实 seam | 不为假想 provider 建抽象 |
| evolving-contracts | 管理 sidecar/reader/CI mixed-version 过渡 | 不跳过兼容证据 |
| tdd | contract 获批后，从稳定公共 seam 写失败测试 | 不在授权前实现 |
| review-code-against-spec | fixture 或 canary 完成后独立两轴审查 | 不替代真实 activation evidence |
| quality-gatekeeper | 组织风险、选集、Agent、ROI 和最终证据 | 不成为 release authority |
| quality-agent-evaluation | 冻结 spec/runs 并分离失败域 | 不启动 runner，不将语义评分硬门禁化 |
| quality-risk-review | 八维风险和 Agent 适用性记录 | 不发明 exemption |
| quality-regression-planning | 可解释选集和 coverage gap | 不自行增删测试凑平衡 |
| quality-automation-roi | 评估是否值得自动化 | 不覆盖安全门或决定发布 |

skill body 永远不是 durable fact。只有 skill 指导下调用确定性工具后生成并冻结的 artifact 才可被
index 引用。

## 19. 工作包与授权边界

| Ticket | 内容 | 完成判据 | 当前许可 |
| --- | --- | --- | --- |
| R3-PRE-001 | 同步 P1b/P1c/G0 状态与 a603f2e exact-SHA CI | 文档、CI URL/log、revision 一致 | 只读审计可做；写入需单独任务 |
| R3-PRE-002 | 关闭本 Spec authority/allowlist/trust/scope 决策 | 版本化 owner 决议 | 未开始 |
| R3-001 | 冻结四个核心 contract 与 digest 向量 | contract review + vectors | 未授权 |
| R3-002 | strict Pydantic / JSON Schema parity | positive/negative parity | 未授权 |
| R3-003 | fixed guarded evaluator core | monotonic/replay/property tests | 未授权 |
| R3-004 | additive thin CLI | exit/envelope/exclusive-create E2E | 未授权 |
| R3-005 | DESIGN_ONLY fixture catalog | initial/mixed/expired/tampered/rollback | 未授权 |
| R3-006 | compatibility observation | 旧入口 golden + mixed-version matrix | 未授权 |
| R3-007 | pinned build provenance | wheel/hash/SBOM 或批准等价物 | 未授权 |
| R3-008 | SHADOW evaluator deployment | 无 CI conclusion/required effect | 依赖真实 GO |
| R3-009 | isolated publisher + receipts | 权限审计和 publisher contract | 依赖 CANARY_READY |
| R3-010 | kill-switch/rollback drill | RTO、通知、证据和恢复点 | 依赖真实环境 |
| R3-011 | limited canary | 批准 cohort、观察窗口、0 wrong-PASS | 依赖显式变更批准 |
| R3-012 | LIMITED_ACTIVE | owner 签署、required 配置和恢复证据 | 依赖全部前项 |

当前只授权本 Spec 文档工作。表中“未授权”不能被解释为默认可开始。

## 20. 功能验收场景

| ID | 场景 | 预期 |
| --- | --- | --- |
| R3-AC-001 | exact valid DESIGN_ONLY fixture | 可生成 report，但 activation_state=NOT_ACTIVATABLE、ci_conclusion=null |
| R3-AC-002 | 未知 schema major/minor | BLOCKED/UNSUPPORTED_CONTRACT |
| R3-AC-003 | extra field | Pydantic 与 JSON Schema 同时拒绝 |
| R3-AC-004 | 绝对路径、.. 或 symlink/junction escape | BLOCKED/UNSAFE_ARTIFACT_PATH |
| R3-AC-005 | media/size/bytes digest mismatch | BLOCKED/ARTIFACT_INTEGRITY_ERROR |
| R3-AC-006 | repo/revision/change/pilot/cohort 混合 | BLOCKED/MIXED_IDENTITY |
| R3-AC-007 | recommendation bytes digest 正确但 decision digest 伪造 | BLOCKED/RECOMMENDATION_DIGEST_MISMATCH |
| R3-AC-008 | 外部 GO 未引用重算 recommendation digest | BLOCKED/APPROVAL_BINDING_MISMATCH |
| R3-AC-009 | approval 缺签名/平台身份、过期或撤销 | BLOCKED/UNTRUSTED_APPROVAL |
| R3-AC-010 | kill switch active | STOP/KILL_SWITCH_ACTIVE，ci_conclusion=null |
| R3-AC-011 | core/adapter/profile/policy/wheel/hash 未批准 | BLOCKED/UNSUPPORTED_COMPATIBILITY |
| R3-AC-012 | check profile 缺项、重复、未知或重排 | BLOCKED/CHECK_PROFILE_MISMATCH |
| R3-AC-013 | missing/extra/duplicate attempt 或 mixed fingerprint | BLOCKED/INCOMPLETE_EVIDENCE |
| R3-AC-014 | runner_invalid 或 technical_failure | BLOCKED/RUNNER_EVIDENCE_INCOMPLETE，不记产品 FAIL/PASS |
| R3-AC-015 | 已批准高风险 deterministic assertion 失败 | DENY/DETERMINISTIC_HIGH_RISK_FAILURE |
| R3-AC-016 | 只有 semantic review 失败 | 不进入硬规则；作为 advisory provenance |
| R3-AC-017 | 正 ROI 与 STOP 同时存在 | STOP，ROI 不反转 |
| R3-AC-018 | 后序 PASS、skill 文本或人工备注试图覆盖 DENY | 最终仍 DENY |
| R3-AC-019 | guard/check 抛异常 | BLOCKED/INTERNAL_EVALUATION_ERROR |
| R3-AC-020 | generated_at 改变 | decision digest 不变 |
| R3-AC-021 | source bytes、policy、approval 或 profile 改变 | digest 改变或 BLOCKED |
| R3-AC-022 | 随机打乱输入枚举或并行完成顺序 | canonical check order 和 decision digest 不变 |
| R3-AC-023 | duplicate/overlap 被排序掩盖 | fail-closed，不去重后 PASS |
| R3-AC-024 | output 已存在 | exit 2，原 bytes 不变 |
| R3-AC-025 | 中途写失败 | 不留下可被 reader 接受的完整 report |
| R3-AC-026 | SHADOW report 送 publisher | publisher 拒绝，不发布 success/failure |
| R3-AC-027 | publisher report bytes/digest 不一致 | 拒绝并写 PUBLISH_FAILED receipt |
| R3-AC-028 | waiver 试图覆盖 STOP/integrity/trust | 拒绝/WAIVER_NOT_APPLICABLE |
| R3-AC-029 | waiver 到期或 scope 不同 | 拒绝，不延长 |
| R3-AC-030 | ACTIVE 后 kill switch | 转 PAUSED，停止发布，runbook 回退 |
| R3-AC-031 | 回退后恢复 | 必须新 approval/index/report/receipt |
| R3-AC-032 | 旧 CLI/MCP/AgentRun/UI 回归 | 公开语义完全不变 |

## 21. 非功能、安全与 SLO

| ID | 要求 |
| --- | --- |
| R3-NFR-001 | 相同冻结输入产生相同 decision digest |
| R3-NFR-002 | evaluator 无网络、模型、MCP、动态 import、任意 callback 和业务 Secret |
| R3-NFR-003 | evaluator 与 publisher 权限隔离，前者无 checks write，后者无 raw access |
| R3-NFR-004 | 所有 writer exclusive-create，失败不留下合法半文件 |
| R3-NFR-005 | 真实 artifact 只在批准受控存储，仓库仅放 Schema/脱敏 fixture |
| R3-NFR-006 | 路径限制在显式 base_dir，防 traversal/symlink/junction escape |
| R3-NFR-007 | Python 3.11 为必验，ACTIVE binary 使用 pinned wheel/hash |
| R3-NFR-008 | 单次批准规模本地评估 p95 小于 10 秒，不含 artifact 下载和 CI 排队 |
| R3-NFR-009 | publisher 从 report 到平台响应 p95 小于 60 秒；超时 fail-closed |
| R3-NFR-010 | kill switch 到停止新 publish 的 RTO 由 owner 批准，建议不超过 15 分钟 |
| R3-NFR-011 | receipt chain 可检测缺口、重复、乱序和 digest mismatch |
| R3-NFR-012 | 不在 report/receipt 复制 Secret、prompt、原始业务 payload 或人工敏感备注 |
| R3-NFR-013 | 检查结果按 profile ordinal 稳定提交，完成顺序不影响 digest |
| R3-NFR-014 | 五个 MCP 工具和既有 CLI 数量/语义保持回归基线 |
| R3-NFR-015 | required check 同名冒充、workflow fork 权限和不可信 PR 事件有威胁测试 |

## 22. 验证策略

### 22.1 Fixture 层

- Pydantic/JSON Schema positive、negative 和 cross-field parity；
- canonical bytes 与独立 SHA-256 vectors；
- raw → iteration → stage → limited gate 全链路 replay；
- tampered/stale/mixed/expired/revoked/unknown/rollback fixtures；
- 状态单调性和输入顺序置换 property tests；
- path/media/size/digest/junction/symlink 安全测试；
- exclusive-create、partial failure、retry 和 recovery；
- CLI/core parity、stdout/stderr 和 0/1/2 exit golden；
- publisher 拒绝非 ACTIVE、digest mismatch 和 target mismatch；
- 旧 Python API、CLI、五 MCP、AgentRunV1、Embedded UI golden 回归。

### 22.2 Shadow / Canary 层

- 同 revision 下 report 与批准人工流程逐项可解释；
- 0 wrong-PASS、0 确认高风险漏选、0 未授权自动放行；
- runner invalid/technical failure 不进入 PASS；
- workflow permissions 静态审计和不可信 PR 威胁测试；
- evaluator/publisher token 隔离；
- kill-switch、publisher outage、check spoof、approval expiry 和 rollback 演练；
- 两名独立人员从冻结 inputs 复算同一 report/digest；
- canary 观察窗口、样本数和扩 cohort 条件由 owner 预先批准。

### 22.3 仓库命令

未来 fixture 实现后至少运行：

    python -m unittest discover -s tests -v
    python plugins/quality-gatekeeper/scripts/smoke_test.py
    python plugins/quality-gatekeeper/scripts/p1_evidence_smoke.py
    python plugins/quality-gatekeeper/embedded_ui/smoke_test.py
    git diff --check

还必须在 exact revision 的 Python 3.11 CI 中安装 pinned build artifact 并验证 installed version/hash。
测试数量只能作为回归快照，不能作为业务 Gate 证据。

## 23. 监控、停止条件与恢复证据

LIMITED_ACTIVE 期间至少监控：

- evaluation 总量及 PASS/DENY/BLOCKED/STOP；
- evidence incomplete、runner invalid、technical failure；
- wrong-PASS、高风险漏选、敏感数据和未授权行为；
- evaluator/publisher 延迟、timeout、平台错误；
- approval/policy/waiver expiry 和 trust verification failure；
- publisher/report digest mismatch；
- kill switch 响应时间、rollback 时间和 receipt chain gap；
- 对人工复核量、维护时间和误阻塞的影响。

立即 PAUSE 的条件：

- 任一 wrong-PASS 或确认高风险漏选；
- 任一未授权放行、敏感数据、证据覆盖或 trust bypass；
- 同名非权威 check 可满足 required；
- report 不能从 raw 独立重建；
- publisher 改写 decision 或发布错误 projection；
- kill switch/rollback 不能在批准 RTO 内生效。

恢复证据包括根因、影响 cohort/revisions、receipt chain、修复 revision、重放结果、权限复核、
回退演练和外部恢复批准。

## 24. 风险与缓解

| 风险 | 影响 | 缓解 |
| --- | --- | --- |
| 将现有整体 Gate 直接 required | 人在环事项被错误硬化 | 固定最小 allowlist 和 sidecar contract |
| 为参考 Harness 过度平台化 | 权限与兼容面失控 | 不依赖 Cordis/runtime，不开放动态插件 |
| caller 自填批准状态 | 未授权激活 | trust envelope + digest binding + fail-closed |
| editable checkout 被当已签发 binary | 运行内容与批准版本漂移 | pinned wheel/hash/installed provenance |
| evaluator 同时持 checks write | 规则与发布权限耦合 | evaluator/publisher 分离 |
| 同名 workflow 冒充 required check | 错误 PASS | check identity、事件来源和 branch policy 威胁测试 |
| infra outage 自动 fail-open | 未验证变更进入 | BLOCKED/failure；降级必须外部 break-glass |
| waiver 变成常规通道 | 安全规则被长期绕过 | 默认禁用、短 TTL、不可豁免 allowlist |
| 正 ROI/多数 PASS 覆盖红线 | 错误继续 | STOP/BLOCKED/DENY 单调 |
| 并行完成顺序进入 digest | 重放不一致 | 只并行纯计算，按 ordinal 稳定提交 |
| policy/profile 事后修改 | 结果选择偏差 | exact digest + 新 index/report |
| fixture 被误当业务证据 | 过早激活 | NOT_ACTIVATABLE + ci_conclusion=null |
| 回退删除失败证据 | 审计断裂 | append-only receipt，新 artifact 恢复 |

## 25. Definition of Done

### 25.1 R3_SPEC_REVIEWED

- 当前事实和 exact revision 已同步；
- 本 Spec 第 26 节必须由 owner 决定的事项全部有版本化批准；
- hard-rule allowlist、trust mechanism、target scope、check identity、waiver、kill switch 和回退已冻结；
- P1c blockers、Round 2 入场和真正的 Round 3 激活依赖没有被文字放宽；
- 明确记录 fixture 实施是否获准。

### 25.2 R3_FIXTURE_VERIFIED

- R3_SPEC_REVIEWED 且 fixture 实施获准；
- strict index/policy/report/receipt（及批准时的 waiver）Schema/Pydantic parity；
- canonical/digest vectors 与独立实现一致；
- fixed guarded core、薄 CLI、单调状态和 ordered trace 全覆盖；
- tampered/unknown/expired/mixed/path/partial-write 全部 fail-closed；
- fixture 固定 NOT_ACTIVATABLE、ci_conclusion=null；
- 旧 API/CLI/五 MCP/AgentRun/UI 回归全绿；
- Python 3.11 exact-SHA CI、三个 smoke、Embedded UI smoke、git diff --check 通过；
- 无 network/model/MCP/dynamic plugin/publisher/required-check side effect。

### 25.3 R3_CANARY_READY

- P1C_REAL_RECOMMENDATION_READY；
- 外部三方 GO_LIMITED_GATE 精确引用重算 recommendation digest；
- Round 2 最终报告和未关闭风险可定位；
- 真实 CI/branch/cohort/check inventory 与权限审计完成；
- pinned build provenance、trusted policy source 和 receipt store 可用；
- shadow replay 与人工流程差异 100% 可解释；
- 0 wrong-PASS、0 确认高风险漏选、0 未授权自动放行；
- kill-switch、publisher outage、check spoof 和 rollback 演练通过；
- 安全/隐私/授权无未关闭高严重度 finding；
- canary 范围、窗口、owner 和停止条件有显式变更批准。

### 25.4 R3_LIMITED_GATE_ACTIVE

- R3_CANARY_READY；
- canary 达到预先批准的自然窗口和样本，不复制样本；
- canary 没有 STOP，BLOCKED/误阻塞在批准门槛内；
- 人类变更单明确批准 limited cohort 的 required-check 激活；
- required check identity、publisher、监控、通知和恢复点可定位；
- 只激活批准 allowlist/cohort，未扩大发布、部署或风险接受权限；
- 激活后独立复算 report/receipt 与平台 conclusion 一致。

## 26. 待评审决策

以下事项不能由实施者或 LLM 默认：

1. Round 2 的试点模块、owners、trusted evidence store、policy source、Agent 适用性和数据治理；
2. P1c 第 24 节全部未决项及门槛拆分批准；
3. 首批 hard-rule allowlist 的精确 check ids/versions；
4. target repo、branches、cohort、required check name 和防同名冒充机制；
5. policy/approval 的 trust root、签名或平台 attestation 机制、撤销和 TTL；
6. infra/platform outage 是持续 BLOCK，还是允许外部 break-glass；谁可批准；
7. waiver 是否允许；若允许，角色、TTL、eligible/ineligible codes；
8. CANARY 的范围、自然窗口、样本、成功/停止和扩 cohort 条件；
9. evaluator/publisher 的 build、发布、保留和供应链证明；
10. publisher token 发行、权限、轮换和事故吊销；
11. kill-switch owner、RTO、通知路由、branch rollback owner；
12. limited-gate artifacts 的受控存储、保留周期、访问组和删除责任人；
13. ACTIVE 评估与发布的延迟预算和可用性 SLO；
14. policy/profile/schema 的 mixed-version 窗口与 contraction 条件；
15. PAUSED/ROLLED_BACK 后恢复所需角色和证据；
16. 独立复算人、审计频率和 escalation path。

在上述关键项未关闭前，不得实现真实 trust verifier、publisher 或 required check。

## 27. 结论与操作提示词

推荐的下一阶段设计是“冻结 admission + 固定 privileged safety core + 薄 CI adapter + 隔离
publisher”。它吸收 DeepSeek Harness 的可重建事实源、单调 guards、确定性提交和严格 seam
条件，但不复制其通用插件运行时，也不把质量安全核心开放给 patch/hook。

当前严格结论仍是 DESIGN_ONLY / NOT_ACTIVATABLE：P1c 尚未实现，R2-G0 尚未启动，没有真实
recommendation、三方 GO_LIMITED_GATE、批准 allowlist、trusted policy 或目标 CI 激活证据。
因此当前最小动作是完成 activation audit 和 contract owner 评审，不是修改 branch protection。

可直接用于后续执行的操作提示词：

> 请依据 docs/round-3-limited-gate-harness-spec.md 推进下一阶段。第一步只做 activation
> audit：确认 P1C_FIXTURE_VERIFIED、P1C_REAL_RECOMMENDATION_READY、外部三方
> GO_LIMITED_GATE attestation（必须精确引用重算的 recommendation decision digest）、
> Round 2 最终报告、hard-rule allowlist、可信 policy/attestation 来源、目标
> CI/branch-protection scope、kill-switch/rollback owner 与安全评审是否全部有版本化、可定位且
> 未过期的证据。任一缺失时，保持 DESIGN_ONLY/NOT_ACTIVATABLE，只允许 Spec 评审、脱敏
> fixture catalog 和只读 inventory；不得创建 required check、修改 branch protection、部署
> adapter 或读取真实业务证据。若 contract owners 在场，使用 $grilling 关闭仅能由当前用户决定的
> 事项；使用 $codebase-design 复核 caller-visible contract/seam；使用 $evolving-contracts 固定
> producer/reader/storage/deployment 矩阵和 Expand → Migrate → Observe → Contract 过渡。
> 只有契约与 fixture 实施许可获批后，才使用 $tdd 先写失败测试，实现
> limited-gate-index@1.0、limited-gate-policy@1.0、limited-gate-report@1.0、固定 monotonic
> guarded core 和薄 qualityctl ci evaluate CLI。只允许批准的结构完整性、Schema、冻结指纹、
> 证据/runner 完整性和确定性高风险失败进入 hard-rule allowlist；任何未知、篡改、过期、未签名、
> mixed identity 或 guard 异常均 fail-closed，后序步骤不得反转 STOP/BLOCKED/DENY；skills、
> LLM 文本、人工备注、ROI 和多数票不得成为状态或批准来源。所有 artifact exclusive-create，
> evaluator 保持无网络、无模型、无 MCP、无 publisher/branch/deploy 权限。完成 fixture 范围后，
> 运行全量 unittest、三个 smoke、Embedded UI smoke、git diff --check 和 Python 3.11
> exact-SHA CI，并使用 $review-code-against-spec 进行 Standards/Spec 两轴独立复核。只有真实
> activation evidence、shadow/canary 对照、0 wrong-PASS、权限审计、kill-switch/rollback 演练和
> 显式人类变更批准全部齐全后，才可另行执行批准 cohort 的 required-check 激活。
