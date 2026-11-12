# Roadmap

FirstLine gives every IT ticket a correct first pass before a technician touches it: **proven with evals, enforced in code, traced end to end, and running on Azure.** CorpLabs AG, a fictional company in Zürich, is the client.

It's a portfolio project for Swiss employers, and the story is the method, not the domain: someone who worked in L1 support shows how they now put AI into a business process. IT tickets are the example. The same steps would carry over to invoices, claims or HR requests.

## The four promises

Every commit makes one of these visible in the demo. They're the questions a client asks before buying AI.

| Promise | The client's question | What the demo shows | Tools |
|---|---|---|---|
| **Proven** | Is it better than what we have, and what does it cost? | The Scoreboard: the agent against two free yardsticks, in CHF, with margins of error | Evals in code, Langfuse experiments |
| **Safe** | Can it do something dangerous? | The agent proposes, code enforces, and a person approves. A risky unlock is blocked even when the model asks for it | LangGraph gates, rules in code, Content Safety |
| **Observable** | Can we see why it decided? | Any decision opens as a trace: what it read, checked, proposed and what a person did | Langfuse |
| **Shippable** | Can it run in our cloud, within budget? | A live URL on Azure, with no keys in the app and a token budget at the gateway | Container Apps, Key Vault, managed identity, API Management, Microsoft Foundry |

`docs/BUSINESS_GOAL.md` holds the money, the baselines and the success criteria.

## Two modes

- **The Assistant** is the front door. An employee describes a problem and gets an answer while they wait. Routine fixes need their confirmation, and anything touching access or security becomes a ticket.
- **The Queue** is the core. A technician's morning batch, pre-triaged by an agent that investigates with read-only tools. The technician approves, corrects or rejects each decision, with its evidence beside it.

## The method

The demo walks through six steps, each with proof in this repository.

1. **Frame the money.** Minutes saved, review time, mistake costs and break-even, in francs.
2. **Define the exam.** Labelled tickets, a held-out set opened once, and two free yardsticks to beat.
3. **Build the baseline.** One model call with a structured decision, before anything clever.
4. **Enforce rules in code.** The model proposes. Code and people decide what runs.
5. **Experiment.** Change one thing, measure it against cost and noise, and write down the decision.
6. **Ship and watch.** Trace every decision, cap the spend, and hand it over.

## The dataset is a means, not the subject

The 745 synthetic incidents give us knowledge, an exam and recorded check results. The labels are frozen: drafted by rules from each incident's root cause, with the owner's seven decisions and the two causes the agent disputed most reviewed by hand. We don't dig further into the data's quirks. The README says plainly that the tickets are synthetic and the labels approximate.

We tune on the development tickets, as a support team learns from its own history. Rigor goes where a reader would notice it: margins of error, the yardsticks and mistakes priced in CHF. The held-out sets are one check at the end, mentioned once on the Scoreboard rather than beside every number.

## The three sprints

Each sprint is one phase of `docs/FRAMEWORK.md`, the reusable framework this roadmap follows, and one course week.

| Sprint | Phase | Question it answers | Where it runs | Done when |
|---|---|---|---|---|
| 1. Prove it | Feasibility: the use case, the money, the data, the core, the budget, and the design and model | Is triage worth automating, with which design and model, at what cost? | Your Mac, with model APIs | A go decision, with the chosen design and model and the cost per ticket |
| 2. Make it a system | Integrate and extend: traces, a system of record, search, MCP tools, a conversation, and the dashboard | Can it run a whole queue, observed, durable and usable? | Your Mac, with Langfuse, Qdrant and Supabase | The Queue works end to end, every ticket traced, with measured review times |
| 3. Deliver it | Production: security, the cloud, cost control and handover | Could a client run it safely in their own cloud? | Microsoft Azure | A hosted demo, a handover pack and a 3-minute video |

### What each service is for

Each store has one job, so nothing has two sources of truth.

| Place | Tool | What it holds | Source of truth? |
|---|---|---|---|
| Context layer | `data/kb/` in git | Playbooks and policies, with owner and review date | Yes |
| Search index | Qdrant | Embedded knowledge base sections and past incidents | No, it can be rebuilt from git |
| System of record | Supabase | Tickets, batches, decisions, reviews, the audit trail and checkpoints | Yes |
| Observability | Langfuse | Traces, datasets, experiments and scores | Yes for traces, no for labels, which stay in git |
| Model and safety layer | Microsoft Foundry | Claude and other models, and Content Safety Prompt Shields | No, it holds no data of ours |
| Gateway | Azure API Management | Keys, rate limits, token budgets and logs | No, it holds rules, not data |

### Where MCP fits

MCP is how the agent's read-only tools get served, not a way into our stores.

- **The agent, with Sprint 2's commit 12.** The investigation tools (search the knowledge base, look up the requester, find similar incidents, run a check) start as plain read-only functions in Sprint 1's commit 7, where the loop is measured. Commit 12 serves them from FirstLine's own small MCP server, read-only by construction, and the loop finds them through MCP instead of hardcoded schemas, which closes that known limitation. Similar incidents come from Qdrant's `incidents` collection, from Sprint 2's commit 2.
- **Not the vendors' servers, for the agent.** Supabase's MCP server can run any SQL and apply migrations, and Qdrant's can write. Both are wider than least privilege allows.
- **Development, now.** Supabase's MCP server in read-only mode, scoped to this project, lets Claude Code inspect the system of record while we build. It's local configuration only, with nothing in the product.
- **Sprint 3.** API Management can front the MCP server, with the same keys, limits and logs as the model calls.

### Spending

The owner pays for every call, so `docs/PROCESS.md` sets the rules: ask before any run over CHF 1, re-score instead of re-running, practise on samples, and run held-out sets once. The whole plan should cost about CHF 5 in model calls, plus Azure, which is torn down between demos.

## Sprint 1: prove it

**Phase 1, feasibility on one machine: define the use case and its money, build the exam and the core, estimate the budget, and choose the design and model with evidence.** Week 1 in one line: start from a business problem you can measure, and test the agent on your own task against a simple baseline.

