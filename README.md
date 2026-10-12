# mootmaker

A meeting-room booking system, built almost entirely with [Claude Code](https://claude.com/claude-code)
to find out what AI-assisted development actually changes about the craft.

**[Try it →  www.mootmaker.com](https://www.mootmaker.com)** — a live, public demo. Sign-in details
for a shared demo account are shown on the home page, so there's nothing to set up. There is also a
native **[Android app](https://github.com/geoffweatherall/mootmaker-release/releases/latest)** (an
APK to sideload, attached to each release).

## Why this exists

I have 20+ years of commercial software development behind me, none of it with AI. I picked a
domain complex enough to be honest — real authentication, real scheduling conflicts, real
multi-environment infrastructure — and a stack I'd used commercially for years, so I could judge
the difference rather than guess at it. I started as a sceptic.

The result is a serverless AWS application (GraphQL API on AppSync, Java Lambdas, DynamoDB, Cognito,
a React SPA on CloudFront) with a native Android app beside the web app. It scales to zero, deploys to
any number of independent environments, ships through a release pipeline, and is covered by unit,
integration, and real-deployment acceptance tests.

## What I learned

The short version. The [full write-up](docs/showcase/learnings.md) has the detail, the screenshots,
and Claude's own pushback on my conclusions.

- **Claude follows the patterns it finds in your codebase**, closely enough that detailed
  coding-standard instructions turn out to be largely unnecessary.
- **You can talk to it like a colleague who already knows the codebase** — the terminology
  shortcuts a team develops over years work immediately.
- **You need to be a good tester to be a good developer using AI.** Claude makes mistakes, and
  they're the kind that look plausible. Test quality is where human effort now pays best.
- **[I should vibe more](docs/showcase/learnings.md#i-should-vibe-more)** — but not completely.
  Caring about direction while letting go of syntax seems to be the right trade.
- **Review, not generation, becomes the bottleneck.** Code got cheap; reading and understanding it
  didn't get cheaper at the same rate.
- **[The test pyramid may need rethinking](docs/showcase/learnings.md#impacts-on-the-test-pyramid)**
  when tests are nearly free to write, and the acceptance criteria become the asset worth
  protecting rather than the test code.
- **[Documentation is not just for humans](docs/showcase/learnings.md#documentation-is-not-just-for-humans)**
  any more — it's how an agent orients itself, which changes what's worth writing down.
- **[Flaky tests are worth chasing now](docs/showcase/learnings.md#flaky-tests-are-worth-chasing-now)** —
  AI makes finding the cause cheap enough that "it's just flaky" stops being the rational call. Every
  intermittent failure in this project — seven of them so far — turned out to be a real bug in the
  product.
- **[Cost models age; the rules they justified don't](docs/showcase/learnings.md#cost-models-age-the-rules-they-justified-dont)** —
  "it's just flaky, add a retry" and "use one wildcard certificate" were both correct arithmetic once.
  A rule stated without its cost model is worth re-deriving before trusting.
- **[Hard problems can still need human insight](docs/showcase/learnings.md#solving-tricky-issues-can-still-need-human-insight)**.
  Claude got within one sentence of a Java cold-start fix and couldn't make the final connection
  itself.

There's also a standalone write-up on
[the debugging techniques](docs/showcase/debugging-techniques.md) used to chase down a real race
condition, framed as transferable skills rather than a war story.

And a **code tour of the v2.0.0 rewrite** —
[`docs/showcase/v2-day-keyed-rewrite-tour.html`](docs/showcase/v2-day-keyed-rewrite-tour.html), a
single self-contained page to open in a browser. It walks the change from a developer's side: what
moved, what was deleted rather than adapted, and what shipping it revealed. Its spine is an index of
**fourteen silent failures** — things that compiled, passed, deployed or reported success while being
wrong — with the common shape named at the end. Four of those were found after the release, and two
are in code written to fix the other two.

## The repositories

Eleven repositories rather than one monorepo. `mootmaker`, this one, is the hub: it holds the
documentation that spans the system, and every other repository describes itself in its own README.
See [repositories](docs/overview/repositories.md) for how they fit together.

| Repository | What it is |
|---|---|
| **mootmaker** (here) | The hub: overviews, runbooks, designs, process, and this write-up |
| [mootmaker-api](https://github.com/geoffweatherall/mootmaker-api) | GraphQL API: AppSync, Java 25 Lambdas, DynamoDB, Cognito |
| [mootmaker-webapp](https://github.com/geoffweatherall/mootmaker-webapp) | Web app: React, TypeScript, MUI, Apollo Client |
| [mootmaker-android](https://github.com/geoffweatherall/mootmaker-android) | Android app: Kotlin, Jetpack Compose, Apollo Kotlin |
| [mootmaker-demo-data](https://github.com/geoffweatherall/mootmaker-demo-data) | Keeps every environment populated with realistic demo data |
| [mootmaker-release](https://github.com/geoffweatherall/mootmaker-release) | The release pipeline: build once, test, promote to `test` then `production`, publish the APK |
| [mootmaker-ephemeral-envs](https://github.com/geoffweatherall/mootmaker-ephemeral-envs) | Short-lived environments: create, keep, tear down, and the daily sweep |
| [mootmaker-email-testing](https://github.com/geoffweatherall/mootmaker-email-testing) | Lets tests read real verification emails |
| [mootmaker-domain](https://github.com/geoffweatherall/mootmaker-domain) | DNS and mail identity for `mootmaker.com` |
| [mootmaker-bootstrap-terraform](https://github.com/geoffweatherall/mootmaker-bootstrap-terraform) | The bucket holding every Terraform state file |
| [mootmaker-bootstrap-aws-accounts](https://github.com/geoffweatherall/mootmaker-bootstrap-aws-accounts) | AWS account guardrails, SSO, budgets and the GitHub deploy roles |

## Documentation

| To | Read |
|---|---|
| Understand how it works | [Overviews](docs/overview/), starting with [the system](docs/overview/system.md) |
| Fix something | [Runbooks](docs/runbooks/README.md) |
| Get set up and run it | [Getting started](docs/development/getting-started.md) |
| See how work is done | [Process](docs/process/README.md) and [designs](designs/README.md) |
| Know what it must do | [Use cases](docs/reference/use-cases.md) and [what Mootmaker does](docs/reference/business-functionality.md) |

[docs/README.md](docs/README.md) lists every document. Issues live in the repository they concern and
are gathered on the [Mootmaker board](https://github.com/users/geoffweatherall/projects/1).

## Working on it

Any number of complete, isolated copies of the system can run side by side. Stand up your own, try a
change, and tear it down:

```bash
mootmaker-ephemeral-envs/create-ephemeral-env.sh geoff --with-demo-data    # prints the site URL
mootmaker-ephemeral-envs/teardown-ephemeral-env.sh geoff-261012-a1b2
```

See [getting started](docs/development/getting-started.md) and [delivery](docs/overview/delivery.md).

---

*Built with Claude Code. The commit history is the honest record of how — including the mistakes.*
