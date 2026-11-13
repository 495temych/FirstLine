"""Each action runs once, by its key, whatever asks for it again."""

import pytest

from agent import actions, tools


@pytest.fixture
def ran(monkeypatch):
    """Every action that really ran, in order."""
    done: list[tuple[str, dict]] = []
    dispatch = tools.dispatch

    def counted(tool, tool_input):
        done.append((tool, tool_input))
        return dispatch(tool, tool_input)

    monkeypatch.setattr(tools, "dispatch", counted)
    return done


ESCALATE = ("create_escalation_ticket", {"queue": "NET-VPN", "summary": "VPN down"})


def test_the_key_is_made_from_the_ticket_and_the_action():
    tool, tool_input = ESCALATE
    key = actions.key_of("INC1", tool, tool_input)
    assert key == actions.key_of("INC1", tool, dict(reversed(tool_input.items())))
    assert key != actions.key_of("INC2", tool, tool_input)
    assert key != actions.key_of("INC1", tool, {**tool_input, "queue": "SEC-INCIDENT"})


def test_a_second_attempt_returns_the_first_outcome_without_running(ran):
    ledger = actions.MemoryLedger()
    first = actions.perform(ledger, "INC1", *ESCALATE)
    again = actions.perform(ledger, "INC1", *ESCALATE)
    assert again == first
    assert len(ran) == 1
    assert first["action_key"] == actions.key_of("INC1", *ESCALATE)


def test_the_same_action_on_another_ticket_runs(ran):
    ledger = actions.MemoryLedger()
    actions.perform(ledger, "INC1", *ESCALATE)
    actions.perform(ledger, "INC2", *ESCALATE)
    assert len(ran) == 2


class Killed(BaseException):
    """The process stopped here."""


def test_an_action_cut_off_mid_run_is_held_not_run_again(ran, monkeypatch):
    ledger = actions.MemoryLedger()

    def cut_off(tool, tool_input):
        ran.append((tool, tool_input))
        raise Killed

    monkeypatch.setattr(tools, "dispatch", cut_off)
    with pytest.raises(Killed):
        actions.perform(ledger, "INC1", *ESCALATE)
    held = actions.perform(ledger, "INC1", *ESCALATE)
    assert held["status"] == "held"
    assert len(ran) == 1


def test_an_action_whose_input_does_not_fit_gives_its_key_back(ran):
    ledger = actions.MemoryLedger()
    with pytest.raises(TypeError):
        actions.perform(ledger, "INC1", "reset_vpn_profile", {"nobody": "x"})
    key = actions.key_of("INC1", "reset_vpn_profile", {"nobody": "x"})
    assert ledger.claim(key, "INC1", "reset_vpn_profile", {"nobody": "x"})


def test_the_backend_installs_its_own_ledger(monkeypatch):
    monkeypatch.setattr(actions, "_installed", [actions.MemoryLedger()])
    mine = actions.MemoryLedger()
    actions.use(mine)
    assert actions.ledger() is mine
