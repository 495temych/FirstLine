"""The simulated remediation tools."""

import re

import pytest

from agent import tools
from agent.tool_schemas import ROUTINE, SENSITIVE, TOOL_POLICY, TOOLS

SAMPLE_ARGS = {
    "group": "FIN_SHARE",
    "username": "current.user",
    "device_id": "current.device",
    "floor": "5",
    "department": "Finance",
    "software_name": "Zoom",
    "queue": "DESK-SUPPORT",
    "summary": "A summary",
    "priority": "P3-Normal",
}


def args_for(schema: dict) -> dict:
    return {k: SAMPLE_ARGS[k] for k in schema["input_schema"]["required"]}


def test_every_schema_has_a_tool_and_every_tool_a_schema():
    assert {t["name"] for t in TOOLS} == set(tools.REGISTRY)


@pytest.mark.parametrize("schema", TOOLS, ids=lambda t: t["name"])
def test_every_tool_says_it_is_simulated(schema):
    result = tools.dispatch(schema["name"], args_for(schema))
    assert result["simulated"] is True
    assert result["status"] == "success"
    assert result["action"] == schema["name"]


def test_escalation_ticket_has_a_number_and_keeps_its_queue():
    result = tools.dispatch(
        "create_escalation_ticket",
        {"queue": "SEC-INCIDENT", "summary": "s", "priority": "P2-High"},
    )
    assert re.fullmatch(r"INC\d{7}", result["ticket_number"])
    assert result["queue"] == "SEC-INCIDENT"
    assert result["priority"] == "P2-High"


def test_an_unknown_tool_is_refused():
    with pytest.raises(KeyError):
        tools.dispatch("format_the_disk", {})


def test_every_tool_has_a_tier_and_an_owner():
    assert TOOL_POLICY.keys() == {t["name"] for t in TOOLS}
    for policy in TOOL_POLICY.values():
        assert policy["tier"] in {ROUTINE, SENSITIVE}
        assert policy["owner"]


def test_tools_that_touch_access_or_security_need_a_technician():
    for name in [
        "unlock_ad_account",
        "add_user_to_share_group",
        "escrow_bitlocker_key",
    ]:
        assert TOOL_POLICY[name]["tier"] == SENSITIVE


def test_every_family_l1_can_fix_has_a_tool():
    covered = {f for p in TOOL_POLICY.values() for f in p["families"]}
    assert covered == {
        "ALP",
        "DCP",
        "EDE",
        "LPD",
        "OES",
        "PDQ",
        "SDA",
        "SIB",
        "VDA",
        "WCI",
    }


@pytest.mark.parametrize(
    ("name", "arguments"),
    [
        ("reinstall_print_driver", {"queue": "ZRH-3F"}),
        ("reset_mobile_mail_profile", {"username": "amy"}),
        ("push_wifi_profile", {"device_id": "LT-AMY"}),
        ("add_user_to_share_group", {"username": "amy", "group": "FIN_SHARE"}),
        ("force_intune_sync", {"device_id": "LT-AMY"}),
        ("escrow_bitlocker_key", {"device_id": "LT-AMY"}),
        ("clean_temp_files", {"device_id": "LT-AMY"}),
    ],
)
def test_new_tools_are_simulated(name, arguments):
    result = tools.dispatch(name, arguments)
    assert result["simulated"]
    assert result["status"] == "success"
