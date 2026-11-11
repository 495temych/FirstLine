-- The rule in agent/rules.py that changed a decision, with its reason and what the
-- agent proposed. Null when no rule changed it.
alter table decisions add column rule jsonb;
