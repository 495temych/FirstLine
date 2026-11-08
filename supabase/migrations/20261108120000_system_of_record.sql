-- FirstLine's system of record: what happens to each ticket at runtime.
--
-- A ticket arrives, sometimes in a morning batch. The agent decides, a person
-- reviews the decision, and each step is an event in the audit trail. Whether a
-- ticket waits for review follows from the data: a decision with no review.
--
-- Labels, the knowledge base, staff records and evaluation runs stay in git.
-- LangGraph creates its own checkpoint tables.
--
-- Row-level security is on with no policies, so Supabase's public API key
-- can't reach these tables. The backend connects to the database directly.

create table batches (
  id uuid primary key default gen_random_uuid(),
  note text,
  created_at timestamptz not null default now()
);

create table tickets (
  id text primary key,
  text text not null,
  requester text not null,
  mode text not null check (mode in ('queue', 'assistant')),
  batch_id uuid references batches,
  created_at timestamptz not null default now(),
  check (mode = 'queue' or batch_id is null)
);

create table decisions (
  id uuid primary key default gen_random_uuid(),
  ticket_id text not null references tickets,
  path text not null
    check (path in ('SELF_SERVE', 'AUTO_FIX', 'ESCALATE', 'OUT_OF_SCOPE')),
  tool text,
  tool_input jsonb,
  queue text,
  priority text,
  cause text,
  rationale text,
  summary text,
  retrieved text[] not null default '{}',
  model text not null,
  version text not null,
  trace_id text,
  cost_usd numeric,
  latency_ms integer,
  created_at timestamptz not null default now()
);

create table reviews (
  id uuid primary key default gen_random_uuid(),
  decision_id uuid not null unique references decisions,
  verdict text not null check (verdict in ('approved', 'corrected', 'rejected')),
  correction jsonb,
  reviewer text not null,
  seconds_spent integer check (seconds_spent >= 0),
  note text,
  created_at timestamptz not null default now(),
  check (verdict = 'corrected' or correction is null)
);

create table events (
  id bigint generated always as identity primary key,
  ticket_id text not null references tickets,
  actor text not null check (actor in ('agent', 'code', 'person')),
  kind text not null,
  detail jsonb not null default '{}',
  at timestamptz not null default now()
);

create index on tickets (batch_id);
create index on decisions (ticket_id);
create index on events (ticket_id, at);

alter table batches enable row level security;
alter table tickets enable row level security;
alter table decisions enable row level security;
alter table reviews enable row level security;
alter table events enable row level security;