| # | Commit | Demo moment |
|---|---|---|
| 1 | ✅ **Tickets.** Import the 745 incidents, split them, and score retrieval for free | A "before" retrieval score |
| 2 | ✅ **CorpLabs.** Company, policies, queues, tools and staff records | The Assistant answers as CorpLabs |
| 3 | ✅ **Playbooks.** 15 playbooks on one template, with section retrieval | Retrieval hit rate from 94% to 100%, false matches from 96% to 4% |
| 4 | ✅ **Labels.** Named causes drafted by rules, then frozen after the owner's review | Each ticket's cause and expected path on the Tickets page |
| 5 | ✅ **Baseline.** Structured decisions, scored against two yardsticks, with cost guards | The first real numbers, including where the agent loses |
| 6 | ✅ **Rules in code.** Requester records, tool risk tiers and the SEC-04 guard | Pick a user: the same lockout gets a different answer, and the dangerous unlock can't run |
| 7a | ✅ **The loop.** Recorded check results, four read-only lookup tools and an agent loop with limits, built and tested with a stub model, so it costs nothing | A stub-driven ticket shows each lookup it made, and the loop can't reach a fix |
| 7c | ✅ **The Assistant as a conversation.** *(Built before 7b, by the owner's choice on 12 November.)* The Assistant becomes a chat: the request, a live checklist of the agent's steps, and the decision and its gate as cards in the thread. It runs the loop, while the Queue and evaluations stay on one call until 7b measures it | Watch the agent search, look up the requester and run a check, step by step, before it proposes anything |
| 7d | ✅ **A work tool's look.** *(By the owner's choice on 12 November, before 7b.)* Every page gets one frame: a sidebar, a top bar and a page header with its one-sentence answer. The Assistant becomes a chat with the message box at the bottom and the ticket's details on the right, the Queue a Jira-style board and Tickets a list. A new `docs/BRAND.md` sets the system | The same product, but it looks like the tool a service desk would use, and the agent's work is the first thing you see |
| 7b | **Investigate, measured.** The loop writes a full handover and cites its evidence, and runs against today's one call on the samples, with the default model, by a rule written before the run | What investigating adds, for what extra cost, on one chart |
| 8 | **Benchmark.** Ten light models, Claude, OpenAI and open-weight, on the full development, unseen and rules sets. Ranked by net saving per ticket, with the Pareto front drawn | Net saving against cost per ticket, with the front, on the Scoreboard, and a written choice |
| 9 ✅ | **The business case.** "Is it worth it?" in CHF: projected from the evaluations, observed from the Queue's reviews, and how it moves if the assumptions are wrong. *(Built in Sprint 2 as its commit 8, and moved here, because the budget is a feasibility question)* | Change the minutes by hand and watch the saving and break-even move |

### Success criteria

The number after each one is the commit that meets it.

**Data (`data/`)**

- [x] (1) `data/tickets/tickets.json` holds only what's known at submission. `data/evals/incidents.json` holds `root_cause`, `resolution`, `correspondence` and the `diagnostics` summary.
- [x] (1) `data/tickets/splits.json` is fixed and repeatable: `CES` and `AIT` are unseen families, halved so one half can be tuned against, and the other 12 are split 60/20/20 by family.
- [x] (1) The source, its MIT licence and the fact that it's synthetic are in `data/tickets/SOURCE.md`. The import can be re-run.
- [x] (2) `data/records/users.json` holds the 628 directory accounts, plus the 20 rules-set users, with invented devices, groups and lockouts. All 745 tickets link to a requester's record.
- [x] (4) Each ticket has one named cause, and each cause has accepted paths, tools, queues and required checks. The labels are frozen after the owner's review of the open decisions and of the two causes the agent disputed most.
- [x] (4) Our 50 tickets are moved to CorpLabs queues and renamed the rules set, with no `review` flag left.
- [x] (7a) `data/tickets/checks.json` holds each imported ticket's checks by playbook step: the action, what healthy looks like, what was observed and whether it passed. It's built by a script from `data/evals/incidents.json`, and a test proves no `diagnostics` summary, `root_cause`, `resolution` or `correspondence` text is in it. Rules-set tickets have no checks.

**Knowledge base (`data/kb/`)**

- [x] (2) `company-profile.md`, `policies/` and the escalation queues describe CorpLabs. No file in the repository names the old client or provider, checked by a test.
- [x] (3) The playbooks follow one template, and a test fails on a missing section or field.
- [x] (3) A test proves `CES` and `AIT` have no playbook, and that no held-out or development ticket id appears in `data/kb/`.
- [x] (3) Each error code in a playbook comes from a knowledge base split ticket.

**Retrieval: sentence-transformers (`agent/retrieval.py`)**

- [x] (1) `uv run -m evals --retrieval` scores hit rate and false match rate on any split, with no model calls and in `poe check`.
- [x] (3) Retrieval matches sections, then returns the best playbook and any policy that matched. `agent/retrieval.py` keeps a small interface, so Qdrant can replace its insides in Sprint 2.
- [x] (3) Hit rate reaches 95% on the development set, with a floor in `poe check`, and false matches on `unseen_dev` fall well below 96%. Each attempt is in `docs/DECISIONS.md`.
- [x] (3) The score adds mean reciprocal rank and recall, as well as the hit rate.

**Agent: LangGraph and Claude (`agent/`)**

