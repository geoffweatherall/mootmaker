# mootmaker

A meeting-room booking system, built almost entirely with [Claude Code](https://claude.com/claude-code)
to find out what AI-assisted development actually changes about the craft.

**[Try it →  www.mootmaker.com](https://www.mootmaker.com)** — a live, public demo. Sign-in details
for a shared demo account are shown on the home page, so there's nothing to set up.

## Why this exists

I have 20+ years of commercial software development behind me, none of it with AI. I picked a
domain complex enough to be honest — real authentication, real scheduling conflicts, real
multi-environment infrastructure — and a stack I'd used commercially for years, so I could judge
the difference rather than guess at it. I started as a sceptic.

The result is a serverless AWS application (GraphQL API on AppSync, Java Lambdas, DynamoDB, Cognito,
a React SPA on CloudFront) that scales to zero, deploys to any number of independent environments,
and is covered by unit, integration, and real-deployment acceptance tests.

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
  intermittent failure in this project turned out to be a real bug in the product.
- **[Hard problems can still need human insight](docs/showcase/learnings.md#solving-tricky-issues-can-still-need-human-insight)**.
  Claude got within one sentence of a Java cold-start fix and couldn't make the final connection
  itself.

There's also a standalone write-up on
[the debugging techniques](docs/showcase/debugging-techniques.md) used to chase down a real race
condition, framed as transferable skills rather than a war story.

## The repositories

| Repository | What it is |
|---|---|
| **mootmaker** (here) | The hub: designs, process, reference docs, and this write-up |
| [mootmaker-api](https://github.com/geoffweatherall/mootmaker-api) | GraphQL API — AppSync, Java 25 Lambdas, DynamoDB |
| [mootmaker-webapp](https://github.com/geoffweatherall/mootmaker-webapp) | React SPA — TypeScript, MUI, Apollo Client, Vite |
| [mootmaker-android](https://github.com/geoffweatherall/mootmaker-android) | Native Android app, a second frontend on the same API (not yet started) |
| [mootmaker-demo-data](https://github.com/geoffweatherall/mootmaker-demo-data) | Per-environment Lambda that keeps the demo populated — ships as part of the product |
| [mootmaker-ephemeral-envs](https://github.com/geoffweatherall/mootmaker-ephemeral-envs) | Ephemeral-environment lifecycle scripts |
| [mootmaker-email-testing](https://github.com/geoffweatherall/mootmaker-email-testing) | The persistent SES email-reading pipeline |
| [mootmaker-release](https://github.com/geoffweatherall/mootmaker-release) | Release pipeline that ships `mootmaker-api`/`mootmaker-webapp`/`mootmaker-demo-data` to `test` and `production` |
| [mootmaker-domain](https://github.com/geoffweatherall/mootmaker-domain) | DNS and mail identity for `mootmaker.com` |
| [mootmaker-bootstrap-terraform](https://github.com/geoffweatherall/mootmaker-bootstrap-terraform) | The shared S3 bucket holding Terraform remote state |
| [mootmaker-bootstrap-aws-accounts](https://github.com/geoffweatherall/mootmaker-bootstrap-aws-accounts) | AWS account guardrails — SCPs, IAM Identity Center, billing alerts |

## Documentation

| Where | What's in it |
|---|---|
| [designs/](designs/) | One design document per feature or change, written and reviewed before any code. [The pattern itself](designs/README.md) explains the lifecycle. |
| [docs/development/](docs/development/) | How to get set up and work on mootmaker, including [how environments work](docs/development/environments.md) |
| [docs/reference/](docs/reference/) | [Data model](docs/reference/data-model.md), [testing strategy](docs/reference/testing-strategy.md), [use cases](docs/reference/use-cases.md), and [what the system does](docs/reference/business-functionality.md) for a non-technical reader |
| [docs/showcase/](docs/showcase/) | The learnings write-up, branding, and the marketing material |

Issues are tracked in GitHub, in the repository they concern, and gathered on the
[Mootmaker board](https://github.com/users/geoffweatherall/projects/1).

## Working on it

Every repository deploys independently to a named environment, so you can stand up a complete,
isolated copy of the whole system and tear it down again:

```bash
cd mootmaker-api      && ./deploy.sh bob    # your own environment, any name
cd ../mootmaker-webapp && ./deploy.sh bob   # prints a site URL — open it and try it
```

See [docs/development/environments.md](docs/development/environments.md) for how that works and how
to tear it down, and the [testing strategy](docs/reference/testing-strategy.md) for how the four
test layers fit together.

---

*Built with Claude Code. The commit history is the honest record of how — including the mistakes.*
