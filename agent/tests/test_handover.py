"""The SLA deadline: Zürich business hours, Monday to Friday, 08:00 to 17:00."""

from datetime import UTC, datetime

import pytest

from agent import handover


def at(text: str) -> datetime:
    return datetime.fromisoformat(text).astimezone(UTC)


def test_every_queue_in_the_table_has_an_sla_the_code_reads():
    slas = handover.slas()
    assert slas["SEC-INCIDENT"] == "Immediate"
    assert all(handover.sla_hours(sla) is not None for sla in slas.values())


@pytest.mark.parametrize(
    ("start", "hours", "due"),
    [
        ("2025-11-18T09:00+01:00", 4, "2025-11-18T13:00+01:00"),  # within a day
        ("2025-11-18T15:00+01:00", 4, "2025-11-19T10:00+01:00"),  # over the night
        ("2025-11-21T16:00+01:00", 4, "2025-11-24T11:00+01:00"),  # over a weekend
        ("2025-11-22T10:00+01:00", 9, "2025-11-24T17:00+01:00"),  # sent on Saturday
        ("2025-11-18T06:00+01:00", 2, "2025-11-18T10:00+01:00"),  # before opening
        ("2025-11-18T20:00+01:00", 0, "2025-11-18T20:00+01:00"),  # immediate
    ],
)
def test_business_hours_skip_nights_and_weekends(start, hours, due):
    assert handover.add_business_hours(at(start), hours) == at(due)


def test_a_day_is_a_business_day():
    assert handover.sla_hours("1 business day") == handover.HOURS_PER_DAY
    assert handover.sla_hours("2 business days") == 2 * handover.HOURS_PER_DAY
    assert handover.sla_hours("whenever") is None
