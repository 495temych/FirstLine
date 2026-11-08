# Data

How we use the original dataset. Its source and licence are in `tickets/SOURCE.md`. All of it is synthetic.

## One rule

The agent sees only what a technician would see when a ticket arrives. Everything found out later is an answer, and the agent never reads it.

## The sets

There are 795 tickets: 745 imported and 50 hand-written. Each group has one job.

| Set | Tickets | Job | When we use it |
|---|---|---|---|
| `kb` | 384 | Raw material for the playbooks | Only when writing them. Never a test |
| `dev` | 129 | Practice test | Any time, and we can tune on it |
| `held_out` | 128 | Final exam | Once, at sprint review |
| `unseen_dev` | 52 | Practice on families with no playbook (`CES`, `AIT`) | Any time, and we can tune on it |
| `unseen_held_out` | 52 | Final exam for the same | Once, at sprint review |
| `rules` | 25 | Hand-written short tickets and policy traps | Any time |
| `rules_held_out` | 25 | Final exam for the same | Once, at sprint review |

The Tickets tab shows `rules`, `dev` and `unseen_dev`, which makes 206 tickets. Held-out tickets stay out of the app.

## Where each thing lives

| File | What it holds | Does the agent see it? |
|---|---|---|
| `tickets/tickets.json` | Each imported ticket as it arrived: title, description, priority, SLA plan, environment, applications and requester | Yes |
| `tickets/splits.json` | Which ticket belongs to which set | No |
| `records/users.json` | Staff records, with invented devices, groups and lockouts | From commit 6 |
| `kb/` | Playbooks, policies, queues and the company profile | Yes, through retrieval |
| `evals/incidents.json` | What really happened: correspondence, diagnostics, root cause and resolution | Never |
| `evals/causes.json` | The named causes, with what a good first pass does for each | Never |
| `evals/cause_labels.json` | Each imported ticket's cause and expected answer. Generated, so don't edit it | Never |
| `evals/families.json` | Each issue family and its playbook | Never |
| `evals/rules_*.json` | The hand-written tickets and their answers | The tickets only |
| `evals/retrieval/` | Saved retrieval scores | Never |
| Langfuse datasets `firstline-rules`, `firstline-dev`, `firstline-unseen_dev` | Copies of the practice sets, with personal details masked. Git stays the source of truth | No |
| `evals/runs/` | Saved agent runs, each with its decisions, so `--rescore` can mark them again for free. The baseline runs of each practice set are committed, and trial runs stay out of git | Never |

## How a ticket gets its answer

We don't label tickets one by one. A person reviews the causes, and each ticket inherits its answer from its cause.

```text
incidents.json: root_cause
  → rules in causes.json name one cause
  → cause_labels.json: expected path, tool or queue, and checks
```

A ticket takes the cause its root cause names first. SEC-04 then overrides lockout tickets, using the requester's record. Rules were written on the `kb` set only, and held-out tickets are labelled unread.

To change an answer, edit `evals/causes.json`, then run:

```bash
uv run -m evals.label_tickets
```

## What each part of the dataset is for

| Job | What it gives us | Where it comes from |
|---|---|---|
| Knowledge | Playbooks | The `kb` set only |
| Evaluation | Scores on tickets the agent hasn't seen | The development, held-out and unseen sets |
| Simulator | Checks that return recorded results, from Sprint 1 commit 7 | `diagnostics` |
| Privacy test | A score for redaction, from Sprint 2 | The source's `pii.json` and `retention.json` |

We don't train a model on it, except the classifier that serves as a yardstick.

## Don't

- Don't write a playbook from any set but `kb`.
- Don't open a held-out set when changing the instructions.
- Don't give the agent an answer file.
- Don't edit `tickets/`, `evals/incidents.json` or `records/users.json` by hand. `uv run -m evals.import_tickets` rebuilds them.
