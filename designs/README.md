# Design documents — pattern & workflow

**Started 2026-08-28.** This folder holds one design document per feature/change of any real size
— written and refined *before* coding starts, then used as the actual prompt implementation begins
from. `date-time-format-settings.md` is the first design written under this pattern; earlier
feature docs (`archive/delete-my-account.md` and its paired `-todo.md`) predate it and used an ad
hoc two-file shape — see "Migrating older docs" below.

## Why

A design doc is a checkpoint: it forces trade-offs, open questions, and scope to be written down
and reviewed *before* any code exists, rather than discovered mid-implementation or left implicit
in a chat transcript. Once a design is refined enough, it doubles as the actual prompt an
implementation session starts from — "read `designs/<name>.md` and build it" should be a
sufficient instruction on its own.

## Status lifecycle

Every design doc carries a `**Status:**` line near the top, one of these four:

| Status | Meaning | Who moves it here |
|---|---|---|
| **Drafting** | Being written, refined, and reviewed. Not safe to build from yet — open questions may still be genuinely unresolved, not just recorded. | Default starting status for any new doc. |
| **Ready** | Refined and reviewed enough to build from as-is. Every *blocking* open question is answered (non-blocking ones can still be listed, to be resolved during implementation). | **Geoff, explicitly** — a design doesn't self-promote to Ready just because Claude judges it thorough. This is the one human-gated transition in the lifecycle. |
| **Building** | An implementation session is actively working from this doc. | Claude, when starting implementation work against it. |
| **Shipped** | Implemented, deployed, and verified — see "Definition of done" below. | Claude, once that bar is actually met — not just "code written." |

A doc can move backward too (e.g. Building → Drafting if implementation surfaces a decision that
needs re-opening) — the table above is the normal forward path, not a one-way gate.

## File naming and location

- One file per feature: `designs/<kebab-case-feature-name>.md` (e.g. `date-time-format-settings.md`).
- [`../docs/reference/data-model.md`](../docs/reference/data-model.md) is not a feature doc — it's
  a standing, living reference for the project's *current* domain data model (Cognito + DynamoDB
  both — see its own header), which is why it lives under `docs/reference/` rather than here. Every
  design doc's "Changes to the domain data model" section describes the *delta* it proposes against
  that reference, links to it rather than duplicating it, and the reference itself gets updated
  once the design ships — it should always reflect what's actually deployed today, never a
  proposal.
- `archive/` holds designs that are **done** — shipped, or superseded by a newer doc — kept for the
  record, not maintained. Nothing in there should be treated as current. Moving a design here when
  it reaches Shipped is what keeps this folder a list of *pending* work: if it is in `designs/`,
  it is still live.

## Section template

Not every section applies to every design — mark one `N/A` in one line rather than omitting it, so
every doc has a predictable, scannable shape. Keep each section proportional to the feature's real
complexity; a small change doesn't need paragraphs where one sentence covers it.

1. **Summary** — two or three sentences: what this is and why, skimmable without reading further.
2. **Status** — the lifecycle marker from the table above, plus the date it last changed.
3. **Scope / non-goals** — what this explicitly does *not* cover, as important as what it does.
4. **Trade-offs and decisions** — decisions already resolved (by discussion, or because one option
   was clearly correct), with the reasoning that led there. This is what lets a later reader (human
   or AI) trust a decision instead of re-litigating it.
5. **Choices you had me make** — distinct from the section above: decisions Claude made
   unilaterally because they weren't worth blocking on, flagged explicitly so Geoff can review and
   override any of them cheaply. If a doc has none of these, say so — it means every real decision
   was made together.
6. **Open questions** — genuinely unresolved items, separate from both sections above. Split into
   *blocking* (must be answered before Status can become Ready) and *non-blocking* (fine to resolve
   during implementation).
7. **Impacts on components** — which files/pages/services/repos this actually touches. Concrete
   enough that "impacts on components" plus "trade-offs and decisions" together could brief a fresh
   implementer with no other context.
8. **Changes to the domain data model and data storage models** — the delta against
   `../docs/reference/data-model.md` (Cognito attributes, DynamoDB tables/attributes/indexes, or both — most features
   that touch persisted state touch more than just DynamoDB, so check both explicitly rather than
   defaulting to "just the obvious database"). `N/A` for anything that's pure UI/display logic over
   already-existing data.
