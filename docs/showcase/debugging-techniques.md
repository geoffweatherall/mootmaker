# Debugging techniques, illustrated by a real bug hunt

Written 2026-08-29, at Geoff's request, after chasing down a genuine race condition in
`mootmaker-webapp`'s Add Meeting room-suggestion feature (see commit `9ba17c4` — "Fix a real
cache-invalidation race in Add Meeting's room suggestion"). This isn't a retelling of that bug for
its own sake; it's an attempt to pull the *general, transferable* techniques out of that specific
hunt, so they're usable on the next bug, not just this one.

None of this is AI-specific. Every technique below is something any developer should reach for.
The one genuinely new wrinkle — covered at the end — is how the *shape* of a bug should influence
which AI model (if any) you reach for while chasing it.

## The core idea: debugging is narrowing a hypothesis space, not guessing

At any point while chasing a bug, there's a set of possible explanations consistent with what
you've observed so far. Progress means shrinking that set — ideally down to one. Every technique
below is really just a different way of shrinking it faster, or of noticing when you're not
actually shrinking it at all (just re-explaining the same evidence a different way, which feels
like progress but isn't).

## 1. Distrust your instruments before you distrust your theory

The very first signal in this bug hunt was a test assertion failing in a way that *looked* like
the application was broken. It wasn't — the assertion itself was reading the wrong thing (checking
`textContent` on what had become an `<input>` element after an unrelated UI change, which is
always empty regardless of what's actually in the field). The test had been silently reporting
nothing useful for several runs before anyone noticed.

**The general lesson**: when a failure looks confusing or inconsistent, check whether you're
actually *observing* the system correctly before you start theorizing about why the system is
broken. A surprisingly large fraction of "weird bugs" are actually "the thing telling me about the
bug is itself wrong." This costs almost nothing to check and saves you from building elaborate
theories on top of bad data.

## 2. Reproduce the *exact* scenario, not an approximation of it

Once a real hypothesis existed (a cache-invalidation race), I built a local reproduction —
correctly reasoned, correctly implemented — and it worked. The real, deployed version still failed
the same way. The gap turned out to be that my local repro used a simplified version of the actual
interaction (fewer items selected, one continuous UI session) rather than the exact sequence the
failing test performed (select many, act on the result, reopen the *same* control, select more,
act again).

**The general lesson**: a repro that's "basically the same" as the real failure but doesn't
actually fail tells you less than it feels like it does. It's tempting to declare victory when a
simplified version reproduces cleanly — but if the *real* thing still fails, the simplification
removed something that mattered. Match the real sequence of actions as closely as you can before
trusting a "can't reproduce it" result.

## 3. Rule out confounds by varying the *environment*, not just the code

When the fix didn't hold, the tempting move was to blame "flaky infrastructure" and move on — a
real thing that really does happen, and a genuine trap precisely because it's sometimes the correct
explanation. Before accepting it here, I reran the exact same scenario against a completely fresh,
never-before-touched environment. It failed identically. That single move eliminated an entire
category of explanation (accumulated test data, environment-specific state) in one step.

**The general lesson**: "it's just flaky" is a hypothesis, not a conclusion — and it's usually the
laziest one available, which is exactly why it deserves the most scrutiny before you accept it.
Test it the same way you'd test any other hypothesis: change the one variable it implies (a fresh
environment, a clean cache, a different machine) and see if the symptom actually goes away.

## 4. When reasoning stalls, make the invisible visible

This is the heart of the hunt, and the part Geoff specifically asked about — see the dedicated
section below on what makes a bug "instrumentable" in the first place.

Concretely, once pure reasoning about the code wasn't resolving anything further, I added direct
observability at three different levels of the same failing interaction:

- **Network-level**: intercepted the actual API requests and responses as they went out, to see
  exactly what values were really being sent and what really came back — removing any doubt about
  what the frontend was actually asking for.
- **Application-level**: temporary logging placed directly inside the running component, at the
  exact moment of the click and on every render, to see the real internal state (not what I assumed
  the state was) at the precise instant the bug occurred.
- **Visual**: a screenshot taken at the exact failure moment — which is what actually cracked the
  case. It showed the previous form field still visually focused, which was the concrete clue that
  redirected the entire investigation.

