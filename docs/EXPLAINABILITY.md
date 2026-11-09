# Explainability

FirstLine's dashboard should explain the project on its own. Someone who never opens the code or the other docs should still be able to answer three questions after a few minutes of clicking: what does the agent do, why did it decide this, and how sure are we that it works. This file sets the rules for every page that tries to answer them. `docs/BRAND.md` sets the look, and this file sets how a page explains.

## Who reads the page

Each page serves three readers at once, in layers:

| Reader | Time | What they need |
|---|---|---|
| A recruiter or hiring manager | 2 minutes | The goal, the result and why it can be trusted, in plain words |
| A technician | All day | The decision, its evidence and the next action, without noise |
| An engineer reviewing the work | As long as it takes | The mechanism, the numbers behind it and a link to the source |

So every page opens with the one-sentence answer, then a picture of the mechanism, then the detail on demand, and finally a link to the evidence. Nobody should need the deepest layer to understand the top one.

## Principles

### 1. Show the mechanism, not a description of it

Draw what really happens: the route a ticket takes, the stations it passes and the gates that hold it. A schematic beats a paragraph, and a paragraph beats a bullet list. A diagram shows the real thing, such as LangGraph's actual nodes, the 17 real tools or the real thresholds, never a simplified story that the code doesn't match.

### 2. The page reads its facts from the code

A fact the UI shows comes from the API, and the API builds it from the code that runs: the model from `agent/config.py`, the tools from `agent/tool_schemas.py`, the graph from `build_graph`, the scores from saved runs. A fact typed into a `.tsx` file goes stale the day the code changes. A test fails when something the code holds, such as a node or a tool, has no explanation.

### 3. Every number answers a question

A figure is labelled with the question it answers, such as "How often is the right playbook found?", not with its technical name. Beside it sit four things:

- **n**, so a reader can judge it: "129 tickets".
- **What good looks like**: the floor `poe check` enforces, or a yardstick.
- **The uncertainty**, where it's measured: a margin of error, or a small-sample warning.
- **Where it came from**: the run, its date and the versions it used.

A number without these is decoration.

### 4. Let people poke it

Explaining works best when the reader acts and the page answers. Good interactions here:

- Click a station on the route to see what happens there, with a real ticket's data.
- Type a request and watch which knowledge base sections it matches, and how strongly.
- Turn retrieval off and see the decision change.
- Open any decision's trace.

An interaction that is free says nothing about cost. One that calls a model shows its price on the button, as the Queue's load button does, and nothing explanatory may call a model by surprise.

### 5. Name things as a user would

Write "knowledge used", not "retrieved units". Write "how high the right playbook ranks", not "MRR", and give the technical name second, for the engineer. Define a term where it first appears, in a short sentence or a disclosure, never in a glossary page nobody opens. Use the same words for the same thing everywhere: a path is called "Auto-fix" on every page.

### 6. Be honest about the limits

Show where it fails, as clearly as where it works. That means mistakes and their cost in CHF, the families it has never seen, a small sample marked as one, and the known limitations from `docs/DECISIONS.md` on the page that they affect. An empty state says what would fill it and how. A reader trusts a page that shows its weak spots.

### 7. Every claim links to its evidence

A decision links to its Langfuse trace. A score links to its saved run, and a tool shows its risk tier and owner. A rule names the code that enforces it. The deepest layer of every page is something a reviewer can check without asking anyone.

## Visual language

`docs/BRAND.md` is the fixed direction: the route metaphor, Familjen Grotesk and IBM Plex Mono, the paper, panel and ink colours, one colour per path, and signal amber for human gates only. Within it:

- **One bold element per page.** On the overview that's the route schematic, and on retrieval it's the score distribution. Everything else stays quiet and tabular.
- **Schematic, not illustration.** Diagrams are inline SVG drawn from data, with lines, stations and labels, and no stock icons, mascots or gradients.
- **Colour carries meaning, never decoration.** A path's colour means that path, and amber means a person decides. Nothing relies on colour alone: every coloured thing has a label or a shape too.
- **Motion answers an action.** A station opens because it was clicked, and a bar grows because a query was typed. Nothing moves on its own, and `prefers-reduced-motion` turns the rest off.
- **Avoid the generated look.** Don't use all-caps eyebrow labels, numbered markers on things that aren't a sequence, a grid of identical cards with the same shadow, or a big number with a gradient accent. The frontend-design skill in `.claude/skills/frontend-design/` lists these defaults. Read it before any design pass.

## The quality floor

- It works at phone width (375 px) with no sideways scrolling.
- Everything can be reached and used with the keyboard, with a visible focus ring.
- Every diagram has a text equivalent for screen readers, such as a list of stations or a table of values.
- Text contrast meets WCAG AA.
- Tests check the explanations the way they check the features: a missing explanation fails, and so does a number shown without its n.

## Checklist for a new page

1. Write the one-sentence answer the page gives, before designing anything.
2. Name its three layers: the answer, the mechanism, the detail and its evidence.
3. List every fact it shows and the code or saved run it comes from.
4. Give each number its question, n, what good looks like, uncertainty and source.
5. Choose the one interaction that teaches the most, and say what it costs.
6. Say where the thing it explains fails.
7. Run a design pass with the frontend-design skill against `docs/BRAND.md`, then review screenshots on desktop and at phone width.
