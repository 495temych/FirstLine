"""The read-only lookups, and what code lets each one read."""

import json

from agent import config, lookups
from agent.tests.fakes import UNIT


def test_the_requester_lookup_has_lockouts_and_recent_tickets_but_no_name():
    record = lookups.lookup_requester("s.keller")
    assert record["found"]
    assert record["lockouts_24h"] == 2
    assert len(record["recent_tickets"]) == 2
    assert "name" not in record
    assert "email" not in record


def test_an_unknown_or_missing_requester_is_said_so():
    assert not lookups.lookup_requester(None)["found"]
    assert lookups.lookup_requester("nobody")["reason"] == "No staff record for nobody."


def test_similar_incidents_come_from_the_knowledge_base_split_only():
    splits = json.loads((config.TICKETS_DIR / "splits.json").read_text())
    tickets = json.loads((config.TICKETS_DIR / "tickets.json").read_text())
    dev = {t["id"]: t for t in tickets if t["id"] in set(splits["dev"])}
    for ticket in list(dev.values())[:20]:
        found = lookups.find_similar_incidents(
            f"{ticket['title']} {ticket['description']}"
        )
        assert found
        assert {i["id"] for i in found} <= set(splits["kb"])
        assert all(i["cause"] and i["fixed_by"] for i in found)


def test_similar_incidents_find_the_same_family():
    found = lookups.find_similar_incidents("account locked again after password reset")
    assert found[0]["id"].startswith("INC-ALP-")
    assert len(found) == lookups.SIMILAR_LIMIT


def test_nothing_in_common_finds_nothing():
    assert lookups.find_similar_incidents("zz qq") == []


def test_search_returns_what_retrieval_found(monkeypatch):
    monkeypatch.setattr(lookups, "retrieve", lambda q: [{**UNIT, "score": 0.8123}])
    assert lookups.search_kb("vpn") == [
        {"doc": "vpn", "section": None, "score": 0.81, "text": "VPN playbook"}
    ]


def test_a_check_reads_only_the_ticket_it_is_given():
    found = lookups.run_check("INC-ALP-0001", "account-lockout-source-check")
    assert found["found"]
    assert found["status"] == "fail"
    assert not lookups.run_check("INC-ALP-0001", "print-spooler-check")["found"]
    assert not lookups.run_check(None, "account-lockout-source-check")["found"]