**The general lesson**: reasoning about code from a mental model of what it *should* do has a
ceiling. Past that ceiling, the fastest path forward is almost always to attach a probe to the real,
running system and look at what it's *actually* doing. This is true whether the probe is a log
line, a debugger breakpoint, a network trace, a screenshot, or a metrics dashboard — the common
thread is trading "I believe X" for "I can see X."

## 5. A negative result is still a result

One specific piece of instrumentation — a log line placed at the very first line of the suspect
function — printed nothing at all during the failing interaction. That absence was the single most
useful data point in the entire investigation: it proved the function was never even being called,
which ruled out every hypothesis about what might be going wrong *inside* it, and pointed the
search somewhere else entirely (something preventing the call from happening at all).

**The general lesson**: don't just look for confirming evidence. An experiment that shows nothing
happened is often more informative than one that shows the "expected" thing happening, because it
eliminates a whole branch of the hypothesis tree in one move. Design your instrumentation so a null
result is possible and would actually tell you something — a probe that always fires regardless of
what's happening isn't earning its keep.

## 6. Turn a hypothesis into a single, falsifiable, one-variable experiment

Once the "previous field still has focus" theory existed, I didn't reason further about whether it
was plausible — I ran one targeted experiment: add an explicit click on something else (forcing
focus away) immediately before the suspect action, and nothing else. The bug vanished immediately.

**The general lesson**: the fastest way to go from "I have a theory" to "I know" is to change
exactly one thing that the theory predicts matters, and observe whether the symptom moves. Resist
the urge to fix three things at once "while you're in there" — if the symptom changes, you won't
know which change actually mattered, and you've just traded one mystery for another.

## 7. Fix at the layer where the bug actually lives

The eventual fix landed in the test helper that was clicking through the UI, not in the
application code the test was exercising — because that's genuinely where the defect was (a
missing "click away to blur" step). It would have been easy to instead paper over the symptom
inside the application (for example, by making the app more defensive about redundant clicks) —
which might have made this one test pass without actually being correct, and would have hidden a
real gap in test coverage rather than closing it.

**The general lesson**: once you know *why* something fails, resist patching the first place that
would make the red test go green. Ask where the defect actually originates, and fix it there — the
fix that doesn't match the diagnosis usually just delays the next confusing bug report.

## 8. Clean up your diagnostic scaffolding before you call it done

Every temporary log line and debug instrument added along the way was removed before the fix was
committed — verified with a fresh check that nothing diagnostic-only survived into the shipped
code.

**The general lesson**: instrumentation earns its keep during the hunt and is a liability
afterward — leftover debug logging is noise for the next person (or the next bug hunt), and
occasionally a real performance or security issue if it's logging anything sensitive. Treat
"remove the scaffolding" as part of the fix, not an optional tidy-up.

## 9. Write down what you tried and what didn't work — not just the final answer

Two other, unrelated bugs were initially suspected of contributing to this same flakiness before
being properly ruled out. That's normal — the record of "checked this, wasn't it" is exactly as
valuable as the record of what the actual cause was, both for your own future self (so you don't
re-walk the same dead end) and for anyone else who picks the thread up later.

**The general lesson**: this is exactly what a good bug-tracking issue is *for* — not just "here's
what was wrong," but "here's what looked plausible and turned out not to be, and why." See
`designs/README.md`'s issue-tracking discussion for how this project is trying to do that.

---

## What makes a bug "instrumentable" — and why it's the single most useful thing to assess early

Before committing to a strategy for chasing a given bug, it's worth explicitly asking: **can I
attach a probe to this system while it's actually failing, and observe its real internal state?**
If yes, the bug is instrumentable. If no, it isn't — and that changes everything about how you
should spend your time.

**Instrumentable** looks like: you can reliably reproduce the failure on demand, you have the
ability to add logging/breakpoints/traces to the system while it fails, and you can iterate
(change something, rerun, observe) in a reasonably tight loop. The bug in this document was
instrumentable throughout — a real, if occasionally slow, deployed environment I could redeploy to
and observe.