- [x] (2) Each tool has a risk tier and an owner in `agent/tool_schemas.py`.
- [x] (5) The decision is a Pydantic class, with the rationale first, so the model reasons before it decides.
- [x] (6) `run_triage` takes a requester and a mode, Assistant or Queue, and the model sees only the parts of that user's record a technician would use: username, department, office, floor, device and groups, never the name or email. The lockout count stays with code, for SEC-04. With no requester it behaves as it does today.
- [x] (6) `agent/rules.py` holds pure functions that both modes call, from a new `enforce` node between `triage` and the gates, so the routers stay pure and the rules run before any gate. Each override is kept in state with the rule, its reason and what the agent proposed.
- [x] (6) SEC-04 §4.2: a requester with 2+ lockouts in the records, on a lockout ticket, ends at `SEC-INCIDENT` at P2-High, whatever the model proposed. A ticket counts as a lockout ticket when the model proposed `unlock_ad_account` or search matched the `account-lockout` playbook or the SEC-04 policy, so the model can't talk its way out by naming another cause. A count stated only in the ticket text stays with the model, as `docs/DECISIONS.md` says.
- [x] (6) In the Assistant, a sensitive fix from `agent/tool_schemas.py` becomes a ticket to `DESK-SUPPORT` naming the fix a technician should run. In the Queue a technician confirms every fix anyway, so the tier changes nothing there.
- [x] (6) Stub-model tests try to break each rule. A stub that proposes `unlock_ad_account` for a user with 2 lockouts never reaches `confirm_fix`, and `execute_tool` never runs. A user with 2 lockouts and a printer ticket isn't overridden, nor is a user with 1 lockout. A stub that calls the lockout something else is still overridden.
- [x] (6) An override is saved with its decision in Supabase, through a new migration, and in the memory store the same way.
- [x] (7a) Four read-only tools are plain functions in `agent/lookups.py`, so commit 12 of Sprint 2 can serve them over MCP unchanged: search the knowledge base, look up the requester (with their lockouts and recent tickets), find similar past incidents with how they ended, and run a check by its playbook step id.
- [x] (7a) Code, not the model, decides what a tool may read. A check runs on the ticket being worked, never one the model names, and similar-incident search reads knowledge base split tickets only, with a simple local search until Qdrant's `incidents` collection arrives in Sprint 2. A check the ticket doesn't have returns no result.
- [x] (7a) The loop is a node in the same graph, `investigate`, chosen by a `design` setting, "one call" or "loop". The model may call the four tools and `record_decision` and nothing else, and its decision goes through `enforce` and the same gates.
- [x] (7a) Each step is kept in state: the tool, its input, a short result, time, tokens and cost. The loop stops at its limits, 6 tool calls and CHF 0.01 by default in `agent/config.py`, and escalates to `DESK-SUPPORT` with what it found.
- [x] (7a) Stub-model tests try to break it: a tool that changes a system is never bound and `execute_tool` never runs, a check on another ticket is refused, a model that never decides stops at the limit, and an unreadable tool call fails that step, not the run.
- [x] (7a) The evaluation runner takes `--design loop`, the design is part of a run's version so the repeat guard tells them apart, and the cost estimate before a run assumes the step limit.
- [ ] (7b) An escalation carries a full handover. Code fills in the requester, device, priority, SLA deadline, applications, checks with their evidence, similar incidents and what's unknown. The model writes only the likely cause, what's ruled out and the next step.
- [ ] (7b) The model cites the steps behind its decision by id, and code checks each one exists. A citation of a step that never ran is dropped and counted.

**Evaluations (`evals/`)**

- [x] (5) The runner scores the development set, unseen families and the rules set: path, action, team, named cause, mistake cost in CHF and cost per ticket, each by family.
- [x] (5) Each score sits beside two yardsticks, the most common answer and a simple classifier trained on the knowledge base split, with a confusion matrix, precision and recall per path, and Cohen's kappa.
- [x] (5) Scores show a margin of error, and each run records the versions of the instructions, tools, knowledge base and labels.
- [x] (5) The development set is run and committed, for CHF 0.98 with the rules and unseen sets. Re-scoring, samples, a spending cap and a repeat guard keep later runs cheap.
- [x] (6) Evaluations pass each ticket's requester and run in Queue mode, the core product, so a sensitive fix such as `restart_print_spooler` is still scored as the fix it is. Each scored ticket records whether a rule changed it.
- [x] (6) A safety score counts routine unlocks under SEC-04, which means any fix proposed on a ticket whose answer expects `SEC-INCIDENT`. It is zero on the rules set, whose SEC-04 tickets are T-006, T-007 and T-020, and T-021, with 1 lockout, still expects the routine unlock. Saved runs re-score for free, and the new scores come from rules, `dev` and `unseen_dev` runs with the default model, about CHF 0.55 in all over three versions of the instructions. *(Zero on the rules set and on unseen families. One on development, INC-ALP-0036, is a known limitation in `docs/DECISIONS.md`.)*
- [ ] (7b) Investigation is scored: required checks run, against each cause's labelled checks, needless checks, steps per ticket, and citations that point at a step that ran.
- [ ] (7b) The rule is written in `docs/DECISIONS.md` before the run: keep the loop if its net saving per ticket beats one call's by more than the margin on the samples, with no SEC-04 failure, at under CHF 0.10 a ticket. The samples are 47 tickets, so only a large difference can show.
- [ ] (7b) The loop runs on the samples, `--sample` on `dev` and `unseen_dev` and `--tiny` on the rules set, for about CHF 0.15, stated before it runs. It runs on the full sets only if the rule keeps it, and only after the owner agrees the cost.
- [x] (8) Every model runs through one harness, `agent/models.py`, with the same instructions and the same forced decision tool. Claude goes to Anthropic and OpenAI's models to OpenAI, on their own keys. The rest go through OpenRouter, each pinned to one provider with no fallback, keeping to providers that support the tool call and don't keep prompts. A model whose provider can't force the tool is only offered it, and says so. Tests use a fake model.
- [x] (8) Each run records the model, who served it, where, and at what reasoning effort (the lowest it accepts), the provider's own reported cost where there is one, median and 90th-percentile time per ticket, and invalid decisions, which count as wrong.
- [x] (8) The roster is ten light models with tool calls, checked against OpenRouter's catalogue and each lab's list: Claude Haiku 4.5 and 5.5, GPT-6 Luna, GPT-5 nano and GPT-6.1 Terra, gpt-oss-120b, Gemini 3.1 Flash-Lite and Mistral Small (both on EU endpoints), DeepSeek V4.1 Flash, Qwen 3.7 Flash and GLM 5.3 Flash. A free smoke test and a five-ticket preflight of each passed, for about CHF 0.03.
- [x] (8) Every model but GPT-6.1 Terra runs on all of `dev`, `unseen_dev` and `rules`, 206 tickets, for about CHF 1 in all, after the owner's go-ahead. Haiku 4.5's saved runs are re-scored, not re-run. Terra, the dearest, runs on the sample first, and in full only if it lands on the front.
- [x] (8) Models are ranked by net saving per ticket from `backend/economics.py`, so a security mistake weighs what it costs. `uv run -m backend.benchmark` computes the Pareto front of net saving against cost per ticket, and against median time, and marks each model on it or beaten. The two yardsticks sit beside them as the bar to clear, off the front. Balanced accuracy shows whether a model just escalates everything.
- [x] (8) The rule is written before the runs: the cheapest model on the front whose net saving is within the margin of the best, with no security mistake on the rules set. The choice is in `docs/DECISIONS.md`, becomes the default model, and How it works shows it as the model's reason. *(The result is recorded. The rule picks Qwen 3.7 Flash, whose invalid answers and unconfirmed region the rule didn't cover, so the default waited for the owner. On 10 November the owner chose Gemini 3.1 Flash-Lite.)*
- [ ] (8) The held-out sets run once, at sprint review, with the chosen design and model.

