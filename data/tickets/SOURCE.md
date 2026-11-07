# Source

These tickets come from [Synthetic IT Support Tickets](https://www.kaggle.com/datasets/alexandermeau/synthetic-it-support-tickets) by alexandermeau, revision 4, under the MIT licence. All of it is synthetic, and it contains no real personal data. The CorpLabs name comes from the dataset.

To import it again, put the dataset in `labs/synthetic_tickets/` and run `uv run -m evals.import_tickets`. The same source gives the same files.

| File | What it holds |
|---|---|
| `tickets.json` | The 745 tickets, with only what's known when they arrive |
| `splits.json` | Which ticket belongs to which set |
| `../records/users.json` | The 628 directory accounts with invented departments, devices, groups and lockouts, then the rules set's users |
| `../evals/incidents.json` | Answers: correspondence, diagnostics, root cause and resolution. The agent never sees this file |

The source lists 769 people, but repeats 88 usernames for different people. A username is unique in a real directory, so the first person with each one keeps it. The source has no requester column, so the import takes the account a ticket names first. In a few tickets that may be a colleague or technician, not the person who raised it.

| Set | Tickets | Use |
|---|---|---|
| `kb` | 384 | The only tickets that may be used to write the knowledge base |
| `dev` | 129 | Development |
| `held_out` | 128 | Run only at sprint review |
| `unseen_dev` | 52 | `AIT` and `CES` tickets, to tune against |
| `unseen_held_out` | 52 | `AIT` and `CES` tickets, run only at sprint review |
