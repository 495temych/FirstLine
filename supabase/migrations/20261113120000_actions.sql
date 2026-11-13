-- Each action the agent proposes and a person approves runs once. Its key is made
-- from the ticket and the action, in agent/actions.py. A key is claimed before the
-- action runs and keeps its outcome after, so a second attempt with the same key
-- returns the first outcome. A key with no outcome was cut off by a restart, and is
-- held for a person.
--
-- The ticket isn't a reference: an Assistant run acts before its record is saved.

create table actions (
  key text primary key,
  ticket_id text not null,
  tool text not null,
  tool_input jsonb not null,
  outcome jsonb,
  claimed_at timestamptz not null default now(),
  done_at timestamptz,
  check ((outcome is null) = (done_at is null))
);

create index on actions (ticket_id);

alter table actions enable row level security;