**API and dashboard (`backend/`, `dashboard/`)**

- [x] (1) The Scoreboard shows retrieval scores.
- [x] (4) Tickets shows family, named cause and expected path, with a filter for each.
- [x] (5) Tickets and evaluations return the new labels and measures. Held-out tickets stay out of every route, checked by a test.
- [x] (5) The Assistant, and a Scoreboard with measures by family, the yardsticks, CHF for mistakes and a confusion heatmap.
- [x] (6) Starting a triage takes a requester, which the API requires and checks against the records. A picker sits on the Assistant, with the rules-set users first and each one's lockouts and device beside their name. The page shows when a rule changed the agent's decision: the rule, its reason, what the agent proposed and the code that enforces it.
- [x] (6) A browser test with the stub model: "I'm locked out of my account" from `m.huber` (1 lockout) becomes a `DESK-SUPPORT` ticket for a technician to unlock, because an unlock is sensitive, and from `s.keller` (2 lockouts) a `SEC-INCIDENT` ticket, marked as changed by SEC-04.
- [x] (6) Workflow and Harness draw the `enforce` node and list the rules from `agent/rules.py`, each with the code that enforces it, and a test fails when a rule has no explanation. The "Who enforces each rule" table in `docs/STATUS.md` moves SEC-04 from the records and the Assistant's risk tiers to code.
- [ ] (7b) The Models view shows the loop beside the one-call run: net saving against cost per ticket on one chart, with checks run and steps per ticket in the table.
- [x] (7c) The Assistant is a conversation. The requester's message is a bubble, and the agent's reply holds a checklist of its steps that fills in as they happen: search, each lookup and check, the rules, then the decision. Each step shows what it found, its time and cost, and opens to show the tool's input and output.
- [x] (7c) The gate is a card in the thread, in amber, and the answer to it and what ran follow as messages. A rule that changed the decision is a step of its own. Nothing about the gates changes: the same API answers the same gates.
- [x] (7c) The run starts in the background and the page reads its steps every second from `GET /api/runs/{id}`, as the Queue board does, so a reload finds the same thread. Each Assistant run is still one ticket. Asking a follow-up is Sprint 2's commit 12, and a new message starts a new ticket.
- [x] (7c) The Assistant runs the loop, in Assistant mode, set by `ASSISTANT_DESIGN` in `agent/config.py`, before 7b has measured it. The Queue and evaluations stay on one call until 7b decides. With one call, the checklist shows its stations: search, the model's decision and the rules.
- [x] (7c) Example tickets include real development tickets with their requester, so a check has a recorded result to read. A typed request has none, and says so. Held-out tickets are never offered.
- [x] (7c) `docs/SPEC.md`'s Assistant section says what it now does. How long a ticket takes, the median and 90th percentile, waits for real Assistant runs, because 7c makes no paid run.
- [x] (7c) Browser tests with a stub model: the steps appear in order, a lockout from `s.keller` shows SEC-04 as a step, a gate card waits and a reload keeps the thread. It works at phone width and from the keyboard, the checklist is a list a screen reader can read, and `prefers-reduced-motion` stops its animation. A design pass with the frontend-design skill checks it against `docs/BRAND.md`.
- [x] (7d) `docs/BRAND.md` sets the new system: tokens, type, shape, layout, components and motion, and `docs/EXPLAINABILITY.md` points to it. Every colour in `dashboard/src/styles.css` is a token on `:root`.
- [x] (7d) Every page has a sidebar with the three groups and their views, a top bar with where you are, and a page header with its title and one-sentence answer. Every view keeps its link, such as `?view=models`. At phone width the sidebar folds into a menu.
- [x] (7d) The Assistant is a conversation: the message box sits at the bottom of the thread, or in the middle of the page before the first message, with who's asking and the knowledge base switch inside it and example tickets beside it. The ticket's details, its status, path, cause, queue or fix, rule, requester, model, time and cost, sit in a panel on the right.
- [x] (7d) The Queue is a board of compact cards with the ticket id, priority, path label and requester, and Tickets is a list with its filters on top. The explaining pages, Money, Models, Workflow, Harness, Retrieval and Evaluations, take the same header, panels and labels.
- [x] (7d) Nothing about what the pages show or do changes, and no model is called. Unit and browser tests pass, it works at phone width and from the keyboard, and `prefers-reduced-motion` stops the motion. A design pass with the frontend-design skill checks each page against `docs/BRAND.md`, with screenshots on desktop and at phone width.
- [x] (8) A "Models" section on the Scoreboard, under the business case, plots net saving against cost per ticket on a log scale, with the Pareto front drawn and a switch to time per ticket. A table lists each model's accuracy with its margin, mistakes in CHF, cost, median and 90th-percentile time, invalid answers and where its provider hosts it.

**The business case (`backend/`, `dashboard/`)**

- [x] (9) The Queue keeps what a technician needs to trust the batch: states, approved unchanged, agent time per ticket and model cost. Net saving and time saved move to the Scoreboard.
- [x] (9) One module in `backend/` computes the economics from `docs/BUSINESS_GOAL.md`'s assumptions, and both the API and the tests use it. Nothing is computed twice.
- [x] (9) The Scoreboard opens with net saving per ticket in CHF, in three layers. Projected: from the latest evaluation, with accuracy, mistakes priced from the labels, the share technicians catch, and model cost. Observed: from the Queue's reviews, where review time and the share caught are measured, and an approved decision the labels say is wrong is priced as a mistake. Sensitivity: sliders for minutes by hand, the hourly rate and the share caught move the saving, and a chart shows where it turns positive.
- [x] (9) Each figure follows `docs/EXPLAINABILITY.md`: its question, n, margin and source, and the assumptions on the page. One line says the numbers come from practice tickets and the held-out sets run once at the end.
- [x] (9) The benchmark of commit 8 sits under the business case, with its Pareto front.

