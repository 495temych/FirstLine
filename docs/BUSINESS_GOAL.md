# Business goal

What FirstLine has to achieve for CorpLabs, how we count the money, what we compare it with, and how we decide whether it worked. `docs/SPEC.md` says what to build, and `docs/ROADMAP.md` says when.

CorpLabs is fictional and its tickets are synthetic, so every number here is either measured on that data or an assumption, and each is labelled.

## The goal

**Every ticket gets a correct first pass before a technician touches it.**

It's worth doing if technician time saved, in Swiss francs, is well above what the system costs, and nothing unsafe happens.

## The problem

The service desk takes every IT request first. A technician reads the ticket, works out which known issue it is, runs the usual checks, then fixes it, sends steps, or hands it to another team. The fix is rarely hard. The time goes on three things:

- **Waiting** for a technician to pick the ticket up.
- **Repeating** the same checks. Every ticket in the 12 known families follows the same three checks for its family.
- **Redoing work after a handover**, when the next team can't see what was already found.

In the knowledge base split, all failing checks belong to L1 or the user on 38% of tickets. That's the source of the "about a third" in the spec. The other tickets need another team, so closing tickets can't be the only measure.

## The three outcomes

| Outcome | Tickets | Measure | What it's worth |
|---|---|---|---|
| Routine tickets close with one approval | About a third | Share a technician approves unchanged, by family | Automation: the first pass and the fix take minutes |
| Other tickets reach the right team first time, already investigated | About two thirds | Right team first time, and required checks in the handover | Acceleration: no bounced tickets, and no repeated checks |
| Nothing unsafe happens | All | Zero rule breaks | The condition for all the rest |

We don't aim to replace technicians, remove the human approval, or maximise the share of tickets the agent touches. A correct "this needs a person" is a good result.

## How we count money

The headline is **net saving per ticket, in CHF**. It compares the same first pass with and without FirstLine.

```text
minutes saved  = (share approved × minutes by hand) − minutes to review
net saving     = minutes saved × rate per minute − model cost − cost of mistakes
```

Every ticket costs a review. A ticket the technician rejects also costs the full first pass by hand, which is the cautious case, because a correction is often quicker than starting again.

| Input | Value | Status |
|---|---|---|
| First pass by hand | 15 minutes | Assumption. The records have no handling times. The first and last messages on a ticket are a median of 14 minutes apart, which is a rough check at best |
| Review of one decision | 2 minutes | Assumption, to be replaced by real review times in Sprint 2 |
| Technician rate | CHF 60 an hour | Assumption, for the owner to change |
| Share approved unchanged | 68% on the development set | Measured against the labels at the baseline, so it's a stand-in until real reviews replace it |
| Model cost | About CHF 0.005 per ticket | Measured on 206 tickets with Haiku and one call. The loop's limit starts at CHF 0.10 |
| Routine fix on a possible compromise | CHF 2,000 | Assumption, and it dominates the total |
| Wrong fix, needless escalation, or a real request declined | CHF 120 | Assumption: 2 hours at CHF 60 |
| Right path, wrong tool or queue | CHF 60 | Assumption: 1 hour at CHF 60 |
| Volume | About 1,500 tickets a year | From the dataset: 745 in six months. It's a sample, so a client's real volume replaces it |

**Break-even.** With these numbers, FirstLine saves time once a technician approves more than 13% of decisions (2 ÷ 15). Below that, reviewing costs more than it saves.

**Illustration, before mistakes.** Today's first passes cost about CHF 22,500 a year.

| Share approved unchanged | Minutes saved per ticket | Saved per year |
|---|---|---|
| 50% | 5.5 | CHF 8,250 |
| 70% | 8.5 | CHF 12,750 |
| 80% | 10 | CHF 15,000 |
| 90% | 11.5 | CHF 17,250 |

**The same 70%, if an assumption moves.**

| Change | Saved per year |
|---|---|
| A review takes 4 minutes | CHF 9,750 |
| A first pass by hand takes 10 minutes | CHF 7,500 |
| A technician costs CHF 80 an hour | CHF 17,000 |

What this tells us:

- **The model is the smallest cost.** Even at the CHF 0.10 limit, a year of tickets costs CHF 150. So we choose the model on accuracy first, then on the cost of the whole task.
- **One bad mistake is expensive.** A single routine unlock on a possible compromise wipes out about 235 tickets of savings at 70%, which is nearly two months. That's why safety is a gate at zero, not part of an average.
- **Hosting may matter more than tokens.** At this volume, the Azure, API Management, Qdrant, Supabase and Langfuse bills could use up a real share of the saving. They're unpriced until Sprint 3, and the handover must include them.

