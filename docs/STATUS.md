# Status

TriagePilot triages one ticket at a time in a Streamlit app. Each ticket gets one model call, grounded in the top 2 knowledge base units, and ends on one of four paths behind human confirmation gates. All 10 remediation tools are simulated. `docs/ROADMAP.md` says what comes next.

## How to run it

```bash
uv sync
uv run pre-commit install
cp .env.example .env
uv run streamlit run app/main.py
```

- Put your key in `.env` as `ANTHROPIC_API_KEY`. `MODEL_NAME` is optional.
- Checks: `uv run poe check`. Tests never call a model.
- Evaluation: `uv run -m evals`. This calls the model 10 times.
- Usage statistics: `uv run -m app.stats`.
- Opening the app also runs the evaluation once, because the code in its collapsed expander still runs. That is 10 model calls per app start.
- The first run downloads `all-MiniLM-L6-v2` (~90 MB).

## Who enforces each rule

From the rules in `docs/SPEC.md`. Later briefs close the gaps.

| Rule | Enforced by | Where |
|---|---|---|
| No fix runs without confirmation | Code | The model's tool call is only parsed. `execute_tool` is reachable only through `confirm_fix` |
| No ticket without confirmation | Code | `create_ticket` is reachable only through `confirm_ticket` |
| A declined fix gives a pre-filled ticket, with no model call | Code | `draft_ticket` |
| Failed self-serve goes to the same ticket confirmation | Code | `route_after_self_serve` |
| The agent never asks the user a question | Instructions only | `agent/prompt.md`, line 52 |
| Access requests are escalated, never out of scope | Instructions only | `agent/prompt.md`, line 25 |
| SEC-04: 2+ lockouts go to `SEC-INCIDENT` | Instructions only | Knowledge base and `agent/prompt.md`. Nothing in code knows a user's lockout count |
| Tool parameters are concrete values | Instructions only | `agent/prompt.md`, line 56 |
| With retrieval off, no tools and no path | Code | `_call_model` binds tools only with retrieval on, and `no_tools` ends the run |
| Every finished run is logged, and evaluation runs are not | Code, with one gap | The `log` node and `log_runs=False`. Retrieval-off runs are not logged either, which the rule doesn't say |
| No secrets or real client data in the repository | Partly | `.gitignore` covers `.env`. Nothing scans commits |

## New clones

The Streamlit skill for coding agents isn't in git, because it's a link into the installed package. To use it on a new clone, after `uv sync`:

```bash
mkdir -p .claude/skills
ln -s ../../.venv/lib/python3.12/site-packages/streamlit/.agents/skills/developing-with-streamlit .claude/skills/developing-with-streamlit
```

## Demo queries

| Query | Expected path | What it demonstrates |
|---|---|---|
| "My VPN keeps disconnecting" | AUTO_FIX (usually) → `reset_vpn_profile`* | RAG on: cites migration, SCEP cert, exact script path. RAG off: generic advice, no tools, `NO TOOLS` badge. |
| "Teams shows me as offline to everyone" | AUTO_FIX → `clear_teams_cache` | Retrieved doc determines triage order (checks build version first). |
| "Floor 5 print queue is stuck" | AUTO_FIX → `restart_print_spooler` | Floor-wide scope triggers server-side fix, not single-user troubleshooting. |
| "VPN cert error, gateway confirmed correct, offline for a month" | AUTO_FIX → `reset_vpn_profile` | Precise query context (confirmed gateway + offline duration) routes directly to cert reset. |
| "Need Zoom installed, no admin rights, it's in Company Portal" | AUTO_FIX → `push_approved_software` | Intune push path instead of directing user to portal UI. |
| "I'm locked out of my account" | ESCALATE → `SEC-INCIDENT` | Lockout frequency absent; per SEC-04 that distinction changes the path entirely. |
| "Locked out twice already today" | ESCALATE → `SEC-INCIDENT` (P2) | Cross-document retrieval: pulls the `account-access` playbook *and* the SEC-04 §4.2 section from `company-profile.md` in the same call — the policy section, not the playbook, is what forces escalation over a routine unlock. |
| "My OneDrive has been stuck syncing for two days" | ESCALATE → `M365-SYNC` | Ambiguous without quota/filename/department info — escalates with explicit reasoning. |
| "My external monitor isn't detected when docked" | SELF_SERVE or ESCALATE | KB has detailed self-serve steps (reseat cable, firmware, input source). May escalate to HW-REPLACE if the doc's steps are exhausted. |
| "What's the weather like today?" | OUT_OF_SCOPE | Scope-check fires before any diagnosis; no retrieval, no tool call. |

\* This bare query is genuinely underspecified — KB-0142 (`vpn.md`) documents three distinct causes, only one of which is safe to auto-fix, so single-shot classification can legitimately land on SELF_SERVE, AUTO_FIX, or ESCALATE from run to run. The more detailed query further down this table (with gateway + offline duration stated) resolves this ambiguity and consistently hits AUTO_FIX. Measured in `evals/runner.py` — see [Evaluation](DECISIONS.md#evaluation).

### Manual test: declining an AUTO_FIX

Run "My VPN cert error persists, I've confirmed the gateway is correct and I was offline for a month" (routes to AUTO_FIX → `reset_vpn_profile`), then click **Cancel** instead of Confirm. The app shows "Automated fix declined — here's a pre-filled ticket," built entirely from the diagnosis already displayed in section 3 above — no second model call. The draft ticket carries the declined tool name (`reset_vpn_profile`), the fixed reason "User declined proposed automated fix; issue persists," the original diagnostic summary, queue `DESKTOP-SUPPORT`, and priority `P3-Normal`. Clicking "Send to ServiceNow" dispatches `create_escalation_ticket` exactly as the ESCALATE path does; clicking Cancel again dismisses it with no ticket created and no fix applied. This is a UI/state-flow behavior, not a retrieval or path-classification outcome, so it isn't part of `evals/runner.py`'s golden set — verify it manually with the steps above.
