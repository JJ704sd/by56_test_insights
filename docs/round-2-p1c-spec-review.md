# Round 2 P1c Spec 评审记录

| 项目 | 结果 |
| --- | --- |
| 评审日期 | 2026-08-19 |
| 评审对象 | `round-2-p1c-stage-recommendation-harness-spec.md` v0.2 Draft |
| 仓库修订 | `a603f2e501601a3e9ae1494920983de318f1db3a` + 当前未提交工作区文档增量 |
| 评审结论 | `REVIEWED_WITH_BLOCKERS` |
| 激活门槛拆分 | `NOT_APPROVED` |
| 当前实施边界 | 只允许 PRE 修复、评审和 fixture catalog；stage core/CLI 禁止开始 |

本记录是工程评审，不是业务批准、Gate 结果、阶段决定或发布授权。它没有启动或重置
8 周时钟，也没有读取、复制或生成真实业务证据。

## 1. 激活门槛批准审计

| 来源 | 当前可定位事实 | 判定 |
| --- | --- | --- |
| P1b §20 | `P1B_REAL_SUMMARY_READY` 才允许进入 P1c 的 G1–G3 阶段建议设计/实现 | 更严格门槛仍有效 |
| P1b §21 | P1c 范围仍是待评审决策；没有批准人、批准时间、批准载体或有效期 | 未批准 |
| P1c 文档头和 §2.3 | 文档状态为 Draft，并明确要求拆分与 P1b 同步评审，批准前按更严格门槛执行 | 未批准 |
| `docs/round-2-pilot/decisions-to-approve.md` | 没有 P1c 门槛拆分的完成记录；现有真实启动决策仍为 `MISSING` | 未批准 |
| Git 历史与当前工作区 | 没有将拆分标为 `APPROVED` 的提交、签署记录或版本化 attestation | 未批准 |

结论：Spec §2.3 提议的“`P1B_FIXTURE_VERIFIED` 后允许脱敏 stage fixture 实现”尚未
与 P1b 同步获批。当前有效门槛保持 `BLOCKED_BY_P1B_REAL_SUMMARY`，因此本轮没有新增
`src/qualityctl/stage.py`、stage Schema、`decide_round2(...)` 或 `decide-round2` CLI。

## 2. P1b Definition of Done 审计

| DoD 项 | 当前证据 | 状态 |
| --- | --- | --- |
| strict report/ledger/index/summary parity | P1b parity 测试；外部 raw ref 新增 Pydantic/JSON Schema 正反 parity | `PASS_LOCAL` |
| identity/draft/attestation/exact matrix | `tests.test_iteration.P1B001To004IntegrityTests` | `PASS_LOCAL` |
| `summarize_iteration` 与薄 CLI | 聚焦测试、CLI exclusive-create 测试和 P1 evidence smoke | `PASS_LOCAL` |
| metric state、ROI、STOP 优先 | P1b aggregation 测试 | `PASS_LOCAL` |
| safe path/digest/duplicate/mixed identity | iteration resolver 测试；四类 raw ref 的 path/symlink/size/media/digest 测试；scope duplicate guard | `PASS_LOCAL` |
| stable decision digest、raw 不变 | digest 和 immutability 回归 | `PASS_LOCAL` |
| test/dev dependency 可复现 | `pyproject.toml` 的 `test` extra 固定 `jsonschema==4.26.0`；CI 安装 `.[test]` | `PASS_CONFIG` |
| 五个 MCP 与旧 CLI 不变 | MCP 注册回归与 smoke | `PASS_LOCAL` |
| Python 3.11 必验环境 | workflow 固定 Python 3.11；当前机器只有 3.14.6，本未提交增量尚无 CI 运行 | `PENDING_CI` |
| 真实治理状态不被 fixture 改写 | `R2-G0=REMAIN_BLOCKED`；真实 summary 未生成 | `PASS` |

严格状态：`P1B_FIXTURE_VERIFIED = PENDING_PY311_CI`。本地 fixture 验证完成不替代
Python 3.11 CI，也不等于 `P1B_REAL_SUMMARY_READY`。

## 3. Contract transition checkpoint

当前与目标兼容矩阵固定为：

| Producer / reader / storage / deployment | 当前 | 本轮允许目标 | 证据与恢复 |
| --- | --- | --- | --- |
| manifest/catalog/agent_spec inline producer | v1 inline object | 继续可读；也可用完整 artifact ref | 正反 resolver/parity 测试；回退为 inline fixture |
| agent_runs producer | v1 inline rows；旧外部 ref 分支不安全 | inline 或完整 artifact ref 共用 resolver | junction/path/size/digest 测试；回退为 inline fixture |
| Pilot Evidence reader | strict `1.0` + P1b hardening | duplicate scope fail-closed | 旧唯一-ID fixture保持不变 |
| difference draft writer/reader | `DRAFT` | additive `BLOCKED/DUPLICATE_SCOPE_ID` | 不改写既有 artifact；停止新 writer 即可回退 |
| iteration reader/writer | strict `1.0` | 保持 | P1b replay fixtures |
| stage producer/reader | 不存在 | 仍不存在 | 无迁移、无持久副作用 |
| evidence storage | 临时目录脱敏 fixture | 仍为临时目录、exclusive-create 输出 | 删除临时目录；无真实 store |
| deployment | Python 3.11 CI + 本地 3.14 | 配置安装 test extra；等待 3.11 CI | revert CI 安装行；运行时依赖未增加 |

