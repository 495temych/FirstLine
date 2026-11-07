"""The decision format: what it records, and what happens when it can't be used."""

from agent.decision import DECISION_TOOL, Decision, read_decision, tool_guide


def arguments(path, **fields):
    return {"rationale": "Why.", "cause": "Stale VPN profile", "path": path, **fields}


def test_the_rationale_comes_first():
    assert next(iter(Decision.model_fields)) == "rationale"
    assert next(iter(DECISION_TOOL["input_schema"]["properties"])) == "rationale"


def test_a_fix_keeps_its_tool_and_values():
    state = read_decision(
        arguments("AUTO_FIX", tool="reset_vpn_profile", tool_input={"username": "a.b"})
    )
    assert state["path"] == "AUTO_FIX"
    assert state["tool_name"] == "reset_vpn_profile"
    assert state["tool_input"] == {"username": "a.b"}
    assert state["cause"] == "Stale VPN profile"


def test_a_fix_with_an_unknown_tool_goes_to_a_person():
    state = read_decision(arguments("AUTO_FIX", tool="format_disk"))
    assert state["path"] == "ESCALATE"
    assert state["tool_name"] == "create_escalation_ticket"
    assert state["tool_input"]["queue"] == "DESK-SUPPORT"


def test_a_fix_can_never_be_the_escalation_tool():
    state = read_decision(arguments("AUTO_FIX", tool="create_escalation_ticket"))
    assert state["path"] == "ESCALATE"
    assert state["tool_input"]["queue"] == "DESK-SUPPORT"


def test_an_escalation_becomes_a_ticket():
    state = read_decision(
        arguments(
            "ESCALATE", queue="SEC-INCIDENT", summary="Repeats", priority="P2-High"
        )
    )
    assert state["tool_name"] == "create_escalation_ticket"
    assert state["tool_input"] == {
        "queue": "SEC-INCIDENT",
        "summary": "Repeats",
        "priority": "P2-High",
    }


def test_an_unknown_queue_goes_to_desktop_support():
    state = read_decision(arguments("ESCALATE", queue="MADE-UP"))
    assert state["tool_input"]["queue"] == "DESK-SUPPORT"
    assert state["tool_input"]["summary"] == "Why."


def test_steps_follow_the_rationale():
    state = read_decision(arguments("SELF_SERVE", steps=["One.", "Two."]))
    assert state["reasoning"] == "Why.\n\n1. One.\n2. Two."
    assert state["tool_name"] is None


def test_out_of_scope_has_no_tool():
    state = read_decision(arguments("OUT_OF_SCOPE", tool="reset_vpn_profile"))
    assert state["path"] == "OUT_OF_SCOPE"
    assert state["tool_name"] is None
    assert state["tool_input"] is None


def test_a_missing_or_broken_decision_goes_to_a_person():
    for broken in (None, {"path": "PANIC"}):
        state = read_decision(broken)
        assert state["path"] == "ESCALATE"
        assert "couldn't be read" in state["reasoning"]


def test_the_guide_lists_fixes_and_not_the_ticket_tool():
    guide = tool_guide()
    assert "reset_vpn_profile(username)" in guide
    assert "create_escalation_ticket" not in guide