Left out, so the figure stays cautious: the receiving team's time, users' waiting time, and tickets the Assistant stops before they're raised. Each gets reported on its own once there's data. The cost of building FirstLine is left out too.

## The baselines

We compare against something at each level, and "better than nothing" doesn't count.

| Baseline | What it answers | Status |
|---|---|---|
| Today's process | Does it save technician time? | The 15-minute assumption, until a client's real numbers replace it |
| Always the most common answer | Is the agent better than a constant? | Measured in commit 5. The agent beats it everywhere |
| A simple classifier, trained on the knowledge base split | Is it better than a free, cheap model on routing? | Measured in commit 5. It beats the agent on the templated development tickets and loses on short requests and unseen teams. It's a yardstick and never decides a ticket |
| One model call | Does investigating add more than it costs? | The Assistant today, compared with the loop in commit 7 |
| Retrieval before the playbooks | Did the knowledge base get better? | Measured: hit rate 94%, false matches 96%. Now 100% and 4% |

The first agent baseline is in the README's "Results". It rests on labels the owner hasn't finished reading, so it's run again once they are confirmed.

## How we evaluate

No single number is enough, so we use a portfolio, from cheap and precise to noisy and close to the business.

| Level | Question | Main measures | Kind of eval |
|---|---|---|---|
| Retrieval | Did it find the right playbook? | Hit rate, reciprocal rank, recall, false matches on unknown families | Direct, free, on every commit |
| Decision | Was the first pass right? | Path, tool or queue, right team first time, precision and recall per path, Cohen's kappa, mistake cost | Direct, against labels |
| Diagnosis | Did it find the cause? | Named cause, and the grade of the write-up | Direct, and a judge checked against human grades |
| Investigation | Did it work like a good technician? | Required checks run, needless checks, evidence that exists | Direct, from tool results |
| Safety | Did any rule break? | Fixes without confirmation, routine unlocks under SEC-04, hidden instructions obeyed | Direct, and each must be zero |
| Privacy | Did personal data escape? | Values left in prompts, traces or logs, and terms wrongly removed | Direct |
| Operations | Would it hold up? | Cost and time per ticket, batch time, failures, recovery after a killed run | Direct |
| Business | Was it worth it? | Share approved unchanged, right team first time, net saving in CHF | Human review |

**The data.** Tickets are split by family: 60% for the knowledge base, 20% for development and 20% held out. `CES` and `AIT` stay out of the knowledge base entirely, to test whether the agent knows what it doesn't know. The agent sees only what a technician would see on arrival. The held-out and `unseen_held_out` sets run once, at sprint review. Our 50 hand-written tickets test the rules and short, vague requests.

**Reading the results honestly.**

- Scores carry a margin of error. At 80% on 129 tickets, that's about ±7 points, so a small gain is noise. Model runs are repeated, and a change counts only if it beats the noise.
- A proper test needs 1,000 or more cases, and we have 361 outside the knowledge base. These sets can show big differences, not small ones.
- The tickets are synthetic and alike, so development scores flatter us. Unseen families, short requests and hidden instructions are the honest tests.
- A change is kept when one measure improves by more than the noise and nothing gets much worse. Safety and privacy can't get worse at all.

## Success criteria

The course says to agree these at the start and measure them at handover. The first table is fixed. The second is for the owner to confirm once the baseline exists.

**Fixed: each one blocks a release**

| Criterion | Target |
|---|---|
| Fixes or tickets created without confirmation | 0 |
| Routine unlocks on a possible compromise | 0 |
| Hidden instructions obeyed | 0 |
| Personal data in prompts, traces or logs, in the Queue | 0 |
| Beats both yardsticks on decisions, by more than the noise | Yes |
| Net saving per ticket, after mistakes and model cost | Above zero |

**Proposed: floors to set from the baseline**

| Criterion | Starting proposal |
|---|---|
| Share approved unchanged | 70%, or well above the 13% break-even |
| Right team first time | Beats the classifier, and at least 85% |
| Required checks in the handover | At least 90% |
| Unknown families escalated rather than given a fix | At least 95% |
| Queue model cost per ticket | Under CHF 0.10 |

## What the tools are for

The tools are where the money comes from, and each kind has a different risk. Today, all 17 are simulated, and the Queue doesn't exist yet.

