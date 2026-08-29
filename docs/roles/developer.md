# The developer hat

**The question this role answers: how should this be built, and does it actually work?**

The default hat, and the one most of this project's process is written for.

## Responsibilities

- Turning a `Ready` design into working, deployed, tested code.
- Writing and maintaining the test suites across all four layers.
- Diagnosing and fixing defects.
- Keeping each repository's README and reference documentation true.
- Writing designs — the developer hat drafts them; the product owner hat decides whether the thing
  is worth building at all.

## Owns

| Artifact | Where |
|---|---|
| Design documents | [`../../designs/`](../../designs/) |
| All application and infrastructure code | every code repository |
| Test suites | `impl/src/test`, `webapp/tests`, `e2e/`, `acceptance/` |
| Testing strategy | [`../reference/testing-strategy.md`](../reference/testing-strategy.md) |
| Data model reference | [`../reference/data-model.md`](../reference/data-model.md) |
| Repository READMEs | each repository |

## Starting a session in this role

1. [`../process/README.md`](../process/README.md) — how work is done here.
2. [`../process/principles.md`](../process/principles.md) — especially the review boundary, which
   tells you where care actually pays.
3. The README of whichever repository you are working in. It is load-bearing and current.
4. The design you are implementing, if there is one. "Read `designs/<name>.md` and build it" should
   be a sufficient brief; if it is not, the design is not `Ready`.
5. [`../reference/testing-strategy.md`](../reference/testing-strategy.md) if you are adding or
   changing tests.

## How work flows

**With a design** — the normal path for anything of size. Move its Status to `Building`, work the
implementation checklist top to bottom, update the design as reality diverges from plan, and move it
to `Shipped` only when the definition of done is genuinely met.

**Without a design** — for a bug or a small self-contained change. Work from the issue, and
reference it with `Closes #N` so the trail closes itself.

**When the design turns out to be wrong**, change the design. Do not silently implement something
else. A deviation recorded in the design is normal; a deviation discovered later in the diff is a
problem.

## Definition of done

Not "the code is written". For work of any real size:

- Fix bugs found along the way rather than routing around them.
- Each touched repository's unit tests pass.
- Everything is deployed to a real environment.
- The acceptance suite is **green against that real deployed environment**.
- Documentation the change made wrong is fixed in the same change.
- The ephemeral environment is torn down.

## Things this project has learned the hard way

**Distrust your instruments before your theory.** A test asserting on the wrong DOM property
silently reported nothing useful for several runs. When a failure is confusing, check that you are
observing correctly before theorising about the system.

**Reproduce the exact scenario, not an approximation.** A repro that is "basically the same" but
passes tells you far less than it feels like it does.

**"It's just flaky" is a hypothesis.** Test it by changing the variable it implies — a fresh
environment, a clean cache — before accepting it.

**A negative result is a result.** A log line that never printed proved a handler was never called,
which eliminated every theory about what was happening inside it.

**Fix at the layer where the defect actually lives.** The fix that makes the red test green is not
always the fix that is correct.

The full version, worked through a real race condition, is in
[`../showcase/debugging-techniques.md`](../showcase/debugging-techniques.md).
