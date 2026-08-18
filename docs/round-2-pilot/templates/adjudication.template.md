# Difference Adjudication（差异裁决模板）

变更：`TBD`<br>
人工范围引用：`TBD`<br>
工具结果引用：`TBD`<br>
初判截止时间（默认 2 个工作日）：`TBD`<br>
高风险差异关闭截止：`TBD`

## 差异记录

| difference_id | 位置/测试 ID | 人工结论 | 工具结论 | 分类 | 风险级别 | 业务证据引用 | 裁决人 | 裁决时间 | 状态 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `TBD` | `TBD` | `TBD` | `TBD` | `TBD` | `TBD` | `TBD` | `TBD` | `TBD` | `TBD` |

每个差异还必须能从下列引用定位原始内容；表格中的摘要不能替代 raw 文件：

| 字段 | 值 |
| --- | --- |
| 原始人工范围/结论引用 | `TBD` |
| 原始工具请求引用 | `TBD` |
| 原始工具输出引用 | `TBD` |
| 首次观察时间 | `TBD` |
| 正式测试/发布路径影响 | `TBD`（影子结果不得自动改变） |
| 修订后的 catalog/mapping 版本（如有） | `TBD` |
| 关闭证明/复核引用 | `TBD` |

允许的分类（只能使用 Spec §7.2）：

`TOOL_TRUE_POSITIVE`、`TOOL_FALSE_POSITIVE`、`TOOL_FALSE_NEGATIVE_HIGH`、
`TOOL_FALSE_NEGATIVE_OTHER`、`HUMAN_BASELINE_ERROR`、`CATALOG_OR_MAPPING_DEFECT`、
`POLICY_AMBIGUITY`、`RUNNER_OR_ENVIRONMENT`、`NO_DIFFERENCE`。

## 安全检查

| 检查项 | 结果 | 证据 |
| --- | --- | --- |
| 错误 `PASS` | `TBD`（必须为 0） | `TBD` |
| 确认的高风险漏选 | `TBD`（必须为 0） | `TBD` |
| 未经授权自动放行 | `TBD`（必须为 0） | `TBD` |
| 敏感数据事件 | `TBD`（必须为 0） | `TBD` |
| 首次及全部重试均保留 | `TBD`（必须为 100%） | `TBD` |

## 裁决规则

- 人工范围未冻结、工具输出被改写、证据缺失或责任人不明确时，差异不计为已关闭。
- `TOOL_FALSE_NEGATIVE_HIGH`、错误 `PASS` 或敏感数据事件不得被 ROI 抵消；按停止流程处理。
- 裁决可以更新后续 catalog/mapping 版本，但不能修改原始输入或原始输出；修订必须新建
  版本并保留前后引用。
- 即使人工与工具没有差异，也要记录 `NO_DIFFERENCE`、分母资格和原始证据引用；不能省略
  记录来制造较高的差异解决率。
- 高风险差异在下一次发布前必须关闭或由授权责任人明确阻塞；普通差异按批准 SLA 分类。
