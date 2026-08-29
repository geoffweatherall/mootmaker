# The author hat

**The question this role answers: what did we learn, and can someone else use it?**

Mootmaker exists to learn about AI-assisted development and to demonstrate professional judgement.
Neither happens automatically. Both require someone to stop, notice what actually just happened, and
write it down in a form another person can use.

This is the hat that turns a project into evidence.

## Responsibilities

- Capturing learnings while they are still fresh and specific.
- Writing the long-form pieces: [`learnings.md`](../showcase/learnings.md),
  [`debugging-techniques.md`](../showcase/debugging-techniques.md).
- Keeping the README's showcase content honest and current.
- Turning specific incidents into transferable principles — the actual skill of this role.

## Owns

| Artifact | Where |
|---|---|
| The learnings essay | [`../showcase/learnings.md`](../showcase/learnings.md) |
| Debugging techniques | [`../showcase/debugging-techniques.md`](../showcase/debugging-techniques.md) |
| README showcase framing | [`../../README.md`](../../README.md) |

## Starting a session in this role

1. [`../showcase/learnings.md`](../showcase/learnings.md) — what has already been said, so a new
   piece adds rather than repeats.
2. Whatever actually just happened: the commit history, the design that was implemented, the issue
   that was closed. **Specifics are the raw material.** A learning written from memory a month later
   is generic; one written from the actual diff is not.
3. [`../process/principles.md`](../process/principles.md) — several learnings became principles, and
   a new one may belong there instead.

## How work flows

**Write from a specific incident, then generalise — never the reverse.** Every piece of this
project's writing that is any good started from something concrete: a race condition, a cold-start
fix, a test that asserted on the wrong DOM property. Starting from a general claim produces the kind
of content-marketing prose nobody learns anything from.

**Include what did not work.** The record of "checked this, wasn't it" is as valuable as the answer,
and it is the part almost everyone omits. It is also the honest part — it shows the actual shape of
the work rather than a reconstructed straight line to the solution.

**Let the conclusion be uncomfortable if it is true.** The most credible thing in `learnings.md` is
the section arguing against the author's own earlier position, and the invited pushback on his own
conclusions. Writing that only says "this went well" is worth very little to a reader.

**Distinguish a learning from a principle.** A learning is "here is what happened and what I now
think". A principle is "here is what we do about it", and belongs in
[`../process/principles.md`](../process/principles.md). The same insight often produces both.

## When to put this hat on

Not on a schedule. The signals worth watching for:

- **A bug took a genuinely interesting route to solve.** That is a techniques piece.
- **A belief changed.** The most valuable thing to write, and the easiest to forget once the new
  belief feels obvious.
- **A decision was hard and got made.** Capture the reasoning while the rejected options are still
  fresh; a design's trade-offs section may be enough.
- **Something was surprising.** Surprise is the reliable signal that a model of the world just
  updated.

## Definition of done

- The piece stands alone. A reader with no context should get something from it.
- Every general claim is anchored to something specific that actually happened here.
- What did not work is included, not edited out.
- It is honest about uncertainty. "This is what I currently think" beats false confidence, and is
  more credible to the professional audience this project is partly written for.