**Not instrumentable** looks like: it only happens on a customer's machine you have no access to;
it's a race that disappears the moment you attach a debugger (a genuine "Heisenbug," where the act
of observing changes the timing enough to hide the symptom); it lives inside a third-party black
box you can't add logging to; or it's so rare or context-dependent that you can't get it to happen
again on demand at all.

**Why the distinction matters**: for an instrumentable bug, the winning strategy is empirical
iteration — form a cheap hypothesis, add a probe, run it, look at the real data, refine, repeat.
You don't need to be right on the first guess, because the system itself will tell you when you're
wrong, quickly and cheaply. For a non-instrumentable bug, that feedback loop doesn't exist — you're
forced back onto careful, unaided reasoning: reading the code closely, holding several possible
causal chains in your head at once, reasoning about subtle interactions without ever getting to
check your work against reality along the way. It's slower, harder, and far more likely to go
down a wrong path and stay there, because nothing is going to tap you on the shoulder and say "no."

Recognizing which situation you're in early is worth doing deliberately, not something to discover
by accident three hours in. If a bug looks non-instrumentable, the actual first move is often to
*make* it instrumentable — get access to logs, build a smaller reproduction, add tracing ahead of
time — rather than accepting "I can't observe this" and reasoning blind.

## Where AI model choice fits into this

This maps directly onto choosing between a faster/cheaper model and a slower/deeper-reasoning one
for a given piece of debugging work (see also the earlier discussion on Opus vs. Sonnet vs. Haiku
for this project) — and the mapping is the same reason the human strategy above changes with
instrumentability, not a separate consideration:

- **On an instrumentable bug**, the value comes overwhelmingly from *running experiments fast*, not
  from any single reasoning pass being maximally deep. A model that iterates quickly — try
  something, look at the real result, adjust — will typically get there efficiently, because the
  running system is doing a large share of the actual work: correcting wrong turns for you, for
  free, on every loop. This is exactly why the faster, cheaper tier handled this bug well: the
  actual breakthrough came from a screenshot and a null log result, not from a single moment of
  unusually deep reasoning.
- **On a non-instrumentable bug**, there's no such feedback loop to lean on — every reasoning step
  has to be right without external correction, because there's no cheap way to check it against
  reality. This is where paying for deeper, more careful reasoning tends to earn its cost: more of
  the burden sits on getting the reasoning right the first time, since you can't just try it and
  see.

Practically: default to the faster tier for a new bug, and treat "I've tried a few things and I'm
still not narrowing it down" as the actual signal to reach for a deeper-reasoning model or to slow
down and reason more carefully yourself — not the bug's apparent difficulty up front, which is
often impossible to judge accurately before you've actually started poking at it.

## A worked timeline of this specific hunt, for reference

1. Acceptance test failing → traced to a broken assertion (checking the wrong DOM property) →
   fixed the assertion, which revealed the test had never actually been checking anything real.
2. With the assertion fixed, a real failure appeared. Read the code, formed a hypothesis (a
   cache-invalidation race between an effect and a button handler), implemented a more robust fix
   that removed the race by construction, added a regression test, verified locally.
3. Fix didn't hold against the real deployed environment. Ruled out environment
   contamination/reuse by testing against a genuinely fresh environment — still failed.
4. Reproduced locally against a controlled mock — worked fine. Compared the exact interaction
   sequence against the real failing test and found a mismatch (a smaller, single-session version
   vs. the real multi-session sequence) — rebuilt the local repro to match exactly. Still passed
   locally, meaning the mismatch wasn't the explanation either.
5. Added real network-level tracing against the live environment. Found the second network request
   was never being sent at all.
6. Added application-level logging inside the component itself, redeployed, captured the browser
   console during the exact failing sequence. The handler's own first line of logging never
   printed — the click wasn't reaching the handler at all.
7. Took a screenshot at the exact moment of the second click. It showed the previous form field
   still visually focused — Escape had closed its dropdown but not blurred the field itself.
8. Ran one targeted experiment: explicitly click elsewhere before the suspect action. Bug
   disappeared immediately, confirming the theory.
9. Fixed it in the test helper (where the actual defect was — an assumption about what Escape
   does), removed all temporary logging, verified with a clean run, committed.