Transition phase：

1. **Expand**：PRE reader hardening 已完成；stage reader 尚未获准创建。
2. **Migrate**：未开始；没有 stage writer 或真实记录。
3. **Observe**：PRE focused/local regression 已完成；Python 3.11 CI 待观察。
4. **Contract**：未开始；只有批准门槛拆分、兼容矩阵签署、全回归和 CI 证据齐全后才可讨论。

安全恢复点是当前 P1b 公共 API：停止使用外部 raw refs，继续使用 inline 脱敏 fixture；已存在
artifact 不改写。没有 dual-write、破坏性迁移或需要回滚的真实数据。

## 4. P1c Spec 阻塞项与技术收口

| ID | 状态 | 阻塞项/收口结果 | 进入 stage 实现前所需关闭证据 |
| --- | --- | --- | --- |
| `P1C-REV-001` | `OPEN` | §2.3 门槛拆分未获批准 | P1b/P1c 同版本决策、批准角色、时间、载体和有效期 |
| `P1C-REV-002` | `OPEN` | stage 契约仍为 Draft，§24 有未决语义 | contract owner 对全部待决项的版本化评审结论 |
| `P1C-REV-003` | `SPEC_RESOLVED` | v0.2 §8.3 删除 `freeze.digest` 后计算语义投影，禁止把文件 bytes digest 回填到同一 artifact | 独立实现该向量并由 Schema/Pydantic/core 测试复核 |
| `P1C-REV-004` | `SPEC_RESOLVED` | v0.2 §8.2/§10.3 分离 summary artifact bytes digest、窗口冻结 decision digest 和重算 decision digest | 三方一致/逐层不一致 fixture 全部通过 |
| `P1C-REV-005` | `SPEC_RESOLVED` | v0.2 §7 冻结有序 canonical material 与独立 SHA-256 向量 | Python core 与独立测试路径输出同一 bytes/digest |
| `P1C-REV-006` | `OPEN` | 当前 revision 已有 Python 3.11 CI run，但 workflow 使用 editable install；Round 3 要求的 pinned exact-SHA provenance 仍缺失 | CI 运行链接/日志、精确 revision 以及 pinned artifact/hash 证据 |

`SPEC_RESOLVED` 只表示文字合同不再歧义，不等于实现、contract owner 批准或 DoD。三个
技术项仍需测试证据；三个 `OPEN` 项关闭前，fixture catalog 只是测试设计清单，不能被解释为
contract freeze 或 `P1C-001` 完成，更不能成为真实 Gate、阶段批准或发布授权。

## 5. 2026-08-19 执行复核快照

本次复核固定为 `HEAD=a603f2e501601a3e9ae1494920983de318f1db3a` 加当前未提交工作区；未执行
reset、checkout、清理、提交或推送。当前工作区没有 `stage.py`、stage Schema、`test_stage.py`
或 `decide-round2` 实现，也没有生成 stage fixture JSON。

