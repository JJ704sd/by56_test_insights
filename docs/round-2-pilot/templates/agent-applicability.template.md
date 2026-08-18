# Agent 适用性记录（待批准模板）

本文件只能记录适用性决策，不能凭空生成 Agent 评测结果。若选择
`NOT_APPLICABLE`，最终报告只能声明“Agent 域不适用且有批准依据”，不得宣称已验证
Agent 收益。

| 字段 | 值 |
| --- | --- |
| `pilot_id` | `TBD` |
| 业务模块/能力 | `TBD` |
| 决策 | `TBD`（`APPLICABLE` / `NOT_APPLICABLE`） |
| 适用性来源系统/文档 | `TBD` |
| 来源版本/快照 | `TBD` |
| `policy_version` | `TBD` |
| 适用范围/排除范围 | `TBD` |
| 批准人及角色 | `TBD` |
| 批准时间 | `TBD` |
| 隔离 runner | `TBD`（适用时必填） |
| Agent/Prompt/模型/工具集版本 | `TBD`（适用时必填） |
| 知识库/数据集版本 | `TBD`（适用时必填） |
| `evaluation_fingerprint` 生成/登记引用 | `TBD`（适用时必填） |
| 人工语义 Oracle/裁决人 | `TBD` |
| `NOT_APPLICABLE` 原因 | `TBD`（不适用时必填） |
| 证据引用 | `TBD` |
| 失效/复审条件 | `TBD` |
| 下次复审时间 | `TBD` |

## 决策依据

`TBD`。必须说明该模块是否包含 Agent 行为、为什么需要或不需要冻结运行指纹、哪些
业务 Oracle 仍然必须由人工裁决，以及当模块边界、模型、Prompt、工具、知识库或数据集
发生变化时如何失效并重新审批。`NOT_APPLICABLE` 必须引用业务范围或架构事实，不能只写
“本轮未测试”。

## 安全约束

- 不使用 LLM Judge 独立裁决权限、计费、安全、数据写入或核心业务正确性。
- runner 无效、技术失败、确定性断言失败和语义失败分域记录；重试保留首次及全部尝试。
- 没有批准的适用性和阈值策略时，Agent 域只能为 `BLOCKED`/未启动，不得被写成 `PASS`。
- Agent 不适用时不得生成伪造的 runs、通过率或 ROI；最终报告只能写“已批准的不适用”，
  并明确 Agent 收益未验证。
