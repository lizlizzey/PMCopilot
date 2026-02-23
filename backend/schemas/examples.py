"""示例 payload 与失败样例。"""

from __future__ import annotations

from pprint import pprint

from .models import ActionCard, OKRMaster, SchemaValidationError, validate_actions_against_okr


OKR_MASTER_PAYLOAD_V1 = {
    "schema_version": "v1",
    "okr_id": "okr-2026-q1",
    "owner": "alice",
    "modules": [
        {
            "schema_version": "v1",
            "module_id": "m-growth",
            "name": "增长",
            "key_results": [
                {
                    "schema_version": "v1",
                    "kr_id": "kr-signup-conv",
                    "title": "注册转化率提升",
                    "status": "in_progress",
                    "target_condition": "greater_equal",
                    "unit": "percentage",
                    "time_granularity": "week",
                    "baseline_value": "12.5",
                    "current_value": "14.2",
                    "target_value": "18",
                }
            ],
        }
    ],
}

ACTION_CARDS_PAYLOAD_V1 = [
    {
        "schema_version": "v1",
        "action_id": "act-landing-revamp",
        "title": "落地页改版",
        "target_kr_id": "kr-signup-conv",
        "status": "in_progress",
    }
]


INVALID_PAYLOAD_SAMPLES = {
    "bad_enum": {
        "schema_version": "v1",
        "okr_id": "okr-2026-q1",
        "owner": "alice",
        "modules": [
            {
                "module_id": "m-1",
                "name": "模块1",
                "key_results": [
                    {
                        "kr_id": "kr-1",
                        "title": "KR",
                        "status": "doing",  # 非法枚举
                        "target_condition": "greater_equal",
                    }
                ],
            }
        ],
    },
    "cross_id_not_found": {
        "okr": OKR_MASTER_PAYLOAD_V1,
        "actions": [
            {
                "schema_version": "v1",
                "action_id": "act-wrong-target",
                "title": "错误关联",
                "target_kr_id": "kr-not-exist",
                "status": "in_progress",
            }
        ],
    },
}


def run_demo() -> None:
    print("=== Valid payload ===")
    okr = OKRMaster.from_payload(OKR_MASTER_PAYLOAD_V1)
    actions = [ActionCard.from_payload(item) for item in ACTION_CARDS_PAYLOAD_V1]
    validate_actions_against_okr(okr, actions)
    print("validation passed")

    print("\n=== Invalid payload: enum ===")
    try:
        OKRMaster.from_payload(INVALID_PAYLOAD_SAMPLES["bad_enum"])
    except SchemaValidationError as exc:
        pprint(exc.errors)

    print("\n=== Invalid payload: cross module id ===")
    try:
        bad_data = INVALID_PAYLOAD_SAMPLES["cross_id_not_found"]
        okr = OKRMaster.from_payload(bad_data["okr"])
        actions = [ActionCard.from_payload(item) for item in bad_data["actions"]]
        validate_actions_against_okr(okr, actions)
    except SchemaValidationError as exc:
        pprint(exc.errors)


if __name__ == "__main__":
    run_demo()
