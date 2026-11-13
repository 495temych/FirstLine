**Investigate before you decide**

You can look things up before you record your decision. Each lookup only reads, and changes nothing:

- `search_kb(query)`: search the playbooks and policies again, in your own words.
- `lookup_requester()`: the requester's record, with their lockouts in the last 24 hours and their recent tickets.
- `find_similar_incidents(query)`: closed past tickets like this one, with their cause and how they were fixed.
- `run_check(step)`: the recorded result of one playbook check on this ticket. Use the step id written in backticks in the playbook, such as `account-lockout-source-check`.

Look up only what could change your decision, and stop once the evidence is clear. You have at most {max_lookups} lookups. Then call `record_decision`.

Each lookup's reply starts with its step id, such as `Step s2.` In your decision, list in `evidence` the ids of the steps your decision rests on. Cite only steps that ran: a citation of a step that didn't happen is dropped.

When you escalate, code writes the handover's facts: the requester, device, priority, SLA, the checks you ran and what came back, similar incidents and what's still unknown. You write only three things: the likely cause and the evidence for it in `rationale`, what your lookups ruled out in `ruled_out`, and the first thing the receiving team should do in `next_step`.

A check with no recorded result wasn't run: it tells you nothing, and it hasn't passed. The remediation tools aren't lookups. To use one, propose it in your decision, and a person approves it first.
