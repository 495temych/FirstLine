# Swiss

CorpLabs AG is in Zürich, so FirstLine is built the way a Swiss client would expect: data kept close, every service's location known, and plain about where it isn't. This file has the rules and the practices that follow from them, for this project and others like it. It's an engineering guide, not legal advice. How each service meets them is in `docs/TECH_STACK.md` and `docs/DECISIONS.md`.

## The rules that apply

- **The Swiss Data Protection Act (revFADP, in force since September 2023)** covers our staff's personal data. It may go to countries the Federal Council lists as adequate, which includes the EU and EEA, and to US companies certified under the Swiss-US Data Privacy Framework. Anywhere else needs safeguards such as standard contractual clauses.
- **The GDPR** applies too, through the offices in Frankfurt, Munich and Milan.
- **Banks, insurers and the public sector** add their own, such as FINMA's outsourcing rules. Clients like that ask where every byte goes.

## Practices

- **Every service names its region** in `docs/TECH_STACK.md`, and a region not yet confirmed says so.
- **Switzerland first, then the EU.** A Swiss region where one exists, the EU otherwise, and a written reason in `docs/DECISIONS.md` when neither is possible.
- **Only what's needed leaves.** Text is redacted before export, and what can run locally does, so ticket text reaches as few services as it must.
- **Providers that don't keep the data.** A model provider must not train on or retain prompts. Through OpenRouter that's `data_collection: "deny"`, and each benchmarked model records its provider and where that provider hosts it.

## Concerns

- **Model calls mostly go to the US.** Anthropic and most open-weight hosts process prompts there, and Claude in Foundry has no Swiss or EU data zone we could confirm. Synthetic tickets make that fine here, but a real client would need an EU-hosted model, so the benchmark says which models have one.
- **Routers hide the host.** OpenRouter can send one model to different providers, so the provider is recorded with every result.
- **Cheap plans rarely let you pick.** The free tier may offer only a US region, so budget and location are traded openly, never silently (`docs/BUDGET.md`).
