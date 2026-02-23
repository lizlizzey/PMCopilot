"""统一后端 schema 定义与校验逻辑。"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, Iterable, List, Literal, Optional


SCHEMA_VERSION_V1 = "v1"


class SchemaValidationError(ValueError):
    """结构化校验错误，包含可读的前端联调信息。"""

    def __init__(self, errors: Iterable[str]):
        self.errors = list(errors)
        super().__init__("; ".join(self.errors))


class Status(str, Enum):
    not_started = "not_started"
    in_progress = "in_progress"
    blocked = "blocked"
    done = "done"


class TargetCondition(str, Enum):
    greater_equal = "greater_equal"
    less_equal = "less_equal"
    equal = "equal"


class NumericUnit(str, Enum):
    percentage = "percentage"
    amount = "amount"


class TimeGranularity(str, Enum):
    day = "day"
    week = "week"
    month = "month"


@dataclass(slots=True)
class KeyResult:
    schema_version: Literal["v1"] = SCHEMA_VERSION_V1
    kr_id: str = ""
    title: str = ""
    status: Status = Status.not_started
    target_condition: TargetCondition = TargetCondition.greater_equal
    unit: NumericUnit = NumericUnit.percentage
    time_granularity: TimeGranularity = TimeGranularity.week
    baseline_value: Decimal = Decimal("0")
    current_value: Decimal = Decimal("0")
    target_value: Decimal = Decimal("0")

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> "KeyResult":
        normalized = dict(payload)
        # 兼容历史字段：krId -> kr_id, progress -> current_value
        if "krId" in normalized and "kr_id" not in normalized:
            normalized["kr_id"] = normalized.pop("krId")
        if "progress" in normalized and "current_value" not in normalized:
            normalized["current_value"] = normalized.pop("progress")
        normalized.setdefault("schema_version", SCHEMA_VERSION_V1)
        normalized.setdefault("status", Status.not_started.value)
        normalized.setdefault("target_condition", TargetCondition.greater_equal.value)
        normalized.setdefault("unit", NumericUnit.percentage.value)
        normalized.setdefault("time_granularity", TimeGranularity.week.value)
        normalized.setdefault("baseline_value", "0")
        normalized.setdefault("current_value", "0")
        normalized.setdefault("target_value", "0")

        errors: List[str] = []
        if normalized["schema_version"] != SCHEMA_VERSION_V1:
            errors.append("KeyResult.schema_version 仅支持 'v1'")
        if not normalized.get("kr_id"):
            errors.append("KeyResult.kr_id 不能为空")
        if not normalized.get("title"):
            errors.append("KeyResult.title 不能为空")

        status = _parse_enum(Status, normalized.get("status"), "KeyResult.status", errors)
        target_condition = _parse_enum(
            TargetCondition,
            normalized.get("target_condition"),
            "KeyResult.target_condition",
            errors,
        )
        unit = _parse_enum(NumericUnit, normalized.get("unit"), "KeyResult.unit", errors)
        granularity = _parse_enum(
            TimeGranularity,
            normalized.get("time_granularity"),
            "KeyResult.time_granularity",
            errors,
        )

        baseline = _parse_decimal(normalized.get("baseline_value"), "KeyResult.baseline_value", errors)
        current = _parse_decimal(normalized.get("current_value"), "KeyResult.current_value", errors)
        target = _parse_decimal(normalized.get("target_value"), "KeyResult.target_value", errors)

        if errors:
            raise SchemaValidationError(errors)

        return cls(
            schema_version=SCHEMA_VERSION_V1,
            kr_id=str(normalized["kr_id"]),
            title=str(normalized["title"]),
            status=status,
            target_condition=target_condition,
            unit=unit,
            time_granularity=granularity,
            baseline_value=baseline,
            current_value=current,
            target_value=target,
        )


@dataclass(slots=True)
class Module:
    schema_version: Literal["v1"] = SCHEMA_VERSION_V1
    module_id: str = ""
    name: str = ""
    key_results: List[KeyResult] = field(default_factory=list)

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> "Module":
        normalized = dict(payload)
        if "moduleId" in normalized and "module_id" not in normalized:
            normalized["module_id"] = normalized.pop("moduleId")
        normalized.setdefault("schema_version", SCHEMA_VERSION_V1)
        normalized.setdefault("key_results", [])

        errors: List[str] = []
        if normalized["schema_version"] != SCHEMA_VERSION_V1:
            errors.append("Module.schema_version 仅支持 'v1'")
        if not normalized.get("module_id"):
            errors.append("Module.module_id 不能为空")
        if not normalized.get("name"):
            errors.append("Module.name 不能为空")

        key_results: List[KeyResult] = []
        for idx, kr_payload in enumerate(normalized.get("key_results", [])):
            try:
                key_results.append(KeyResult.from_payload(kr_payload))
            except SchemaValidationError as exc:
                errors.extend([f"Module.key_results[{idx}]: {msg}" for msg in exc.errors])

        if errors:
            raise SchemaValidationError(errors)

        return cls(
            schema_version=SCHEMA_VERSION_V1,
            module_id=str(normalized["module_id"]),
            name=str(normalized["name"]),
            key_results=key_results,
        )


@dataclass(slots=True)
class OKRMaster:
    schema_version: Literal["v1"] = SCHEMA_VERSION_V1
    okr_id: str = ""
    owner: str = ""
    modules: List[Module] = field(default_factory=list)

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> "OKRMaster":
        normalized = dict(payload)
        if "okrId" in normalized and "okr_id" not in normalized:
            normalized["okr_id"] = normalized.pop("okrId")
        normalized.setdefault("schema_version", SCHEMA_VERSION_V1)
        normalized.setdefault("modules", [])

        errors: List[str] = []
        if normalized["schema_version"] != SCHEMA_VERSION_V1:
            errors.append("OKRMaster.schema_version 仅支持 'v1'")
        if not normalized.get("okr_id"):
            errors.append("OKRMaster.okr_id 不能为空")
        if not normalized.get("owner"):
            errors.append("OKRMaster.owner 不能为空")

        modules: List[Module] = []
        for idx, module_payload in enumerate(normalized.get("modules", [])):
            try:
                modules.append(Module.from_payload(module_payload))
            except SchemaValidationError as exc:
                errors.extend([f"OKRMaster.modules[{idx}]: {msg}" for msg in exc.errors])

        kr_ids = [kr.kr_id for m in modules for kr in m.key_results]
        duplicated = sorted({kr_id for kr_id in kr_ids if kr_ids.count(kr_id) > 1})
        if duplicated:
            errors.append(f"OKRMaster.modules[].key_results[].kr_id 不允许重复: {duplicated}")

        if errors:
            raise SchemaValidationError(errors)

        return cls(
            schema_version=SCHEMA_VERSION_V1,
            okr_id=str(normalized["okr_id"]),
            owner=str(normalized["owner"]),
            modules=modules,
        )

    def all_kr_ids(self) -> set[str]:
        return {kr.kr_id for module in self.modules for kr in module.key_results}


@dataclass(slots=True)
class ActionCard:
    schema_version: Literal["v1"] = SCHEMA_VERSION_V1
    action_id: str = ""
    title: str = ""
    target_kr_id: str = ""
    status: Status = Status.not_started

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> "ActionCard":
        normalized = dict(payload)
        if "actionId" in normalized and "action_id" not in normalized:
            normalized["action_id"] = normalized.pop("actionId")
        normalized.setdefault("schema_version", SCHEMA_VERSION_V1)
        normalized.setdefault("status", Status.not_started.value)

        errors: List[str] = []
        if normalized["schema_version"] != SCHEMA_VERSION_V1:
            errors.append("ActionCard.schema_version 仅支持 'v1'")
        if not normalized.get("action_id"):
            errors.append("ActionCard.action_id 不能为空")
        if not normalized.get("title"):
            errors.append("ActionCard.title 不能为空")
        if not normalized.get("target_kr_id"):
            errors.append("ActionCard.target_kr_id 不能为空")

        status = _parse_enum(Status, normalized.get("status"), "ActionCard.status", errors)

        if errors:
            raise SchemaValidationError(errors)

        return cls(
            schema_version=SCHEMA_VERSION_V1,
            action_id=str(normalized["action_id"]),
            title=str(normalized["title"]),
            target_kr_id=str(normalized["target_kr_id"]),
            status=status,
        )


@dataclass(slots=True)
class MetricPoint:
    timestamp: str = ""
    value: Decimal = Decimal("0")


@dataclass(slots=True)
class MetricSeries:
    schema_version: Literal["v1"] = SCHEMA_VERSION_V1
    metric_id: str = ""
    kr_id: str = ""
    unit: NumericUnit = NumericUnit.percentage
    time_granularity: TimeGranularity = TimeGranularity.day
    points: List[MetricPoint] = field(default_factory=list)


@dataclass(slots=True)
class RetroReport:
    schema_version: Literal["v1"] = SCHEMA_VERSION_V1
    report_id: str = ""
    module_id: str = ""
    highlights: List[str] = field(default_factory=list)
    blockers: List[str] = field(default_factory=list)
    next_actions: List[str] = field(default_factory=list)


def validate_actions_against_okr(okr: OKRMaster, actions: List[ActionCard]) -> None:
    """跨模块 ID 约束：ActionCard.target_kr_id 必须存在于 OKRMaster。"""

    allowed = okr.all_kr_ids()
    errors = [
        f"ActionCard[{idx}].target_kr_id='{action.target_kr_id}' 不存在于 OKRMaster.modules[].key_results[].kr_id"
        for idx, action in enumerate(actions)
        if action.target_kr_id not in allowed
    ]
    if errors:
        raise SchemaValidationError(errors)


def _parse_enum(enum_cls: type[Enum], value: Any, field_name: str, errors: List[str]):
    try:
        return enum_cls(value)
    except Exception:
        errors.append(f"{field_name} 非法值: {value!r}，可选值: {[e.value for e in enum_cls]}")
        return list(enum_cls)[0]


def _parse_decimal(value: Any, field_name: str, errors: List[str]) -> Decimal:
    try:
        return Decimal(str(value))
    except Exception:
        errors.append(f"{field_name} 必须是数值")
        return Decimal("0")
