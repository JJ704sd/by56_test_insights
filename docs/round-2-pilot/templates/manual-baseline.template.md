# Manual Baseline 登记说明（P0）

对应 CSV：[`manual-baseline.template.csv`](manual-baseline.template.csv)。该 CSV 只有表头，
不包含历史或业务数据。`source_kind` 只能区分真实历史记录、前瞻采集或非分母演练，不能
用仓库测试、examples 或估算值填充真实基线。

## 资格规则

- `manual_scope_frozen_at` 必须早于任何工具结果展示或运行时间；
- `tool_result_visible_before_freeze` 必须为 `NO`，否则 `baseline_eligible=NO`；
- 每行绑定唯一 `iteration_id`、`change_id`、人工范围引用、变更/构建引用和复核人；
- 缺少可信来源、冻结记录、脱敏检查或实际耗时的记录只能留在排除清单；
- 历史记录必须满足时间可信、字段完整、人工范围未受工具污染且可复核，否则改为前瞻
  采集；
- 不能把准备期/基线采集期计入 8 周影子时钟，也不能复制、拆分或补造变更。

## 最小采集顺序

1. 先写入人工风险范围、人工回归范围和预估/实际耗时；
2. 测试负责人冻结 `manual-scope`，记录时间和摘要；
3. 仅在冻结后运行或展示 qualityctl 结果；
4. 回填正式执行结果、差异裁决和维护/复核成本；
5. 由复核人确认资格，排除项保留原因和证据引用。

总分钟必须等于各人工成本列的可复算合计；没有真实数据时保持空行，不填写 `0`。
