# Round 2 P1c 脱敏 Fixture Catalog

状态：`CATALOG_ONLY / NO_STAGE_ARTIFACTS_GENERATED / NOT_BUSINESS_EVIDENCE`

本 catalog 只登记未来获批后可实现的脱敏测试场景。所有 identity 必须使用 `fixture-` 前缀，
所有 refs 使用 `fixture://` 或测试临时目录，时间为明确的合成时间，内容不得来自真实模块、
真实人员、真实运行、真实审批或受控业务存储。catalog 条目不是 `stage-index@1.0`、阶段建议、
Gate、批准或发布授权，也不启动或重置 8 周时钟。

## 1. PRE resolver 与 scope fixtures（已实现）

| Fixture ID | 输入/变异 | 预期 |
| --- | --- | --- |
| `P1C-PRE-FX-001` | manifest/catalog/agent_spec JSON + agent_runs JSONL，全部为 base-dir 内完整 ref | change report `ELIGIBLE`，仅 fixture |
| `P1C-PRE-FX-002` | 四类 ref 逐一使用绝对路径 | `BLOCKED`，读前拒绝 |
| `P1C-PRE-FX-003` | 四类 ref 逐一包含 `..` | `BLOCKED`，读前拒绝 |
| `P1C-PRE-FX-004` | agent_runs 通过 symlink/junction 指向 base-dir 外 | `BLOCKED`，读前拒绝 |
| `P1C-PRE-FX-005` | 四类 ref 的登记 size 与 stat 不同 | `BLOCKED`，不解析内容 |
| `P1C-PRE-FX-006` | 四类 ref 的 SHA-256 与 bytes 不同 | `BLOCKED`，不把内容交给规则核心 |
| `P1C-PRE-FX-007` | JSON/JSONL media type 错配 | `BLOCKED` |
| `P1C-PRE-FX-008` | manual scope 重复 test ID | `BLOCKED/DUPLICATE_SCOPE_ID` |
| `P1C-PRE-FX-009` | tool scope 重复 test ID | `BLOCKED/DUPLICATE_SCOPE_ID` |
| `P1C-PRE-FX-010` | 完整/缺字段 external ref 的 Pydantic 与 JSON Schema 比较 | positive/negative parity |

## 2. Stage contract fixtures（仅登记，未实现）

以下条目只有在 §2.3 门槛拆分获批后才能生成实际 JSON：

| Fixture ID | 覆盖工作包/AC | 合成场景 | 固定预期 |
| --- | --- | --- | --- |
| `P1C-FX-001` | `001/002`, AC-033 | strict positive stage index/policy/recommendation | 三个 Schema/Pydantic 同时接受；仍为 fixture-only |
| `P1C-FX-002` | `002`, AC-030/033 | unknown/extra/missing/unsupported version | 同时拒绝，stable contract code |
| `P1C-FX-003` | `003`, AC-003/004/032 | 只有 summary，或 bytes/window/replay decision digest 任一不同 | `BLOCKED/RAW_REFERENCE_MISSING` 或对应稳定 mismatch code |
| `P1C-FX-004` | `003`, AC-007 | stage ref 的 absolute/parent/symlink/size/media/digest 变异 | 全部 fail-closed |
| `P1C-FX-005` | `004`, AC-005/006 | mixed pilot/evidence class、跨 iteration 重复 eligible | `BLOCKED`，分母不重复 |
| `P1C-FX-006` | `004`, chronology family | cutoff 早于 Day 0、window 晚于 cutoff、iteration 重叠 | 对应 stable chronology code |
| `P1C-FX-007` | `005`, AC-008/009 | 每项安全 STOP 与正 ROI/approval complete 同时出现 | 最终保持 `STOP` |
| `P1C-FX-008` | `005`, check execution | 私有 check throw/非法 shape/未知 profile | `BLOCKED/CHECK_EXECUTION_ERROR` 或 `UNSUPPORTED_CHECK_PROFILE` |
| `P1C-FX-009` | `006`, AC-010/011 | Day 14 前；到期但候选/eligible 不足 | `PENDING_NOT_DUE`；`EXTEND_G1` |
| `P1C-FX-010` | `006`, AC-012 | 合成 G1 全满足 | preview `R2-G1_HEALTHY`；非真实 Gate |
| `P1C-FX-011` | `006`, AC-013/014 | 无完整 iteration；首迭代需重复 | `PENDING_ITERATION`；`REPEAT_ITERATION` |
| `P1C-FX-012` | `006`, AC-015 | 合成首完整迭代全满足 | preview `R2-G2_ITERATION_VALIDATED` |
| `P1C-FX-013` | `006`, AC-016/017 | G3 时间/迭代/eligible/ROI 任一不足 | `CONTINUE_OBSERVATION` 或 `ADJUST_AND_REPEAT` |
| `P1C-FX-014` | `006/007`, AC-018 | 合成 G3 全满足 | preview `GO_LIMITED_GATE`，但三项 formal 字段固定 false/NONE |
| `P1C-FX-015` | `007`, AC-024/025 | 只改变 generated_at；再改变 cutoff | 前者 digest 不变，后者 digest 改变 |
| `P1C-FX-016` | `007`, approval readiness | 角色缺失/重复/过期/完整 | readiness 变化不产生批准 |
| `P1C-FX-017` | `008`, AC-026 | CLI 首次写入与目标已存在 | exclusive-create；冲突原 bytes 不变 |
| `P1C-FX-018` | `009`, compatibility | initial/mixed/final/unsupported rollback | 混合态 fail-closed，旧 P1b reader 保持 |
| `P1C-FX-019` | activation | REAL + G0 非 READY/P1b real-ready 缺失 | `BLOCKED`，不启动时钟 |
| `P1C-FX-020` | authority boundary | skill 文本声称批准但无 attestation | 忽略声称，保持 incomplete/blocked |
| `P1C-FX-021` | `001/003`, AC-031, NFR-015 | 修改 freeze 投影任一字段或提交错误 profile vector | 对应 stable digest/profile code；不得继续执行 Gate |

## 3. 每个未来 fixture 的强制元数据

每个实际 fixture 必须同时包含：

- `fixture_id`、覆盖 ticket/AC/NFR、synthetic seed 和创建脚本版本；
- `identity.evidence_class=FIXTURE`、`business_evidence=false`、
  `outcome_scope=FIXTURE_ONLY`；
- `formal_stage_decision_made=false`、`formal_release_effect=NONE`、
  `formal_release_allowed=false`；
- 所有输入 artifact 的相对 ref、bytes size、media type 和 SHA-256；
- 独立预期向量，不能从 production implementation 复制算法生成；
- freeze/profile canonical bytes 与 P1c Spec §7/§8.3 的独立 SHA-256 向量；
- 禁止项确认：无真实业务证据、无真实 owner/批准、无 Harness 进程、无 Agent runner、
  无网络/remote adapter/MCP 新工具、无 required check、无发布或回滚权限。

实际 stage fixture 目录目前故意不存在。批准后也必须使用 exclusive-create 生成新文件；修正
使用新 fixture ID/digest，不覆盖旧 bytes。
