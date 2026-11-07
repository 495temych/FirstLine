# Source

These tickets come from [Synthetic IT Support Tickets](https://www.kaggle.com/datasets/alexandermeau/synthetic-it-support-tickets) by alexandermeau, revision 4, under the MIT licence. All of it is synthetic, and it contains no real personal data. The CorpLabs name comes from the dataset.

To import it again, put `itsm_ticket_corpus_flat.csv` in `labs/synthetic_tickets/` and run `uv run -m evals.import_tickets`. The same source gives the same files.

| File | What it holds |
|---|---|
| `tickets.json` | The 745 tickets, with only what's known when they arrive |
| `splits.json` | Which ticket belongs to which set |
| `../evals/incidents.json` | Answers: correspondence, diagnostics, root cause and resolution. The agent never sees this file |

| Set | Tickets | Use |
|---|---|---|
| `kb` | 384 | The only tickets that may be used to write the knowledge base |
| `dev` | 129 | Development |
| `held_out` | 128 | Run only at sprint review |
| `unseen_dev` | 52 | `AIT` and `CES` tickets, to tune against |
| `unseen_held_out` | 52 | `AIT` and `CES` tickets, run only at sprint review |