| 证据 | 结果 | 边界解释 |
| --- | --- | --- |
| Python 版本 | `3.14.6` | 本地环境，不替代 Python 3.11 必验环境 |
| `python -m unittest discover -s tests -v` | `153/153`，exit `0` | P1b/PRE 脱敏与仓库回归通过；不是业务证据 |
| `smoke_test.py` | exit `0`，仍为五个 MCP 工具 | 没有新增 MCP 工具 |
| `p1_evidence_smoke.py` | exit `0`，`formal_release_effect=NONE` | 仅 synthetic-p1 fixture |
| Embedded UI smoke | exit `0` | 未扩展 UI 或批准入口 |
| `git diff --check` | exit `0` | 仅格式/空白检查 |
| GitHub Actions `python-qualityctl` | [run 32118256664](https://github.com/JJ704sd/by56_test_insights/actions/runs/32118256664) 为此前记录的成功运行 | workflow 使用 Python 3.11；该 run 不能作为当前精确 revision 或工作区的 CI 证据 |

因此 `P1C-REV-006` 仍为 `OPEN`：当前 `a603f2e`/工作区没有 Python 3.11 CI 证据。严格门禁仍为
`P1B_FIXTURE_VERIFIED=PENDING_PY311_CI`，不是 `P1B_FIXTURE_VERIFIED`，更不是
`P1B_REAL_SUMMARY_READY`。R2-G0 审计仍为 `REMAIN_BLOCKED`、`0/9 READY`，没有真实 Day 0、
受控真实证据、已批准 policy 或双人真实 summary 复算；八周时钟保持未启动。

仓库中没有 contract owner 在场或 §24 版本化批准的可定位证据，故 `P1C-REV-002` 继续 `OPEN`，
§24 不由实施者代答。`P1C-REV-001` 也继续 `OPEN`：P1b §21 的 `PENDING_APPROVAL` 与
P1c §2.3 的 `NOT_APPROVED` 未发生同步批准。依据 P1c §2.3/§17，本轮到此停止；只保留 PRE、
Spec 评审、fixture catalog 和阻塞记录范围，不进入 `P1C-001`–`P1C-009` 的 stage artifact
实现。

## 6. PRE 最小修复复核

以下复核全部只使用脱敏 fixture；它们不是业务证据，也不改变 §2.3 门槛或 §24 的责任人决策：

| 缺口 | 修复与独立证据 | 状态 |
| --- | --- | --- |
| exact core identity 可缺失 | `EvidenceVersionsV1`/Pilot Schema 要求 `core_version` 与 `core_commit`；缺失 commit 的 Pydantic、Schema 和 verifier 负例为 `BLOCKED/INVALID_BUNDLE` | `PASS_LOCAL` |
| iteration artifact media type 未执行 | `_resolve_json_ref` 仅接受 `application/json`；`text/plain` ledger fixture 为 `BLOCKED/UNSUPPORTED_MEDIA_TYPE` | `PASS_LOCAL` |
| 运行时钟改变决策 | 窗口有效性以已冻结 `freeze.frozen_at` 判断；不同 `now` 只改变 `generated_at`，重算结果与 `decision_digest` 一致 | `PASS_LOCAL` |
| fixture business boundary 可被伪造 | `IterationSummaryV1` 与 `iteration-summary` Schema 对 `evidence_class/status/business_evidence` 加交叉约束；伪造 fixture 为校验失败 | `PASS_LOCAL` |
| test/dev dependency 可复现 | `jsonschema` 从范围约束收紧为当前已验证的 `4.26.0` | `PASS_CONFIG` |

当前实现只支持已存在的 exact version/commit fixture 路径；“commit、artifact digest 或二者”的最终选择
仍是 P1b §21/本 Spec §24 的责任人事项，未被本地修复记录为批准。上述 `PASS_LOCAL` 也不替代
Python 3.11 当前工作区 CI、`P1C-REV-001/002/006` 或 `P1B_REAL_SUMMARY_READY`。

## 7. 修复后状态快照

本轮仍固定为 `HEAD=a603f2e501601a3e9ae1494920983de318f1db3a` 加当前未提交工作区；未创建
stage Schema/core/CLI，也未读取或生成真实业务证据。focused evidence/iteration 测试分别为
`31/31`、`22/22`，全量为 `153/153`；smoke 与 `git diff --check` 均为 exit `0`。
`P1C-REV-001`（门槛同步批准）、
`P1C-REV-002`（contract owner/§24）和 `P1C-REV-006`（当前工作区 Python 3.11 CI）继续 `OPEN`。

## 8. 2026-08-19 当前 revision CI 状态增补

本节为对 §5 和 §7 历史快照的追加记录，不改写当时的执行上下文，也不把 CI 成功误解释为
P1c 或真实业务准备就绪。

| 证据 | 当前结果 | 边界解释 |
| --- | --- | --- |
| 当前 revision | `d2401bab0bf18eec3e7d7abb40a7b7915e6932fb`，已推送至 `codex/record-desktop-inline-proof` | 仅证明该提交已进入远端分支 |
| Python 3.11 GitHub Actions | [run 32227894301](https://github.com/JJ704sd/by56_test_insights/actions/runs/32227894301)，`success` | head SHA 与当前 revision 精确匹配；运行了 unit tests 与 MCP smoke |
| 安装/构建 provenance | `python -m pip install -e .[test]` | 不是 pinned wheel/hash 的 exact-SHA 构建证据；该缺口仍 `OPEN` |

因此，旧快照中“当前 revision 尚无 Python 3.11 CI 结果”的子事实已由本次 run 补充更新；但
`P1C-REV-006` 所需的可用于 Round 3 activation audit 的 pinned exact-SHA provenance 仍未关闭，
不应据此改写为 `P1C_FIXTURE_VERIFIED`、`P1C_REAL_RECOMMENDATION_READY` 或任何 `GO_LIMITED_GATE`。
`P1C-REV-001`、`P1C-REV-002`、R2-G0 `REMAIN_BLOCKED`、真实 evidence 缺失以及 stage core/CLI
未实现均保持原状态；本增补不创建 required check、publisher 或任何发布/分支保护副作用。
