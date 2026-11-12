"""The recorded checks hold what was checked and seen, and never the answer."""

import json

from agent import config
from evals import build_checks
from evals.runner import load_set

STEP = {
    "step_id": "diag-1",
    "playbook_step_id": "vpn-client-check",
    "action": "Checked the client version.",
    "expected_result": "The client is current.",
    "observed_result": "Version 5.1, two releases behind.",
    "result_status": "fail",
    "performed_by": "service_desk",
    "evidence": "Client log shows 5.1.",
}


def checks() -> dict[str, list[dict]]:
    return json.loads(config.CHECKS_FILE.read_text())


def incidents() -> list[dict]:
    return json.loads(build_checks.INCIDENTS_FILE.read_text())


def test_a_check_keeps_the_step_and_what_was_seen():
    incident = {"id": "INC-VDA-0001", "diagnostics": {"steps": [STEP]}}
    assert build_checks.checks_of(incident) == [
        {
            "step": "vpn-client-check",
            "action": "Checked the client version.",
            "expected": "The client is current.",
            "observed": "Version 5.1, two releases behind.",
            "status": "fail",
        }
    ]


def test_the_saved_checks_are_what_the_script_builds():
    assert checks() == build_checks.build_checks(incidents())


def test_no_answer_text_is_in_the_checks():
    saved = checks()
    for incident in incidents():
        text = json.dumps(saved[incident["id"]], ensure_ascii=False)
        answers = [
            incident["diagnostics"]["summary"],
            incident["root_cause"],
            *incident["resolution"]["steps"],
            *(turn["message"] for turn in incident["correspondence"]),
        ]
        leaked = [answer for answer in answers if answer and answer in text]
        assert not leaked, incident["id"]


def test_rules_set_tickets_have_no_checks():
    rules_ids = {ticket["id"] for ticket, _ in load_set("rules")}
    rules_ids |= {ticket["id"] for ticket, _ in load_set("rules_held_out")}
    assert rules_ids
    assert not rules_ids & set(checks())


def test_past_incidents_come_from_the_knowledge_base_split_only():
    past = json.loads(config.PAST_TICKETS_FILE.read_text())
    tickets = json.loads(build_checks.TICKETS_FILE.read_text())
    splits = json.loads(build_checks.SPLITS_FILE.read_text())
    assert past == build_checks.build_past_incidents(incidents(), tickets, splits["kb"])
    assert {incident["id"] for incident in past} == set(splits["kb"])


def test_a_past_incident_keeps_its_cause_and_first_fix():
    incident = {
        "id": "INC-VDA-0001",
        "root_cause": "Old client",
        "resolution": {"steps": ["Updated the client", "Confirmed"]},
    }
    ticket = {"id": "INC-VDA-0001", "title": "VPN drops", "description": "It drops"}
    other = {**ticket, "id": "INC-VDA-0002"}
    assert build_checks.build_past_incidents(
        [incident, {**incident, "id": "INC-VDA-0002"}],
        [ticket, other],
        ["INC-VDA-0001"],
    ) == [
        {
            "id": "INC-VDA-0001",
            "title": "VPN drops",
            "description": "It drops",
            "cause": "Old client",
            "fixed_by": "Updated the client",
        }
    ]
