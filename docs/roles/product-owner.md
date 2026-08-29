# The product owner hat

**The question this role answers: what should exist, and in what order?**

The hardest hat to wear honestly on a solo project, because the person deciding what to build is
the same person who wants to build the interesting thing. Its main job is to be the voice that asks
whether something should exist at all — a question the developer hat is structurally bad at asking,
having already started thinking about how.

## Responsibilities

- Deciding what mootmaker should do, and saying no.
- Keeping [`business-functionality.md`](../reference/business-functionality.md) accurate — it is the
  authoritative record of the system's behaviour, written for a non-technical reader.
- Maintaining [`use-cases.md`](../reference/use-cases.md), the client-agnostic catalogue the
  acceptance suites draw on.
- Triaging incoming issues: is this real, does it matter, which hat owns it, what priority.
- Ordering the backlog on the project board.

## Owns

| Artifact | Where |
|---|---|
| Business functionality | [`../reference/business-functionality.md`](../reference/business-functionality.md) |
| Use cases | [`../reference/use-cases.md`](../reference/use-cases.md) |
| Issue triage and priority | the [project board](../process/issues-and-board.md) |
| The `Drafting → Ready` gate on designs | [`../../designs/`](../../designs/) |

## Starting a session in this role

1. [`../reference/business-functionality.md`](../reference/business-functionality.md) — what the
   system does today.
2. The [project board](../process/issues-and-board.md), filtered to open work.
3. Any design currently at `Drafting`, if the session is about promoting one.
4. [`../process/principles.md`](../process/principles.md) — particularly "what mootmaker is for".
   Several product decisions follow directly from it being a demo rather than a business.

## How work flows

**New functionality is written down before it is built.** It goes into
`business-functionality.md` first, in the same bullet style, then into a design, then into code.
Each commit to that file is intended to read as a release note.

**Triage is a real activity, not a reflex.** For each incoming issue: is it genuinely a defect or a
misunderstanding; does it matter given this is a demo; which hat owns it; and is it small enough to
stay an issue or big enough to need a design.

**The `Ready` promotion is this hat's most consequential act.** It means "build this as written",
and it is the one human-gated transition in the design lifecycle. Promoting a design that is not
genuinely build-from-able wastes a lot of downstream work, because the implementing agent will do
exactly what it says.

## Deciding what not to build

The most useful thing this hat does. Some questions worth actually asking:

- **Does this serve the learning goal or the portfolio goal?** Those are the two reasons mootmaker
  exists. Work that serves neither is hobby work, which is fine — but call it that.
- **Would a real product need this, or does it just sound impressive?** The demo is meant to be
  credible, not feature-complete.
- **Is this interesting because it is valuable, or because it is fun to build?** Both are legitimate
  here; conflating them is not.
- **What does this cost to run?** Scale to zero is a hard constraint, not a preference.

## Definition of done

For a product-owner session:

- Decisions are recorded where someone else can find them — in `business-functionality.md`, in an
  issue, or in a design's trade-offs section. A decision that exists only in a chat transcript has
  not been made.
- Anything promoted to `Ready` has every blocking question genuinely answered, not just recorded.
- The board reflects reality: nothing open and unlabelled, nothing done and still showing as open.
