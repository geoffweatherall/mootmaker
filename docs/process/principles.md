# Principles and constraints

The things that were previously only in Geoff's head, written down for the first time in August
2026. Everything else in [`process/`](README.md) is downstream of these.

When a decision is hard, work out which principle it turns on and follow that. When two conflict,
the one earlier in this document usually wins.

## What mootmaker is for

**It is a learning project about AI-assisted development, and a portfolio piece.** It is not a
business, and it has no users to let down. That single fact justifies a lot of what follows: the
production environment is a public demo with deliberately weak passwords, its data is disposable,
and shipping something imperfect to production is cheap.

**It should also demonstrate professional judgement.** Which is the counterweight: "it's only a
demo" is not licence for work that would embarrass you in a code review. The point is to show what
good practice looks like when an AI is doing most of the typing.

## Cost

**Scale to zero.** Nothing should cost money while nobody is using it. Every AWS service choice is
made against this: AppSync and Lambda over a running container, DynamoDB on-demand over provisioned
capacity, S3 + CloudFront over a server.

**Free tier first.** Where a free option is adequate, take it. GitHub Actions is free with unlimited
minutes on public repositories, which is why CI has no marginal cost here.

**A long-lived environment must justify itself.** `production` is the only one, and it exists
because a public demo is part of the point. The `test` environment was retired in August 2026
precisely because it could not justify its standing cost. See [environments.md](environments.md).

**Ephemeral means ephemeral.** An environment left running is a direct contradiction of scale to
zero. Four leaked in a single day in August 2026 before anyone noticed — tearing yours down is part
of finishing the work, not a tidy-up.

## The stack

Verified against what is actually deployed, 2026-08-29. Prefer these over introducing something new;
if a new dependency is genuinely better, say why in the design.

| Layer | Choice |
|---|---|
| API | AWS AppSync (GraphQL), Java 25 Lambda handlers |
| Data | DynamoDB, with GSIs rather than table scans |
| Auth | Amazon Cognito, with a `post_confirmation` trigger creating the Person record |
| Web | React 19, TypeScript 6, MUI 9, Apollo Client 4, Vite 8 |
| Hosting | S3 + CloudFront, Route 53, ACM |
| Mail | SES, for sign-up and password-reset flows |
| Infrastructure | Terraform, remote state in a shared S3 bucket, one state key per environment |
| Testing | JUnit, Vitest, Playwright (integration, e2e, and acceptance layers) |
| Orchestration | bash — deploy, undeploy, verify, and environment lifecycle scripts |

**No long-lived credentials anywhere.** Local work uses AWS SSO; anything automated should use OIDC
rather than an access key. The account guardrails in `mootmaker-bootstrap-aws-accounts` exist to
enforce this.

## How much human review the code actually gets

This is the project's position on the "how much vibe coding is acceptable" question, and it is
deliberately an experiment rather than a settled rule. It was written down on 2026-08-29 and is
expected to move as evidence accumulates.

**Always reviewed properly by a human:**

- **The design**, before work starts. This is where the leverage is — a wrong design produces a
  large volume of confidently wrong code.
- **The test cases**, unit and acceptance, after. Tests are the real quality gate, so they are what
  a human should spend attention on.
- **Any diff touching:** authentication and Cognito; persisted data or migrations; IAM and Terraform
  permissions; anything with a cost implication. These share a property — mistakes are expensive,
  hard to reverse, or invisible until they matter.

**Skim-only:** everything else. Read where something looks off. Otherwise the tests, and a green
acceptance run against a real deployed environment, are the gate.

**Why this line and not a stricter one.** Review time does not get cheaper at the same rate code
generation does, so full line-by-line review of everything an AI produces is where the whole
approach stops paying. The bet is that effort spent on design and test quality catches more than the
same effort spent reading implementation code. If that bet turns out to be wrong, the evidence will
be defects reaching production that a code read would plausibly have caught — and this section
should change.

## Testing

**A green acceptance run against a real deployed environment is the definition of working.** Not a
passing unit suite, not a successful deploy. See [`../reference/testing-strategy.md`](../reference/testing-strategy.md)
for how the four layers fit together.

**Verify against reality, not against your own output.** A script exiting zero is not evidence that
the thing it was meant to do happened. Check the resource, the file, the deployed page.

**"It's just flaky" is a hypothesis, not a conclusion.** It is the laziest explanation available,
which is exactly why it deserves the most scrutiny before being accepted.

## Documentation

**Documentation is read by agents, not just people.** That changes the economics: a document that
orients an AI correctly saves tokens and prevents wrong work on every future session, so it earns
its keep far faster than documentation written only for humans.

**Each repository's README is load-bearing** and is kept current deliberately. It is the first
thing to read and the first thing to update.

**A stale document is a defect.** If a change makes a document wrong, fixing it is part of the
change.

**Write down what did not work, not just what did.** The record of "checked this, wasn't it" is as
valuable as the answer — see [`../showcase/debugging-techniques.md`](../showcase/debugging-techniques.md).

## Working with AI

**Let the agent be agentic.** A heavily locked-down setup where AI only suggests code forgoes most
of the available gain. Running tests, deploying, and inspecting real state is where the leverage is.

**Prefer scripts over per-file reasoning** for anything repetitive. A generated diff is reviewable,
repeatable, and far cheaper than reasoning through twenty files.

**The codebase is the style guide.** Claude follows patterns it finds far more reliably than
instructions it is given, so keeping the code consistent matters more than writing conventions down.

**Be tool-agnostic where it is free to be.** Process lives in markdown that any agent can read. See
[ai-collaboration.md](ai-collaboration.md).

## Reversibility

**Prefer changes that are cheap to undo.** Where two approaches are close, take the one that is
easier to back out.

**Archive rather than delete.** Superseded planning docs go to `designs/archive/`; repositories get
archived, not deleted. The account's GitHub token deliberately lacks `delete_repo`.

**Git history is the honest record.** Do not rewrite it to make the story look tidier. The mistakes
are part of what this project is demonstrating.