**Checks and CI**

- [ ] (all) `uv run poe check` passes on every commit, with the coverage thresholds unchanged and no API key.
- [ ] (all) New dependencies are in `docs/TECH_STACK.md` in the commit that adds them. Commit 8 adds `langchain-openai` and needs `OPENROUTER_API_KEY`. Local models through Ollama and a shorter prompt are later experiments, not part of it.

## Sprint 2: make it a system

**Phase 2, integrate and extend: traces, a system of record and search as services, the agent's tools over MCP, a conversation in the Assistant, and a dashboard that explains it.** Week 2 in one line: keep logic in code, measure everything, and make long work durable.

| # | Commit | Demo moment | Course idea |
|---|---|---|---|
| 1 | ✅ **Langfuse.** One trace per ticket, tagged runs and scores on traces, with personal data redacted before anything leaves the Mac | Click a decision and follow it, with no names in the trace | Traces, experiments, sending only what the task needs |
| 2 | **Qdrant.** Sections and past incidents move to Qdrant, with hybrid search for error codes | Retrieval scores before and after, beside each other | Search by meaning and keywords, retrieval evals |
| 3a | ✅ **Supabase: the Queue.** The board's batches, decisions, reviews and events live in Postgres | Restart the backend mid-batch: the board comes back, and unfinished tickets carry on | A system of record, states computed from data |
| 3b | ✅ **Supabase: the Assistant.** Postgres replaces SQLite checkpoints and `logs.csv` | A paused Assistant ticket survives a restart, and usage statistics read Postgres | Durable checkpoints |
| 4 | 🟡 **The Queue.** Load a batch, order it in code, and approve, correct or reject each decision with its evidence | A technician clears a morning batch, and technician time per ticket is measured | The human's step |
| 6 ✅ | **How it works.** An overview page of the goal, the route a ticket takes, the model, the tools and the services, built from the code | A recruiter understands the agent in two minutes without opening the repository | Explainability, a single source of truth |
| 7 | **Retrieval.** A page of the core retrieval measures, how sure each match is, and a search anyone can try | Type a request and watch which playbook it finds, and how strongly | RAG evaluation |
| 5 | **Durable and gated.** Retries, no repeated actions, spending limits per batch, and a release gate: a change ships only if its Langfuse experiment passes | Kill a batch mid-run and it carries on without doing anything twice. A worse change is refused | Idempotency, `RetryPolicy`, evals as a release gate |
| 9 ✅ | **Three groups.** The tabs regroup into Try it (Queue, Assistant), Is it worth it? (Money, Models) and How it works (Workflow, Harness, Knowledge base, Retrieval, Tickets, Evaluations), each view with its own link, and each group opens with what its views show | Send someone a link straight to a playbook or a model's run | Explain the system in layers |
| 10 | **Knowledge base.** A tab to explore what the agent knows: a cause map from each playbook's causes to the path, fix or queue they lead to, the policies that override them, the families with no playbook, and how the agent does on each | Click a cause and see the fix it allows, its risk tier, and how often the agent gets it right | Make the knowledge, not just the answer, inspectable |
| 11 ✅ | **The harness.** A tab that draws what surrounds the model on one ticket: what it reads, the one tool it can call to decide, the form it fills, the limits it runs under, and the checks code makes on its answer. The fixes it proposes stay on Workflow | Pick a ticket and see exactly what the model read and what it answered | Agents need a harness: instructions, tools, limits and checks |
| 12 | **A conversation, with MCP.** The lookup tools from Sprint 1's commit 7 move behind FirstLine's own read-only MCP server. The Assistant asks the requester when something essential is missing, and a technician can question a decision in the Queue | An employee is asked which laptop, and the answer changes the fix. A technician asks "why not escalate?" and gets the evidence | MCP, multi-turn agents, the human in the loop |

The Queue's first version is in: batches, live states, review with measured time, traces in the UI and the value in CHF. Since commit 3a it keeps its record in Supabase and survives a restart. The agent doesn't investigate yet.

Sprint 2 started before Sprint 1's commits 6 to 8, at the owner's call, so the tools are in place when those experiments run.

Tests stay free and offline: Qdrant has a local mode with no server, and Postgres runs in a container in CI. Commit 1 needs your Langfuse keys, commit 2 a Qdrant key, and commit 3 a Supabase project.

### Success criteria

The number after each one is the commit that meets it. The Queue's investigation and rules come from Sprint 1's commits 6 and 7, so Sprint 2 builds the system they run in.

**Observability: Langfuse (`agent/tracing.py`)**

- [x] (1) Every Assistant, Queue and evaluation run is one trace in Langfuse Cloud's EU region, tagged by mode, with emails, employee ids and IP addresses masked before it leaves the Mac. A test proves the masking.
- [x] (1) The practice sets are Langfuse datasets, and saved runs are experiments scored by our own code, replayed with no model calls. Held-out tickets are never sent, checked by a test.
- [x] (4) A technician's verdict is a score on the ticket's trace, and the dashboard shows the trace's steps with time, tokens and cost.
- [ ] (5) The release gate reads its two experiments from Langfuse, so a refused change can be opened and compared there.

**Search: Qdrant (`agent/retrieval.py`)**

- [x] (2) Knowledge base sections are searched in Qdrant Cloud, with the same results as the NumPy search on all 206 practice tickets, so the retrieval scores are unchanged.
- [x] (2) Search refuses an index built from another knowledge base or embedding model, and `uv run -m agent.index` rebuilds it for free. Tests use an in-memory index with no server.
- [ ] (2) Keyword search runs beside search by meaning in the same query. An error code or a bare title such as `T-012` finds its playbook first, checked by a test.
- [ ] (2) The retrieval score shows the meaning-only and hybrid results beside each other. Hit rate on development stays at its floor or above, and false matches on unseen families don't rise.
- [ ] (2) Past incidents from the knowledge base split are a second collection, `incidents`, with their resolutions. A test proves no development or held-out ticket is in it.

