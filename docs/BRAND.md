# Brand

FirstLine looks like the work tool a service desk already knows: a sidebar to move around, the work in the middle, and its details on the right. What makes it an AI product is what sits in the middle. The agent's steps are the main thing on the page, every decision says why next to it, and a person decides at every gate.

## Principles

- **The agent shows its work.** Its steps, what each one found and what it cost are always on screen, in order, as they happen. Nothing it decided is hidden behind a click, though the detail may be.
- **One bold element per page.** The agent's steps in the Assistant, the board in the Queue, the route in Workflow, the chart in Retrieval. Everything else is quiet and tabular.
- **Colour means something.** Blue is something you can do, amber is a person deciding, and each path has its colour. Nothing else is coloured, and nothing relies on colour alone.
- **Dense, not crowded.** Rows are compact like Jira's, and whitespace separates groups, not items.

## Fonts

From Google Fonts:

- **Interface**: Instrument Sans, at 13 px for body text and 12 px for details, with headings at 16, 20 and 24 px, weights 400, 500 and 600.
- **Tools, queues, ticket ids and code**: IBM Plex Mono.

Numbers use tabular figures.

## Colours

One light theme, whatever the system setting. Every colour is a token on `:root` in `dashboard/src/styles.css`, and nothing in a component is a raw hex value.

| Token | Value | Use |
|---|---|---|
| Canvas | `#F6F7F9` | Page background |
| Surface | `#FFFFFF` | Sidebar, panels, cards and the top bar |
| Sunken | `#EEF1F5` | The requester's message, code, inputs at rest |
| Border | `#DFE2E7` | 1 px hairlines; `#C9CED6` for controls, as `--border` and `--border-strong` |
| Ink | `#172033` | Main text |
| Ink secondary | `#4B5568` | Supporting text |
| Ink muted | `#6B7385` | Labels, captions and metadata |
| Action blue | `#1D5BD8` | Buttons, links, focus and the current page; tint `#E8EFFC` |
| Gate amber | `#F2B705` | A person decides, and nothing else; tint `#FFF8DB`, text `#6B4E00` |
| Danger | `#C9372C` | Something failed; tint `#FDECEA` |

Each path has one colour, used for its label and for the line beside the agent's steps once it decides:

| Path | Colour | Label tint |
|---|---|---|
| Self-serve | `#1F7A4D` | `#E3F3EA` |
| Auto-fix | `#0F6F7A` | `#DFF1F2` |
| Escalate | `#B5480E` | `#FBE9DF` |
| Out of scope | `#5E6878` | `#ECEEF1` |
| No tools | `#6B4FBB` | `#EEEAFA` |

Auto-fix is teal, not blue, so a path is never mistaken for something to click.

## Shape and space

- A 4 px grid. Panels are padded 16 px, rows 6 to 8 px.
- Corners: 6 px on controls, labels and inputs, 10 px on panels and cards, round on avatars.
- Hairline borders separate things. Shadows only lift what floats: a drawer, a popover, a menu.
- Text lines stay under about 80 characters.

## Layout

Every page has the same frame:

- **Sidebar** on the left: FirstLine, then the three groups (Try it, Is it worth it?, How it works) with their views, each with a line icon. A footer shows the model in use. At phone width it folds into a menu button in the top bar.
- **Top bar**: where you are, as a breadcrumb.
- **Page header**: the page's title and its one-sentence answer, with the page's actions on the right.

The Assistant is a conversation with the message box at the bottom, or in the middle of the page before the first message. The ticket's details sit in a panel on the right, which stacks below the conversation at phone width. The Queue is a board, its review a drawer on the right. Tickets is a list with its filters on top.

## Components

- **Path and status labels**: small, tinted, with the colour's text, such as Escalate or Waiting.
- **Buttons**: blue for the one main action on a view, outlined for the rest, plain for the least. A button that calls a model says its price.
- **Evidence links**: trace, saved run, code path, each saying where it goes.
- **Step list**: the agent's steps as checked items on one line, each with what it found, its time and its cost, and a rule that changed the decision as a step of its own.
- **Gate card**: amber border and tint, saying what waits and what each answer does.
- **Message box**: who's asking and whether the knowledge base is on, inside the box, beside the button.
- **Metrics**: a number with the question it answers, its n, what good looks like and its source, never a big number on its own.

## Motion

About 150 ms, only in answer to something a person did: a drawer opening, a step being checked off, a disclosure expanding. A step that is working shows it, and nothing else moves on its own. `prefers-reduced-motion` turns it off.

## Avoid

- Decorative motion, gradients, glows and sparkles for "AI".
- All-caps labels, numbered markers on things that aren't a sequence, and grids of identical cards with the same shadow.
- A coloured border on one edge of a panel. The step list's line is the only one-edge line, and it is a route, not a border.

## Tone

Plain English, sentence case and no exclamation marks. Name a button after what it does, such as "Run fix". Money in francs is written as CHF 2'000.
