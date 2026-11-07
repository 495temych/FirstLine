"""The labelled sets and records must agree with the knowledge base and tools."""

import json
import re
from pathlib import Path

import pytest

from agent import config, retrieval
from agent.tool_schemas import TOOLS
from evals import runner

SETS = ["dev", "held_out"]
USERS = json.loads(config.USERS_FILE.read_text())
PATHS = {"SELF_SERVE", "AUTO_FIX", "ESCALATE", "OUT_OF_SCOPE"}
TEXT_FILES = {".css", ".json", ".md", ".py", ".ts", ".tsx"}


def known_units() -> set[str]:
    return {
        u["doc"] if u["section"] is None else f"{u['doc']}::{u['section']}"
        for u in retrieval._get_units()
    }


def known_queues() -> set[str]:
    text = "\n".join(p.read_text() for p in config.KB_DIR.rglob("*.md"))
    return set(re.findall(r"`([A-Z0-9]+-[A-Z0-9-]+)`", text))


@pytest.mark.parametrize("name", SETS)
def test_sets_have_25_tickets_and_5_tiny(name):
    assert len(runner.load_set(name)) == 25
    assert len(runner.load_set(name, tiny=True)) == 5


@pytest.mark.parametrize("name", SETS)
def test_tiny_covers_every_path_and_the_records(name):
    answers = [a for _, a in runner.load_set(name, tiny=True)]
    assert {p for a in answers for p in a["paths"]} >= PATHS - {"AUTO_FIX"}
    assert any(a["difficulty"] == "records" for a in answers)


@pytest.mark.parametrize("name", SETS)
def test_every_label_exists(name):
    units, queues = known_units(), known_queues()
    tools = {t["name"] for t in TOOLS}
    requesters = {u["id"] for u in USERS}
    for ticket, answer in runner.load_set(name):
        assert ticket["requester"] in requesters
        assert set(answer["paths"]) <= PATHS
        assert set(answer["units"]) <= units
        assert set(answer["tools"]) <= tools
        assert set(answer["queues"]) <= queues
        assert answer["difficulty"] in {"routine", "hard", "records"}


def test_the_sets_share_no_ticket():
    dev = {t["text"] for t, _ in runner.load_set("dev")}
    held_out = {t["text"] for t, _ in runner.load_set("held_out")}
    assert not dev & held_out


def test_lockout_labels_match_the_records():
    lockouts = {u["id"]: u["lockouts_24h"] for u in USERS}
    for name in SETS:
        for ticket, answer in runner.load_set(name):
            if answer["difficulty"] != "records":
                continue
            if lockouts[ticket["requester"]] >= 2:
                assert answer["queues"] == ["SEC-INCIDENT"]
            elif answer["tools"] == ["unlock_ad_account"]:
                assert lockouts[ticket["requester"]] == 1


def test_records_hold_the_directory_and_the_rules_set_users():
    assert len(USERS) == 648
    assert len({u["id"] for u in USERS}) == 648


def test_every_record_has_what_the_tickets_page_shows():
    for user in USERS:
        assert user.keys() >= {"id", "name", "department", "floor", "lockouts_24h"}
        assert user["device"]["id"]


def test_the_old_client_is_gone():
    old = re.compile("|".join(["limm" + "atica", "sihl" + "werk"]), re.IGNORECASE)
    folders = ["agent", "backend", "briefs", "dashboard/src", "docs", "e2e", "evals"]
    paths = [p for f in folders for p in (config.ROOT / f).rglob("*") if p.is_file()]
    paths += [
        p for p in (config.ROOT / "data").rglob("*") if p.suffix in {".md", ".json"}
    ]
    paths += [config.ROOT / "AGENTS.md", config.ROOT / "README.md"]
    text_files = [p for p in paths if p.suffix in TEXT_FILES]
    assert not [p for p in text_files if old.search(p.read_text())]


@pytest.mark.parametrize("package", ["agent", "backend"])
def test_only_the_evals_open_the_answers(package):
    sources = (config.ROOT / package).rglob("*.py")
    assert not [p for p in sources if _names_answers(p)]


def _names_answers(path: Path) -> bool:
    text = path.read_text()
    named = "answers.json" in text or "incidents.json" in text
    return named and "tests" not in path.parts