9. **Technical considerations** — implementation-level constraints, gotchas, and things a future
   implementer would otherwise have to rediscover the hard way (e.g. "backend times are naive local
   ISO strings, never parse them as UTC" — the kind of invariant that isn't obvious from the code
   alone). **Say what this leaves behind**: what it writes, where that goes, and what deletes it.
   Logs, metrics, snapshots, images, queued messages and stored objects all default to accumulating
   forever unless something is configured to expire them — see
   [`../docs/process/principles.md`](../docs/process/principles.md)'s "Nothing accumulates without
   a bound". If nothing deletes it, that is a gap in the design.
10. **Testing impacts** — which test layers need new or changed coverage (this project's own
    layering — unit / mocked-integration / real-deployed e2e+acceptance — is described in each
    repo's own `testing-strategy.md`), and specifically whether *existing* test scenarios need to
    change, not just whether new ones are needed.
11. **Documentation impacts** — which READMEs/CLAUDE.md files/use-case catalogs need updating once
    this ships, and roughly what changes in each.
12. **Rollout & migration** — how this reaches users safely: does it need a data migration/backfill
    for existing records, a feature flag, a phased rollout (ephemeral → `production` — there is no
    longer a long-lived `test` environment), or does it just deploy cleanly with no transition
    state to worry about?
13. **Risks** — what could go wrong, and anything that would make this harder to reverse than a
    normal deploy (e.g. a change that's easy to ship but expensive to undo).
14. **Implementation checklist** — an ordered, dependency-tracked task list, `[Geoff]`/`[Claude]`
    tagged for manual-vs-implementation steps (mirroring `archive/google-sign-in-todo.md`'s style,
    which predates this template but got the checklist shape right). Usually sparse or absent while
    Drafting, and filled in properly by the time a doc reaches Ready — it's what turns "Ready" into
    something Claude can actually start executing top-to-bottom.
15. **Definition of done** — the concrete bar for Shipped. At minimum: the feature's own new/changed
    acceptance-test coverage is green, the existing acceptance suite is still green on a real
    deployed environment (this project's usual done condition for work of any real size — fix bugs
    found along the way, confirm each touched repo's own unit tests, deploy, then a clean acceptance
    run against a real environment), and anything listed under "Documentation impacts" is actually done, not
    just planned.

## Process

1. Claude drafts the doc (Status: Drafting), researching the current codebase directly rather than
   guessing, and asks whatever questions are genuinely blocking before writing — see each doc's own
   "Choices you had me make" / "Open questions" split for how the rest gets handled.
2. Geoff and Claude refine it together — this can mean several rounds; the doc keeps being edited in
   place, not superseded by a new file.
3. Geoff moves Status to Ready when it's genuinely build-from-able. Like every other edit to this
   file, that happens on the design's own `design/<name>` branch and lands on `main` via a PR — see
   [`../docs/process/branching-and-prs.md`](../docs/process/branching-and-prs.md) — not a direct
   push, even though it's a one-line change.
4. An implementation session starts by reading the doc directly, moves Status to Building, and
   works through the Implementation checklist. The doc keeps being updated as reality diverges from
   plan (a design doc describes the *current* plan, not a frozen record of the first draft).
5. Once Definition of done is actually met, Status moves to Shipped, `../docs/reference/data-model.md` (if
   touched) gets updated to reflect the new current state, and the design **moves to
   [`archive/`](archive/)** — so `designs/` only ever lists work that is still pending.

## Migrating older docs

Some planning docs predate this pattern and used an ad hoc two-file shape (a "design & decisions"
doc plus a separate `-todo.md` checklist). They now live in [`archive/`](archive/):

| Archived | Superseded by |
|---|---|
| `archive/delete-my-account.md` + `-todo.md` | Nothing yet — still the most detailed record of that feature's thinking |
| `archive/meeting-picker-dropdowns-todo.md` | Shipped 2026-08-28; kept only for the record |

The old `archive/google-sign-in.md` and its `-todo.md` were **deleted** on 2026-09-01 rather than
kept: [`google-sign-in.md`](google-sign-in.md) fully supersedes them and is still unstarted, so
having two competing docs for unbuilt work was a live source of confusion rather than a record of
anything. Archiving is for work that is *done*; a superseded doc for work that never began is just
a second answer to the same open question.

They are **not rewritten to fit this template**. They are genuinely detailed planning notes, and
reformatting them would risk losing content for no gain. The rule is: when an archived doc is
picked up again for real work, write a new design in this folder under the current template and
leave the archived original alone as history. That is what happened with `google-sign-in.md`, and
what should happen to `delete-my-account` if it is ever revived.

Nothing in `archive/` is maintained or should be treated as current.
