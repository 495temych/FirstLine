"""Every ticket has one named cause, and every cause says what a first pass does."""

import json
import re

import pytest

from agent import config
from agent.tool_schemas import TOOLS
from evals import import_tickets, label_tickets

CAUSES = label_tickets.load_causes()
LABELS = json.loads(label_tickets.LABELS_FILE.read_text())
PATHS = {"SELF_SERVE", "AUTO_FIX", "ESCALATE", "OUT_OF_SCOPE"}
INCIDENTS = json.loads((config.EVALS_DIR / "incidents.json").read_text())
TICKETS = json.loads((config.TICKETS_DIR / "tickets.json").read_text())
USERS = json.loads(config.USERS_FILE.read_text())


def cause(**fields) -> dict:
    return {"id": "a", "family": "VDA", "match": [], "otherwise": [], **fields}


def known_queues() -> set[str]:
    text = "\n".join(p.read_text() for p in config.KB_DIR.rglob("*.md"))
    return set(re.findall(r"`([A-Z0-9]+-[A-Z0-9-]+)`", text))


def known_checks(family: str) -> set[str]:
    return {
        step["playbook_step_id"]
        for incident in INCIDENTS
        if import_tickets.family_of(incident["id"]) == family
        for step in incident["diagnostics"]["steps"]
    }


def test_every_ticket_has_one_cause():
    assert sorted(x["id"] for x in LABELS) == sorted(t["id"] for t in TICKETS)
    names = {c["id"] for c in CAUSES}
    assert {x["cause"] for x in LABELS} <= names


def test_the_labels_are_what_the_rules_give():
    labels, unnamed = label_tickets.build_labels(INCIDENTS, TICKETS, USERS, CAUSES)
    assert unnamed == []
    assert labels == LABELS


@pytest.mark.parametrize("item", CAUSES, ids=lambda c: c["id"])
def test_every_cause_has_a_workable_answer(item):
    assert item["paths"]
    assert set(item["paths"]) <= PATHS
    assert {t["name"] for t in TOOLS} >= set(item["tools"])
    assert known_queues() >= set(item["queues"])
    if "AUTO_FIX" in item["paths"]:
        assert item["tools"]
    if "ESCALATE" in item["paths"] and item["family"] != label_tickets.ANY_FAMILY:
        assert item["queues"]


@pytest.mark.parametrize("item", CAUSES, ids=lambda c: c["id"])
def test_required_checks_exist_for_the_family(item):
    assert set(item["checks"]) <= known_checks(item["family"])


def test_families_with_no_playbook_only_escalate():
    for item in CAUSES:
        if item["family"] in import_tickets.UNSEEN_FAMILIES:
            assert item["paths"] == ["ESCALATE"]
            assert not item["tools"]


def test_the_cause_named_first_wins():
    causes = [cause(id="a", match=["alpha"]), cause(id="b", match=["beta"])]
    named = label_tickets.name_cause("VDA", "beta, then alpha", causes)
    assert named
    assert named["id"] == "b"


def test_vague_wording_only_counts_as_a_last_resort():
    causes = [cause(id="a", otherwise=["vague"]), cause(id="b", match=["exact"])]
    named = label_tickets.name_cause("VDA", "vague, then exact", causes)
    assert named
    assert named["id"] == "b"
    named = label_tickets.name_cause("VDA", "only vague", causes)
    assert named
    assert named["id"] == "a"


def test_an_unconfirmed_cause_applies_to_every_family():
    causes = [
        cause(id="a", match=["vpn"]),
        cause(id="u", family="*", match=["unknown"]),
    ]
    named = label_tickets.name_cause("VDA", "vpn fault, cause unknown", causes)
    assert named
    assert named["id"] == "u"


def test_a_cause_from_another_family_never_matches():
    assert label_tickets.name_cause("WCI", "alpha", [cause(match=["alpha"])]) is None


def test_a_ticket_no_rule_names_is_reported():
    incident = {"id": "INC-VDA-0001", "root_cause": "nothing"}
    ticket = {"id": "INC-VDA-0001", "requester": "u"}
    users = [{"id": "u", "lockouts_24h": 0}]
    labels, unnamed = label_tickets.build_labels([incident], [ticket], users, [])
    assert labels == []
    assert unnamed == ["INC-VDA-0001"]


def test_repeat_lockouts_in_the_records_go_to_security():
    item = cause(paths=["AUTO_FIX"], tools=["unlock_ad_account"], queues=[], checks=[])
    label = label_tickets.label("INC-ALP-0001", item, lockouts=2)
    assert label["paths"] == ["ESCALATE"]
    assert label["queues"] == ["SEC-INCIDENT"]
    assert label["tools"] == []
    assert label_tickets.label("INC-ALP-0001", item, lockouts=1)["tools"]


def test_repeat_lockouts_change_only_lockout_tickets():
    item = cause(paths=["AUTO_FIX"], tools=["reset_vpn_profile"], queues=[], checks=[])
    assert label_tickets.label("INC-VDA-0001", item, lockouts=3)["tools"]


def test_the_command_writes_the_labels(tmp_path, monkeypatch, capsys):
    path = tmp_path / "labels.json"
    monkeypatch.setattr(label_tickets, "LABELS_FILE", path)
    label_tickets.main()
    assert json.loads(path.read_text()) == LABELS
    assert "745 tickets labelled, 0 unnamed" in capsys.readouterr().out
