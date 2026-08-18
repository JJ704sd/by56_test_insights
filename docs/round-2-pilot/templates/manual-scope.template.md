# Manual Scope（单个变更人工基线冻结模板）

变更：`TBD`<br>
迭代：`TBD`<br>
人工范围负责人：`TBD`<br>
人工范围版本：`TBD`<br>
冻结时间（必须早于工具结果展示/运行）：`TBD`<br>
人工证据引用：`TBD`

| 冻结包字段 | 当前值 |
| --- | --- |
| `change_ref`（提交/构建） | `TBD` |
| `catalog_version`（工具运行前已知） | `TBD` |
| `mapping_version` | `TBD` |
| 人工范围摘要/文件校验 | `TBD` |
| 冻结记录校验/追加位置 | `TBD` |
| 工具结果展示前状态 | `NOT_SHOWN`；冻结后才允许改为已展示 |
| 是否进入主分母 | `TBD`；冻结证据缺失时必须为 `NO` |

## 1. 解盲顺序硬检查

- [ ] `change_id`、变更提交/构建引用和版本类型已记录。
- [ ] 人工风险范围、人工回归范围和预计耗时已完整填写。
- [ ] 测试负责人确认人工范围已经冻结。
- [ ] 冻结记录已写入受控存储，且冻结后未被覆盖。
- [ ] 上述完成后才展示或运行 `qualityctl` 结果。
- [ ] 原始人工范围、时间戳和摘要已生成不可变引用；后续修订必须新建版本。
- [ ] 未运行的工具不得先写入工具结论；工具结果展示时间单独记录。

若任何一项未勾选：本变更不得进入主分母；工具可以在隔离演练中运行，但结果必须单独
标为 `EXCLUDED_PRE_FREEZE`。

## 2. 人工八维风险范围

| 风险维度 | 人工状态 | 证据/场景引用 | 人工 owner | 预计复核分钟 |
| --- | --- | --- | --- | --- |
| `business_flow` | `TBD` | `TBD` | `TBD` | `TBD` |
| `exception_paths` | `TBD` | `TBD` | `TBD` | `TBD` |
| `boundaries` | `TBD` | `TBD` | `TBD` | `TBD` |
| `permissions` | `TBD` | `TBD` | `TBD` | `TBD` |
| `data_consistency` | `TBD` | `TBD` | `TBD` | `TBD` |
| `upstream_downstream` | `TBD` | `TBD` | `TBD` | `TBD` |
| `side_effects` | `TBD` | `TBD` | `TBD` | `TBD` |
| `recoverability` | `TBD` | `TBD` | `TBD` | `TBD` |

## 3. 人工回归范围

| test_id | suite/优先级 | 纳入/排除 | 原因 | 预计分钟 | 证据引用 |
| --- | --- | --- | --- | --- | --- |
| `TBD` | `TBD` | `TBD` | `TBD` | `TBD` | `TBD` |

人工基线总分钟：`TBD`<br>
人工结论：`TBD`（不得填写工具结论）<br>
工具结果展示时间：`TBD`<br>
最终执行/发布结果：`TBD`（沿用正式流程）

## 4. 变更后修订

如果人工范围在冻结后确需修订，必须说明原因、批准人、时间和新版本引用；原始冻结包
继续保留，且该变更默认从主分母排除，直到测试负责人重新确认资格。不得通过改写原文件
来消除人工与工具差异。