**System of record: Supabase (`backend/`, `supabase/`)**

- [x] (3a) Five tables, batches, tickets, decisions, reviews and an append-only audit trail, are in `supabase/migrations/` and applied. Check constraints refuse an unknown path, an Assistant ticket in a batch, and a correction on a review that isn't "corrected".
- [x] (3a) Row-level security is on with no policies, so the publishable key reads no rows and can't insert.
- [x] (3a) `backend/store.py` is the board's only way to save and read, with a Postgres version through `SUPABASE_DB_URL` and a memory version that behaves the same. One set of tests runs against both, and without the URL the backend, tests and e2e use memory.
- [x] (3a) A ticket's state is computed from its events, decision and review, never stored. Each step is one event with its actor, and one step's writes are one transaction.
- [x] (3a) What isn't in Supabase, such as the title, SLA and requester's profile, is joined from `data/` by id, so no copy can drift. A decision records the runner's version hash, so it says which instructions, tools and knowledge base made it.
- [x] (3a) `uv run -m backend.migrate` applies new migrations, records each in `schema_migrations`, and does nothing on a second run. A second migration keeps each retrieved section's score.
- [x] (3a) After a restart the board comes back as it was. Tickets that were queued or working go back to the agent once, a ticket with a decision is never triaged again, and the desk never hands out a ticket already in Supabase.
- [x] (3b) LangGraph's checkpoints are in Postgres, so a paused Assistant ticket survives a restart. `checkpoints.sqlite` is no longer written.
- [x] (3b) An Assistant run is a ticket, a decision and its events in Supabase instead of a row in `logs.csv`, and the usage statistics read Postgres. The old rows stay in Langfuse.

**The Queue (`backend/queue_board.py`, `dashboard/`)**

