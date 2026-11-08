-- Each retrieved section keeps its score, so a technician sees how well the
-- knowledge used matched: [{"doc": ..., "section": ..., "score": ...}].

alter table decisions alter column retrieved drop default;
alter table decisions
  alter column retrieved type jsonb using to_jsonb(retrieved);
alter table decisions alter column retrieved set default '[]'::jsonb;
