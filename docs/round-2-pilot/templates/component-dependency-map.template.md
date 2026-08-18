# Component / Upstream / Downstream Mapping（P0）

对应 CSV：[`component-dependency-map.template.csv`](component-dependency-map.template.csv)。当前
只有表头和 `TBD` 占位行，不代表任何真实模块、依赖或历史逃逸已经评审。

## 填写规则

- 每行绑定一个 `map_version`、`scope_ref` 和稳定 `component_id`；同一组件的多个上下游
  关系用同一版本的独立记录表达，不覆盖旧版本；
- `upstream_component` 和 `downstream_component` 必须来自批准的架构/依赖来源；未知关系
  不能默认为“无依赖”；
- `historical_escape_ref` 只能引用可复核的历史缺陷/逃逸记录；没有证据时保持 `TBD`，
  不用示例或推测补齐；
- `risk_dimensions` 必须能与八维 manifest 关联，至少由测试负责人和研发负责人复核；
- `owner`、`reviewer`、`source_ref`、`recorded_at` 在 R2-G0 前必须可定位；
- `review_status` 只有在证据、复核人和时间都齐全时才能从 `PENDING_REVIEW` 改为批准状态。

## 与质量工具的边界

映射用于生成真实变更的 `changed_components`、`dependencies.upstream/downstream` 和
目录关联；它不改变 `qualityctl` 的规则核心。映射缺失或与变更冲突时，保留原始输入并
将该变更标为证据不足/差异待裁决，不把空映射当作低风险。