| Kind | What it does | Who runs it | Value |
|---|---|---|---|
| Read | Look up the requester and device, search playbooks and past incidents, run a check | The agent, automatically | Removes repeated checks |
| Handover | Create the escalation ticket with its evidence | Proposed by the agent, confirmed by a person | Removes redone work |
| Fix | Change a system, within one user or device where possible | Proposed by the agent, approved by a person | Closes routine tickets |

**Read tools are safe to automate**, because they change nothing. They do need the same care with personal data, and ticket text can never choose what they read. Real versions would call Active Directory logs, Microsoft Graph for Intune, PaperCut and GlobalProtect.

**A loop has to earn its cost.** Every family has three checks, always the same ones, so investigating may add little. Commit 7 tries the loop against one call on samples first, and keeps it only if it wins by more than the noise.

**The handover needs more than it has.** `create_escalation_ticket` takes a queue, a priority and one sentence today, which can't deliver the second outcome. From commit 7, code fills in everything it already knows, and the model writes only what needs judgement.

| Part of the handover | Filled in by |
|---|---|
| Requester, device, priority, SLA deadline and affected applications | Code, from the records |
| Checks run, with results and evidence | Code, from tool results, so nothing can be invented |
| Similar past incidents and how they ended | Code, from search |
| What's still unknown, including checks that couldn't run | Code |
| Likely cause, what's ruled out, and the suggested next step | The model, citing the evidence above |
| Queue | The model, and rules in code can overrule it |

**A fix is more than a tool call.** From Sprint 2, each one follows the same steps:

1. A check shows the fault, and code confirms that the rules allow this fix for this user.
2. A person sees the proposed fix, with its evidence and parameters, and approves it.
3. It runs in its own step, once, with a key that stops it running twice.
4. The check that failed runs again. If it passes, the ticket closes. If not, it escalates with both results.
5. All of it goes in the audit trail.

In production, each fix would be a narrow runbook under a managed identity that can do only that job. The records hold no results from after a fix, so step 4 can only be simulated here, and the demo must say so.

**Autonomy is earned one action at a time.** Nothing that changes a system runs without a person today. The spec keeps it that way for this pilot, and Sprint 3 records a level for each action.

| Stage | What happens | To move on |
|---|---|---|
| Shadow | The agent decides on real tickets, and nothing happens | Decisions match technicians on the measures above |
| Approve each | A technician approves each decision | The family meets its floors |
| Approve in bulk | A technician approves a reviewed list | High approval, with no sign of rubber-stamping |
| Automatic | One routine fix runs alone, with a report and spot checks | Long clean record, and a person can stop it at once |

A fix can only go past bulk approval if it's routine, limited to one user or device, reversible, and checkable afterwards. Device compliance looks like the best first candidate: the service desk owns 24 of its 25 tickets with a failing check, and `force_intune_sync` changes very little. The Sprint 1 numbers decide, and the handover names it. Unlocks, group changes, and anything under SEC-04 stay with a person.

## Risks to the business case

| Risk | Why it matters | Response |
|---|---|---|
| The assumed minutes are wrong | The saving rests on them | Real review times in Sprint 2, and the sensitivity table above |
| Rubber-stamping | Technicians approve everything, so the approval stops protecting anyone | Track time per review and rejection rates, and seed known errors into review lists |
| Synthetic data | Real tickets are messier, so scores will fall | Honest tests now, and shadow mode before anything else at a client |
| Unknown issues | Confident wrong answers cost more than escalations | False match rate, unseen families, and a playbook needed for any fix |
| Prompt injection | Tickets are untrusted, and records are private | Read-only Queue tools, a person before anything leaves, and guardrails |
| Knowledge base goes stale | Wrong playbooks give confident wrong fixes | Owner and review date on each playbook, and a process at handover |

**If it doesn't work out.** Plan B is to keep the Queue as a triage and handover tool, with fixes left to technicians, which still delivers the second outcome. Plan C, if a client won't send data to a model provider, is a local model.

## Who decides

| Moment | What's decided |
|---|---|
| Labels, commit 4 | Frozen after the owner's review of the open decisions and two disputed causes |
| End of Sprint 1 | Does it beat the yardsticks? Which model and design? |
| End of Sprint 2 | Do the review times confirm the saving? Does the Queue hold up? |
| End of Sprint 3 | Could a client run it without us, and do the numbers beat the Sprint 1 baseline? |

A person is always accountable for what the agent does. Each of the six pillars (safety, fairness, security, privacy, transparency and accountability) gets a named owner in Sprint 3.
