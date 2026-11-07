"""The import keeps answers apart from tickets, and the splits are fixed."""

import csv
import json
from collections import Counter

from agent import config
from evals import import_tickets as importer

SET_NAMES = {"kb", "dev", "held_out", "unseen_dev", "unseen_held_out"}
ANSWER_FIELDS = {"correspondence", "diagnostics", "root_cause", "resolution"}
DIRECTORY = [
    {"username": "amy", "display_name": "Amy Lee", "email": "amy@corplabs.com"},
    {"username": "bo", "display_name": "Bo Berg", "email": "bo@corplabs.com"},
]


def row(ticket_id: str = "INC-ALP-0001") -> dict:
    return {
        "record_id": ticket_id,
        "record_type": "incident",
        "status": "closed",
        "ticket": json.dumps(
            {
                "submitted_at": "2025-11-18T08:00:00Z",
                "submitted_title": "Locked out",
                "submitted_description": "My account is locked",
                "priority": "high",
                "sla_plan": "Business-hours SLA",
                "environment": {"os": "iOS"},
                "applications": ["SSO Portal"],
            }
        ),
        "correspondence": json.dumps([{"message": "Hi"}]),
        "diagnostics": json.dumps({"summary": "Found it"}),
        "root_cause": "Cached credentials",
        "resolution": json.dumps({"steps": ["Cleared them"]}),
    }


def saved_tickets() -> list[dict]:
    return json.loads((config.TICKETS_DIR / "tickets.json").read_text())


def saved_splits() -> dict[str, list[str]]:
    return json.loads((config.TICKETS_DIR / "splits.json").read_text())


def test_the_family_comes_from_the_id():
    assert importer.family_of("INC-ALP-0001") == "ALP"


def test_a_record_splits_into_what_arrived_and_what_came_after():
    ticket, incident = importer.split_record(row())
    assert ticket["title"] == "Locked out"
    assert ticket["applications"] == ["SSO Portal"]
    assert not ANSWER_FIELDS & ticket.keys()
    assert incident["root_cause"] == "Cached credentials"
    assert incident["resolution"] == {"steps": ["Cleared them"]}


def test_a_family_splits_60_20_20():
    sets = importer.split_ids(f"INC-ALP-{n:04}" for n in range(100))
    assert {name: len(ids) for name, ids in sets.items()} == {
        "dev": 20,
        "held_out": 20,
        "kb": 60,
    }


def test_unseen_families_stay_out_of_the_knowledge_base():
    ids = [f"INC-CES-{n:04}" for n in range(10)]
    sets = importer.split_ids(ids)
    assert set(sets) == {"unseen_dev", "unseen_held_out"}
    assert len(sets["unseen_dev"]) == len(sets["unseen_held_out"]) == 5


def test_the_order_of_the_input_does_not_change_the_split():
    ids = [f"INC-ALP-{n:04}" for n in range(50)]
    assert importer.split_ids(ids) == importer.split_ids(reversed(ids))


def test_the_requester_is_the_account_named_first():
    pii = [{"value": "bo"}, {"value": "Amy Lee"}, {"value": "Portland"}]
    assert importer.find_requester("Amy Lee here, bo agrees", pii, DIRECTORY) == "amy"


def test_a_requester_can_come_from_a_later_record():
    pii = [{"value": "bo"}]
    assert importer.find_requester("My VPN is down", pii, DIRECTORY) == "bo"


def test_no_named_account_means_no_requester():
    assert importer.find_requester("My VPN is down", [], DIRECTORY) is None


def test_invented_details_stay_the_same_and_keep_the_real_ones():
    first = importer.invent_record(DIRECTORY[0], "Sales")
    assert first == importer.invent_record(DIRECTORY[0], "Sales")
    assert first["name"] == "Amy Lee"
    assert first["department"] == "Sales"
    assert first["device"]["id"] == "LT-AMY"


def test_a_repeated_username_keeps_its_first_person():
    twins = [*DIRECTORY, {**DIRECTORY[0], "display_name": "Amy Lund"}]
    records = importer.build_records(twins, [], [])
    assert [r["name"] for r in records] == ["Amy Lee", "Bo Berg"]


def test_lockout_history_matches_the_count():
    history = importer._lockout_history(2)
    assert history[1] == "Account lockout, 2 of 2 in the last 24 hours"


def test_the_import_writes_tickets_answers_splits_and_records(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    with (source / "itsm_ticket_corpus_flat.csv").open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(row()))
        writer.writeheader()
        writer.writerows(row(f"INC-ALP-{n:04}") for n in range(5))
    (source / "pii.json").write_text(
        json.dumps(
            [
                {"ticket_id": f"INC-ALP-{n:04}", "pii_instances": [{"value": "amy"}]}
                for n in range(5)
            ]
        )
    )
    (source / "users_directory.json").write_text(json.dumps({"users": DIRECTORY}))
    users = tmp_path / "users.json"
    users.write_text(json.dumps([{"id": "s.keller"}]))
    tickets_dir, evals_dir = tmp_path / "tickets", tmp_path / "evals"
    importer.import_tickets(source, tickets_dir, evals_dir, users)
    tickets = json.loads((tickets_dir / "tickets.json").read_text())
    incidents = json.loads((evals_dir / "incidents.json").read_text())
    assert len(tickets) == len(incidents) == 5
    assert tickets[0]["requester"] == "amy"
    assert (tickets_dir / "splits.json").exists()
    records = json.loads(users.read_text())
    assert [r["id"] for r in records] == ["amy", "bo", "s.keller"]
    assert records[2]["office"] == "Zürich"
    assert records[0]["department"] in importer.DEPARTMENTS


def test_every_ticket_links_to_a_staff_record():
    ids = {u["id"] for u in json.loads(config.USERS_FILE.read_text())}
    assert all(t["requester"] in ids for t in saved_tickets())


def test_all_745_tickets_are_in_exactly_one_set():
    splits = saved_splits()
    assert set(splits) == SET_NAMES
    members = [ticket_id for ids in splits.values() for ticket_id in ids]
    assert len(members) == len(set(members)) == 745
    assert set(members) == {t["id"] for t in saved_tickets()}


def test_the_saved_splits_can_be_rebuilt():
    assert saved_splits() == importer.split_ids(t["id"] for t in saved_tickets())


def test_every_family_is_split_evenly():
    splits = saved_splits()
    knowledge_base = Counter(importer.family_of(i) for i in splits["kb"])
    development = Counter(importer.family_of(i) for i in splits["dev"])
    held_out = Counter(importer.family_of(i) for i in splits["held_out"])
    assert len(knowledge_base) == 12
    assert not importer.UNSEEN_FAMILIES & knowledge_base.keys()
    for family, count in knowledge_base.items():
        assert abs(development[family] - held_out[family]) <= 1
        assert 2.5 < count / development[family] < 3.5


def test_saved_tickets_hold_no_answers():
    tickets = saved_tickets()
    assert not any(ANSWER_FIELDS & t.keys() for t in tickets)
    incidents = json.loads((config.EVALS_DIR / "incidents.json").read_text())
    arrived = {t["id"]: json.dumps(t) for t in tickets}
    assert not [i["id"] for i in incidents if i["root_cause"] in arrived[i["id"]]]


def test_the_source_and_its_licence_are_recorded():
    source = (config.TICKETS_DIR / "SOURCE.md").read_text()
    assert "MIT" in source
    assert "synthetic" in source