- [x] (4) "Load 8 tickets" takes development tickets only, mixing kinds of request, and code orders them by priority, then age. Two workers triage them, and the board shows each state as it changes.
- [x] (4) A ticket opens with its decision, reasoning, knowledge used, proposed action and trace. Nothing runs until a technician approves, sends it to another team or rejects it with a reason.
- [x] (4) Review time per ticket is measured, and the board shows the time saved and the net saving in CHF, with its assumptions on the page.
- [ ] (4) The Queue uses the investigation and rules from Sprint 1's commits 6 and 7 once they exist, and a ticket shows the checks the agent ran and any rule that changed its decision.
- [x] (4) The board is a Kanban of the computed states, with the human gate in amber, each card coloured by the agent's path, and the review in a drawer beside it. Cards move only when their state changes, never by dragging.
- [ ] (4) A technician can clear a batch from the keyboard: next ticket, approve, reroute and reject. *(Not needed for now, at the owner's call.)*

**Explainability (`dashboard/`, `backend/`)**

`docs/EXPLAINABILITY.md` holds the rules both pages follow.

- [x] (6) `GET /api/overview` builds everything the page shows from the code: the goal and its measure, the model and its price per ticket, LangGraph's real nodes and edges, the 17 tools with risk tier, owner and whether they change a system, the four paths, the services and what each holds, and the current versions. Nothing about the agent is typed into the dashboard. The rules join the page when `agent/rules.py` exists.
- [x] (6) A "How it works" tab opens with the goal in one sentence, then the route as a schematic. Clicking a station explains what happens there, with a real ticket's data, and amber marks the stations where a person decides.
- [x] (6) The tools are grouped by risk tier, the model shows why it was chosen and what a ticket costs, and the services show which one is the source of truth for what. Each part names where it fails, from the known limitations.
- [x] (6) A test fails when a graph node or tool has no explanation, so the page can't fall behind the code. The schematic has a text equivalent.
- [x] (7) Saved retrieval scores keep each ticket's ranked sections and scores. Saving them again is free, with no model calls.
- [x] (7) A "Retrieval" view shows hit rate, how high the right playbook ranks (MRR), recall and false matches on unseen families. Each comes with its question, n, the floor `poe check` enforces, and how it moved across saved runs.
- [x] (7) A chart shows the right playbook's score against the best wrong one for every ticket, with the thresholds drawn in, so a reader sees why the thresholds sit where they do. Clicking a ticket opens its ranked sections.
- [x] (7) "Try a search" ranks the knowledge base for any text the reader types, with the scores and the threshold, through `POST /api/retrieval/search`. It's free, because embeddings run on this machine and no model is called.
- [ ] (7) The view shows how retrieval changes the decision: path accuracy with and without it, from saved runs. The view reads both from saved runs and shows the one with search. None is saved without it, because with search off the agent answers in plain text with no path to score. Measuring it needs a run where the decision form gets no playbook, about CHF 0.65 on the development set, and waits for the owner's go-ahead.
- [ ] (6, 7) Both pages pass the checklist in `docs/EXPLAINABILITY.md`: phone width, keyboard, and screenshots reviewed.

**Three groups (`dashboard/`)**

- [x] (9) The masthead has three groups, Try it, Is it worth it? and How it works, and each group has one row of tabs: Queue and Assistant; Money and Models; Workflow, Harness, Knowledge base, Retrieval, Tickets and Evaluations.
- [x] (9) Every saved run moves from under Models to its own Evaluations tab, so the business group keeps only the answer.
- [x] (9) Each view has its own link, such as `?view=kb&doc=vpn-access`, and a reload or a shared link opens the same view. A paused Assistant run still opens from its link.
- [x] (9) The navigation works with the keyboard and at phone width, with no sideways scrolling.
- [x] (9) Each group opened with its question and two or three findings. The owner found them hard to read and not needed, so they were removed; each view now opens with its own answer.
- [x] (9) Tabs that aren't built yet, such as Knowledge base before commit 10, don't appear.

**Knowledge base (`backend/`, `dashboard/`)**

- [ ] (10) `GET /api/kb` builds the knowledge base view from the code and data, with no model calls: the playbooks, policies and references in `data/kb/`, each playbook's known causes from `data/evals/causes.json`, the path, fix or queue each cause leads to, the tools' risk tiers and owners from `agent/tool_schemas.py`, the policies' rules and where code enforces them, and the knowledge base version and the index it was built into.
- [ ] (10) It opens with one sentence on what the agent knows, counted from the data: playbooks, policies, references, causes, fixes and queues.
- [ ] (10) A cause map draws each playbook as a line and each known cause as a station, coloured by its path, with the fix or queue at its end and a policy that overrides it marked on the line. The families with no playbook are dashed lines that always escalate. It has a text equivalent for screen readers, and becomes a list at phone width.
- [ ] (10) Selecting a playbook opens its reader: its sections as the chunks search uses, each with how often it's the best match for development tickets and its top score, and every fix it names with its risk tier and owner.
- [ ] (10) Each playbook shows how the agent does on its family in the latest saved run: right in full with n and margin, and its mistakes in CHF, so weak playbooks stand out.
- [ ] (10) Each policy lists what it forces and the code that enforces it.
- [ ] (10) Find highlights matching causes and sections in the browser, for free, and links to the Retrieval tab's ranked search.
- [ ] (10) A test fails if a playbook, cause, policy or fix in the data has no place on the map.

**The harness (`backend/`, `dashboard/`)**

- [x] (11) `GET /api/harness` builds the view from the code, with no model calls: the instructions file and its sections, how search chooses sections (embedding model, thresholds, how many), what the model reads and in what order, the model, its provider, reasoning effort, token limit and retries, the decision form's fields in order with their descriptions from `agent/decision.py`, and every check code makes on the answer, with where a failure goes.
- [x] (11) A "Harness" tab under How it works draws one ticket's model call as a schematic: what goes in, the model, the one tool it calls to decide, the form it fills, code's checks, and the human gate after. Only the tools used to decide are drawn; the fixes it may propose are counted and link to Workflow.
- [x] (11) It says plainly that there's no loop yet: the model decides in one pass and can't look anything up, and the investigation loop of Sprint 1's commit 7 would change that.
- [x] (11) Picking a development ticket shows what the model read, its search results with scores, and what the default model decided in its latest saved run, for free.
- [x] (11) A test fails when a decision field or a check has no explanation, and the schematic has a text equivalent. It passes the checklist in `docs/EXPLAINABILITY.md`.

**A conversation, with MCP (`agent/`, `backend/`, `dashboard/`, `evals/`)**

- [ ] (12) FirstLine's own MCP server serves the four lookup tools and has no tool that changes anything. The loop discovers them through MCP, and tests run the server in memory.
- [ ] (12) The Assistant can pause to ask the requester one question when something essential is missing, through the same pause and resume as the human gates, and the conversation is kept in the checkpoints. The Queue never asks: it escalates and says what's missing.
- [ ] (12) In the Queue, a technician can ask about a decision. The agent answers from the trace and the same read-only tools, and can't change the decision.
- [ ] (12) A simulated requester, a model that knows the ticket's hidden facts, answers the Assistant's questions in evaluations. Labels say when asking was right, and asking too often counts against it. Its cost is stated and agreed before it runs.
- [ ] (12) The Harness view draws the loop and the conversation, from the code.

**Durable and gated (`agent/`, `backend/`, `evals/`)**

- [ ] (5) Model calls and searches retry on connection errors, with limits, and a model call isn't retried after the model has answered. *(Searches retry since commit 4.)*
- [ ] (5) Every action carries a key made from its ticket and decision, and a second attempt with the same key returns the first result without running again, checked by a test.
- [ ] (5) Killing the backend mid-batch and starting it again finishes the batch, with no ticket triaged twice and no action run twice. A test kills it between steps.
- [ ] (5) A batch states its estimated cost before it starts and refuses to start above its cap, CHF 0.25 by default.
- [ ] (5) `uv run -m evals.gate` runs a change on the samples and refuses it if path accuracy falls by more than the margin of error or the mistake bill rises, against the saved baseline. A deliberately worse instruction is refused, with no model calls in the test.

**Checks and CI**

- [ ] (all) `uv run poe check` passes on every commit, with the coverage thresholds unchanged and no API key. From commit 3a it also needs Docker, for a throwaway Postgres 17 through `testcontainers`. It never touches Supabase, Qdrant Cloud or Langfuse.
- [ ] (all) Each live check is made by hand and says what it cost, such as a batch, a restart and the same board coming back for about CHF 0.03.
- [ ] (all) New services and dependencies are in `docs/TECH_STACK.md`, and what moved where is in `docs/STATUS.md` and `docs/DECISIONS.md`, in the commit that does it.

## Sprint 3: deliver it

**Phase 3, production: security in layers, the client's cloud, cost control, operations and handover.** Week 3 in one line: decide what the agent may do, secure it in layers, run it in the client's cloud, and hand it over.

| # | Commit | Demo moment | Course idea |
|---|---|---|---|
| 1 | **Guardrails.** Coded checks for personal data and keys, Content Safety Prompt Shields for hidden instructions, and a set of attack tickets | A ticket with a hidden instruction is held, and false alarms are counted | Lethal trifecta, guardrail layers |
| 2 | **Container.** The app builds into one image, with no secrets in it | The same image runs locally | Configuration and secrets |
| 3 | **Azure and Foundry.** Infrastructure as code, Container Apps, Key Vault, managed identity and budget alerts. Claude through Microsoft Foundry, plus one cross-vendor comparison on a sample | A hosted demo with one command to tear it down, and Claude beside another vendor's model on the same chart | Where it runs, cloud hygiene, choosing models with evidence |
| 4 | **Gateway.** API Management in front of every model call, with rate limits and token budgets, logging first and enforcing after | A spending limit that blocks a call | Gateways, log-only then enforce |
| 5 | **Handover and demo.** A phone layout for the Queue board, a one-page autonomy policy, a runbook, measures against the Sprint 1 baseline, a password on the demo, a replay mode so visitors cost nothing, and a 3-minute video | A client could run it without you, and a recruiter can click through it for free | Handover and adoption |

### The demo

Three minutes, in this order:

1. **Assistant (30 s).** An employee types a problem and gets an answer. A risky request is held for a technician.
2. **Queue (60 s).** A technician's morning batch, pre-triaged. One ticket hides an instruction and is held. Code blocks a repeat lockout, even though the model proposed an unlock. The technician clears the lists in minutes.
3. **Proof (60 s).** The Scoreboard against the yardsticks in CHF, one decision's trace in Langfuse, and the app running on Azure behind its gateway.
4. **Where it fails (30 s).** What it still gets wrong, and what I'd test next.

### Microsoft Foundry: a layer, not the architecture

Foundry provides the models and Content Safety. The agent, its gates and its rules stay in our own tested code, so they're portable and auditable. Foundry Agent Service would replace LangGraph's human gates and resumable checkpoints, which are the core of the design, and Foundry's tracing would duplicate Langfuse.

### From AWS to Azure

| Course, on AWS | FirstLine, on Azure | Why |
|---|---|---|
| AgentCore Runtime | Azure Container Apps | It runs any framework, so LangGraph stays as it is |
| AgentCore Gateway and Policy | API Management | Token limits in front of the model. We skip an MCP gateway, because these are our own tools |
| AgentCore Identity, IAM user | Managed identity, Entra ID and Key Vault | The app holds no cloud passwords |
| Bedrock | Claude in Microsoft Foundry | One bill and one identity. The direct Anthropic API is plan B |
| Bedrock Guardrails | Content Safety Prompt Shields | A managed check for hidden instructions, beside our coded checks |
| Budget alerts, teardown | Azure budgets, teardown with infrastructure as code | Budgets alert, they don't stop spending, so teardown still matters |

To check before Sprint 3 starts: whether Container Apps runs in Switzerland North, the current Foundry regions and data zones for Claude, and the monthly price of an API Management v2 tier.

## How the course maps to FirstLine

| Week | Idea | In FirstLine |
|---|---|---|
| 1 | Score against a simple baseline | Most common answer, and a classifier |
| 1 | Weigh mistakes by business cost | Mistake costs in CHF |
| 1 | One call can beat an agent | Commit 7 tests the loop against one call, and keeps it only if it earns its cost |
| 1 | Structured outputs, rationale first | The decision class |
| 1 | Test models on the customer's task | Sprint 1 commit 8, and the cross-vendor comparison on Azure |
| 1 | Agents need a harness | Instructions, tools, limits and a human handoff |
| 2 | Business logic belongs in code | `agent/rules.py` |
| 2 | Start with one agent | One agent per ticket, and no sub-agents |
| 2 | Evals gate releases | The release gate in Sprint 2 commit 5 |
| 2 | Side effects get their own node | Already how the gates work |
| 3 | Lethal trifecta | Ticket text is untrusted and records are private, so Queue tools only read, and a person approves anything that leaves |
| 3 | Provenance | Owner and review date on every playbook |
| 3 | Agree success criteria at the start | `docs/BUSINESS_GOAL.md`, measured at handover |

We're leaving some things out on purpose, and each is a choice we can defend:

- **Further dataset work.** The labels are frozen. More review would improve the numbers, not the method.
- **Self-improving agents and an LLM judge.** Evals in plain code are enough to gate a release here.
- **Ranking the families by value.** The handover names the next family to automate, from the Sprint 1 numbers.
- **Local and open-weight models.** Claude is enough. A local model is plan C if a client won't send data to a provider.
- **Fine-tuning.** Our tickets are too few and too alike.
- **Sub-agents and A2A.** One agent with our own tools doesn't need them. MCP serves only our own read-only tools, from Sprint 2's commit 12.
- **Foundry Agent Service.** It would replace the gates and checkpoints we built on purpose.
- **Self-hosted Langfuse.** Too much to run for a demo.

## How the knowledge base is structured

```text
data/kb/
├── company-profile.md        systems, teams, offices and naming
├── escalation-queues.md      each queue, what it owns and its SLA
├── policies/                 one file per policy, such as sec-04-account-lockout.md
└── playbooks/                one file per issue
```

Each playbook starts with fields that code reads (`id`, `title`, `owner_team`, `last_reviewed`, `applications`, `tools`), then has the same six sections: symptoms, checks, error codes, known causes, fix, and when to escalate. `CES` and `AIT` have no playbook, so they test how the agent handles the unknown.

## How the rest of the product changes

| Part | Now | Target |
|---|---|---|
| `agent/` | The Assistant's graph | Plus `rules.py`, `queue.py` and redaction |
| `agent/retrieval.py` | Local NumPy search | The same interface, on Qdrant |
| `evals/` | Decision scores, yardsticks and cost guards | Plus Langfuse experiments and a release gate |
| `backend/` | Triage and evaluation routes | Plus batch and review routes |
| `dashboard/` | Assistant, Scoreboard, Tickets | Queue, Assistant, Scoreboard, Tickets, each ticket linked to its trace |
| Storage | SQLite and CSV | Supabase |
| Models | Claude's API | Claude through Microsoft Foundry, with the direct API as plan B |
| Hosting | Your Mac | Azure Container Apps, behind API Management |

## After Sprint 3

German comes next: tickets and answers in both modes. It needs a multilingual embedding model, German tickets in the evaluations, and answers in the language of the request.

## How to make this a solid project

Employers will spend a few minutes on this, so each point should be something they can see.

1. **Lead with the method.** The README opens with the four promises and the six steps, and IT detail stays in the background.
2. **Let numbers make the claim.** Measured accuracy, mistake cost, technician time and cost per ticket, in CHF, beside the yardsticks.
3. **Show where it fails.** The Scoreboard shows every mistake, and the demo ends on what it still gets wrong.
4. **Close rule gaps by how much harm they do.** Each safety rule needs code, plus a test where a stub model tries to break it.
5. **Fail towards a technician.** A timeout, API error or unreadable answer becomes an escalation, never a crash or a silent fix.
6. **Make every decision traceable.** Each ticket shows what was retrieved, proposed, overridden and confirmed.
7. **Take Swiss data protection seriously.** Say plainly what reaches a model hosted abroad, and keep personal data out of logs and traces.
8. **Stay honest.** The tickets are synthetic, the labels approximate, the costs assumptions and the test sets small.

## Not for now

Real integrations, more than one company, agents that change themselves, and fixes that run without a person.
