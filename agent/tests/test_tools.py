"""The simulated remediation tools."""

import re

import pytest

from agent import tools
from agent.tool_schemas import TOOLS

SAMPLE_ARGS = {
    "username": "current.user",
    "device_id": "current.device",
    "floor": "5",
    "department": "Finance",
    "software_name": "Zoom",
    "queue": "DESKTOP-SUPPORT",
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
