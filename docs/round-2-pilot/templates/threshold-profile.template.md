# Threshold Profile（待批准模板）

当前没有阈值结果。所有数值、容差、样本数和 hard-fail 规则必须来自可审计来源，且在
R2-G0 前冻结；Spec 的推荐值不是本项目的批准值。

| 字段 | 值 |
| --- | --- |
| `profile_version` | `TBD` |
| `source_ref` | `TBD` |
| `approval_status` | `TBD`（`APPROVED` / `UNAPPROVED`） |
| 批准人 | `TBD` |
| 批准时间 | `TBD` |
| 适用 Agent/case | `TBD` |
| `evaluation_fingerprint` | `TBD` |
| 高风险 `planned_runs` | `TBD` |
| 高风险 `min_pass_rate` | `TBD` |
| 高风险 `hard_fail_on_any` | `TBD`；不得通过平均值关闭 |
| 中风险样本/复核要求 | `TBD` |
| 低风险样本/复核要求 | `TBD` |
| 确定性断言失败处理 | `TBD` |
| `runner_invalid`/`technical_failure` 处理 | `TBD`；不能当作业务通过 |
| 语义复核缺失处理 | `TBD` |
| 数值绝对/相对容差 | `TBD`；每条断言只能选择一种口径 |
| 重试、首次失败和额外运行口径 | `TBD`；不得覆盖原始尝试或事后扩样 |
| 不适用/策略未批准状态 | `TBD`；至少保持 `BLOCKED` 或 `REVIEW_REQUIRED` |
| 失效/回滚版本 | `TBD` |
| 证据引用 | `TBD` |

## 冻结检查

- [ ] Agent、Prompt、模型参数、工具集、知识快照、数据集和 runner 指纹已绑定。
- [ ] 所有 runs 使用同一个 `evaluation_fingerprint`。
- [ ] 未批准、混用指纹、样本不足、runner 无效和首次失败的处理口径已写明。
- [ ] 原始阈值文件不可被运行结果覆盖。
- [ ] 高风险 case 的首次有效失败仍然是失败，不能用重试或平均值改写。
- [ ] 每个 case 的 `planned_runs`、断言和人工复核要求均能回指批准来源。
