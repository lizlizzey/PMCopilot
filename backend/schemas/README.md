# Backend Unified Schemas (`v1`)

该目录提供统一 schema 定义：

- `OKRMaster`
- `Module`
- `KeyResult`
- `ActionCard`
- `MetricSeries`
- `RetroReport`

## 版本策略

所有模型统一包含：

- `schema_version: "v1"`

向后兼容策略：

1. **新增字段默认值**：`from_payload` 会对 `status`、`target_condition`、`unit`、`time_granularity`、数值字段等自动补默认值。
2. **废弃字段迁移映射**：
   - `okrId -> okr_id`
   - `moduleId -> module_id`
   - `krId -> kr_id`
   - `actionId -> action_id`
   - `progress -> current_value`
3. **版本门禁**：当前仅接受 `v1`，其它版本直接报错，避免静默数据错配。

## 字段约束

### 数值单位

- `unit`: `percentage | amount`
  - `percentage` 代表百分比数值（例如 `18` 表示 `18%`）
  - `amount` 代表金额/货币类绝对值

### 时间粒度

- `time_granularity`: `day | week | month`

### 枚举值

- `status`: `not_started | in_progress | blocked | done`
- `target_condition`: `greater_equal | less_equal | equal`

## 跨模块 ID 约束

`ActionCard.target_kr_id` 必须存在于：

`OKRMaster.modules[].key_results[].kr_id`

通过 `validate_actions_against_okr(okr, actions)` 强制校验。

## 示例与失败样例

运行：

```bash
python -m backend.schemas.examples
```

会输出：

- 合法 payload 校验通过
- 非法枚举失败信息
- 跨模块 ID 不存在失败信息
