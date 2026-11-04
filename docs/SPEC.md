# TriagePilot: the L1 triage pilot

From the head of service delivery at Sihlwerk IT AG.

## How support works today

We run IT for small and mid-size companies around Zürich. Our first client on this pilot is Limmatica AG, a financial services firm with about 850 staff. Its environment is described in our knowledge base, starting with `company-profile.md`.

One L1 technician covers several client sites. For each ticket they read the request, work out which known issue it is, look up the playbook, and then fix it remotely, send the user steps, or pass it on to the right team. Most tickets are routine and well documented. The fix is rarely hard. The wait for a technician, and often the trip to site, is what costs our clients time and us money.

## The pilot

We want an agent, TriagePilot, to do the first pass on a ticket the way a good L1 technician does. For each ticket it should:

- look up the relevant playbooks and policies in the client's knowledge base
- choose exactly one path:
  - **SELF_SERVE**: the fix is documented, safe and simple, so the user gets numbered steps
  - **AUTO_FIX**: the fix is documented, safe and reversible, so the agent proposes one of our remediation tools with its parameters
  - **ESCALATE**: information is missing, the issue sits with infrastructure, hardware, identity or security, or the knowledge base does not support a confident fix, so the agent drafts a ticket for the right queue with a priority
  - **OUT_OF_SCOPE**: the request has nothing to do with workplace technology
- explain its diagnosis in a few sentences, grounded in what it retrieved, and end with the path and the main reason

Our goal is to resolve routine tickets remotely, before anyone travels, and to hand the rest to the right team with a write-up they do not need to redo.

## What our technicians need to see

- The ticket text, and a few example tickets to try.
- What the agent retrieved: each knowledge base unit, its similarity score, and the lines that matched.
- The path it chose, its reasoning, and the action it proposes.
- A confirmation card before any fix runs or any ticket is created.
- After a self-serve answer, a way to say it worked, or that it did not and should go to a technician.
- Live statistics from real use: tickets by path, the share resolved without a technician, response times.
- A Scoreboard with the results of our evaluations.
- A switch that turns retrieval off, so we can show what the agent does without our knowledge base.

## Rules

- No fix runs without a technician's confirmation. The system must block it, even if the agent calls the tool directly.
- No escalation ticket is created without a technician's confirmation.
- When a technician declines a proposed fix, the issue does not just disappear: they get a ticket pre-filled from the agent's diagnosis, with no new model call.
- When self-serve steps do not work, the user's issue goes to the same ticket confirmation.
- The agent never asks the user a question. If missing information changes the path, it escalates and says what is missing.
- Requests for access, permissions or admin rights are IT requests. They are escalated, never declined as out of scope.
- Policy SEC-04 §4.2: two or more lockouts in 24 hours are a possible compromise. Never a routine unlock. They go to `SEC-INCIDENT`.
- Tool parameters are always concrete values. An unknown user is `current.user`, an unknown device is `current.device`.
- With retrieval off, the agent gets no tools and chooses no path. It gives general, hedged advice only.
- Every finished run is recorded in the usage log. Evaluation runs are not.
- No secrets or real client data in the repository.

## Our records

- `data/kb/`: Limmatica's knowledge base, 11 single-issue playbooks and the company profile, which is split by section.
- `logs.csv`: real usage from the app, one row per finished run. It is not in git.
- `data/records/`: invented records of Limmatica's users, their devices and recent lockouts. The agent doesn't use them yet.
- `data/evals/`: two labelled sets of 25 tickets. The agent never sees the answers.

## Not for now

- Real integrations. Every tool is simulated and says so in its result.
- More than one client.
- Conversations or follow-up questions. One ticket, one pass.
- A ticket queue or batch processing. A technician works one ticket at a time.
- German. The knowledge base and the agent's instructions are in English.
- Sign-in. Everyone who opens the app sees everything.
