# Round 2 最终报告（模板）

试点：`TBD`<br>
`pilot_id`：`TBD`<br>
模块：`TBD`<br>
观测期：`TBD` – `TBD`<br>
报告版本：`TBD`<br>
状态：`DRAFT`；没有完整证据前不得填写阶段决策。

本报告只汇总受控原始证据和版本化裁决；仓库模板、examples、单元测试、MCP smoke 或
静态 HTML 预览不能作为真实业务样本。Round 2 默认使用静态 HTML/结构化 MCP 输出，
不新增 Embedded UI、审批、发布或写回能力。

## 1. 执行摘要

只能填写来自受控原始证据的事实。不得把模板、examples、仓库测试数量或推测收益写成
业务试点结果。

## 2. R2-G0 状态矩阵

| 条件 | 状态 | 证据引用 | 批准人/时间 |
| --- | --- | --- | --- |
| Charter、范围、owner、升级 | `TBD` | `TBD` | `TBD` |
| 30–50 条 catalog + Schema | `TBD` | `TBD` | `TBD` |
| 八维风险与组件/依赖映射 | `TBD` | `TBD` | `TBD` |
| Agent 适用性、阈值、ROI policy | `TBD` | `TBD` | `TBD` |
| 两个迭代人工基线 | `TBD` | `TBD` | `TBD` |
| 人工耗时采集演练 | `TBD` | `TBD` | `TBD` |
| 非阻塞运行演练 | `TBD` | `TBD` | `TBD` |
| 受控存储/访问/脱敏/保留 | `TBD` | `TBD` | `TBD` |
| 回退/紧急停止责任人 | `TBD` | `TBD` | `TBD` |

## 3. 观测范围与分母

- 8 周是否完整：`TBD`
- 完整迭代数：`TBD`
- 合格变更数：`TBD`
- 排除项及原因：`TBD`
- Agent 是否适用：`TBD`

## 4. 安全红线结果

| 硬门槛 | 结果 | 证据引用 |
| --- | --- | --- |
| 错误 `PASS` = 0 | `TBD` | `TBD` |
| 确认的高风险漏选 = 0 | `TBD` | `TBD` |
| 未经授权自动放行 = 0 | `TBD` | `TBD` |
| 敏感数据事件 = 0 | `TBD` | `TBD` |
| 失败域可归因率 = 100% | `TBD` | `TBD` |
| 重试证据保留率 = 100% | `TBD` | `TBD` |

任何一个安全红线不满足，阶段决策必须为 `STOP`，不能用效率或 ROI 抵消。

## 5. 效率、质量和 ROI

填写每项的公式、原始输入、版本、分母和复算位置；没有真实数据写 `TBD`，不要补零。

## 6. 已创建/修改的文件与运行版本

`TBD`。说明模板、目录、映射、策略、CLI/MCP 版本以及任何代码变更；列出哈希和受控
证据引用，不把仓库模板当作业务证据。

## 7. 验证命令及结果

| 命令 | 环境/版本 | 结果 | 证据引用 |
| --- | --- | --- | --- |
| `python -m unittest discover -s tests -v` | `TBD` | `TBD` | `TBD` |
| `python plugins/quality-gatekeeper/scripts/smoke_test.py` | `TBD` | `TBD` | `TBD` |
| Schema/目录校验命令 | `TBD` | `TBD` | `TBD` |
| `git diff --check` 或等价格式检查 | `TBD` | `TBD` | `TBD` |

## 8. 尚缺业务输入与审批

链接 [`decisions-to-approve.md`](../decisions-to-approve.md) 并逐项列出未完成 owner、
来源、批准时间和下一步。

## 8.1 证据完整性与不可覆盖检查

| 检查项 | 结果 | 证据引用 |
| --- | --- | --- |
| 原始输入保留 | `TBD` | `TBD` |
| 首次输出保留 | `TBD` | `TBD` |
| 所有重跑独立保存 | `TBD` | `TBD` |
| 差异与裁决未覆盖 raw | `TBD` | `TBD` |
| Secret/敏感数据扫描 | `TBD` | `TBD` |
| 影子任务未成为 required check | `TBD` | `TBD` |

## 9. 阶段决策

唯一允许值：`GO_LIMITED_GATE` / `ADJUST_AND_REPEAT` / `STOP`。当前模板值必须保持 `TBD`。

## 10. 是否可以启动 8 周影子时钟

`TBD`。只有 R2-G0 全部 `READY` 且签署完成时才可填写 `YES`；否则填写 `NO` 并说明
阻塞项。

## 11. 下一项最小可执行动作

`TBD`。必须指定一个 owner、一个动作、一个截止时间和一个可验证输出；当前最小动作
只能是补齐一项业务输入/审批或完成一次非分母演练，不得直接启动 8 周时钟。
