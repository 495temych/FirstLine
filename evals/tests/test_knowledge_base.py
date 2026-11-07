"""The playbooks follow one template and come only from the knowledge base split."""

import json
import re
from pathlib import Path

import pytest

from agent import config, retrieval
from agent.tool_schemas import TOOLS
from evals import import_tickets

SECTIONS = [
    "Symptoms",
    "Checks",
    "Error codes",
    "Known causes",
    "Fix",
    "When to escalate",
]
FIELDS = {
    "id",
    "title",
    "family",
    "owner_team",
    "last_reviewed",
    "applications",
    "tools",
}
EXTRA_PLAYBOOKS = {"onedrive", "teams", "hardware-peripherals"}
PLAYBOOKS = sorted((config.KB_DIR / "playbooks").glob("*.md"))


def fields(path: Path) -> dict:
    return retrieval.read_playbook(path.read_text())[0]


def body(path: Path) -> str:
    return retrieval.read_playbook(path.read_text())[1]


def problems(text: str) -> list[str]:
    """What breaks the template in one playbook, if anything."""
    meta, playbook_body = retrieval.read_playbook(text)
    missing = [name for name in sorted(FIELDS) if not meta.get(name)]
    if re.findall(r"(?m)^## (.+)$", playbook_body) != SECTIONS:
        missing.append("sections")
    return missing


def splits() -> dict[str, list[str]]:
    return json.loads((config.TICKETS_DIR / "splits.json").read_text())


def kb_text() -> str:
    """Everything the knowledge base split may draw on."""
    members = set(splits()["kb"])
    tickets = json.loads((config.TICKETS_DIR / "tickets.json").read_text())
    incidents = json.loads((config.EVALS_DIR / "incidents.json").read_text())
    return json.dumps(
        [t for t in tickets if t["id"] in members]
        + [i for i in incidents if i["id"] in members]
    )


def test_there_are_12_family_playbooks_and_three_more():
    families = [fields(p)["family"] for p in PLAYBOOKS]
    assert len(PLAYBOOKS) == 15
    assert families.count("null") == len(EXTRA_PLAYBOOKS)
    assert len({f for f in families if f != "null"}) == 12


@pytest.mark.parametrize("path", PLAYBOOKS, ids=lambda p: p.stem)
def test_every_playbook_follows_the_template(path):
    assert problems(path.read_text()) == []
    assert fields(path).keys() == FIELDS
    assert fields(path)["id"] == path.stem


def test_a_missing_section_fails_the_template():
    text = PLAYBOOKS[0].read_text().replace("## Fix", "## Repair")
    assert problems(text) == ["sections"]


def test_a_missing_field_fails_the_template():
    text = PLAYBOOKS[0].read_text().replace("owner_team:", "owner:")
    assert problems(text) == ["owner_team"]


@pytest.mark.parametrize("path", PLAYBOOKS, ids=lambda p: p.stem)
def test_every_tool_a_playbook_names_exists(path):
    known = {t["name"] for t in TOOLS}
    listed = fields(path)["tools"].strip("[]").split(", ")
    assert {t for t in listed if t} <= known


def test_unseen_families_have_no_playbook():
    families = {fields(p)["family"] for p in PLAYBOOKS}
    assert not import_tickets.UNSEEN_FAMILIES & families


def test_families_point_to_the_playbook_that_claims_them():
    mapped = json.loads((config.EVALS_DIR / "families.json").read_text())
    claimed = {fields(p)["family"]: p.stem for p in PLAYBOOKS}
    for family, details in mapped.items():
        assert details["doc"] == claimed.get(family)


def test_no_development_or_held_out_ticket_appears_in_the_knowledge_base():
    text = "\n".join(p.read_text() for p in config.KB_DIR.rglob("*.md"))
    sets = splits()
    closed = [i for name, ids in sets.items() if name != "kb" for i in ids]
    assert len(closed) == 361
    assert not [ticket_id for ticket_id in closed if ticket_id in text]


def test_every_error_code_comes_from_the_knowledge_base_split():
    known = kb_text()
    family_playbooks = [p for p in PLAYBOOKS if p.stem not in EXTRA_PLAYBOOKS]
    for path in family_playbooks:
        section = body(path).split("## Error codes")[1].split("## Known causes")[0]
        codes = re.findall(r"(?m)^- `([^`]+)`", section)
        assert codes
        missing = [c for c in codes if c not in known]
        assert not missing, f"{path.stem}: {missing}"
