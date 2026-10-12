# Principles and constraints

The constraints everything else in [`process/`](README.md) follows from.

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

Two rules carry equal weight here, and every other cost decision follows from one or the other.
**Scale to zero** governs what *runs*; **nothing accumulates without a bound** governs what *piles
up*. Neither is sufficient alone: a system can idle at zero and still bill more every month.

**Scale to zero.** Nothing should cost money while nobody is using it. Every AWS service choice is
made against this: AppSync and Lambda over a running container, DynamoDB on-demand over provisioned
capacity, S3 + CloudFront over a server.

**Free tier first.** Where a free option is adequate, take it. GitHub Actions is free with unlimited
minutes on public repositories, which is why CI has no marginal cost here.

**A long-lived environment must justify itself.** There are two. `production` exists because a
public demo is part of the point. `test` exists as the release pipeline's rehearsal stage, deployed
to only by that pipeline and never used by hand, because catching a broken release before
`production` is worth its small standing cost. See [delivery](../overview/delivery.md#environments).

**Ephemeral means ephemeral.** An environment left running is a direct contradiction of scale to
zero. Tearing yours down is part of finishing the work, not a tidy-up.

**Nothing accumulates without a bound.** Under steady usage the bill should be *flat*. If usage does
not grow but the bill does, something is accumulating that nobody chose to keep — and that is a
defect, not a cost of doing business.

This is the harder of the two to hold, because nothing announces it. Scale to zero fails loudly — an
idle bill is visible the moment you look. Accumulation fails silently and slowly, and by the time it
is obvious it has been true for months. A thing that costs nothing per hour still costs something per
gigabyte-month forever.

The test is not "is anything expensive" but **"does anything grow with time rather than with usage"**.
Logs, snapshots, published Lambda versions, stored objects, and rows nobody deletes all default to
growing forever unless something is configured to expire them. Every one of them needs an answer to
*what deletes this*, and "nothing" is only acceptable when the thing is genuinely bounded by
something else.

Measured rather than asserted: [cost and scale to zero](../overview/cost-and-scale-to-zero.md) has
the actual bill, what drives it, and the checks that would catch this principle being broken.

Concretely, and as a rule rather than a suggestion:

- **Every CloudWatch log group has a retention period.** No exceptions. AWS's default is "never
  expire", so a group created by anything other than deliberate Terraform/CloudFormation — Lambda
  auto-creates one on a function's first invocation — retains forever unless someone sets it. This
  project uses **120 days**.
- **Every store with a natural lifetime has that lifetime configured**, not left to the default:
  S3 lifecycle rules, CloudWatch metric filters and alarms, ECR image retention, snapshot and
  backup schedules, SQS message retention, DynamoDB TTL where the data is genuinely transient.
- **A resource that outlives what it belonged to is a leak**, even a free one. `terraform destroy`
  removes a Lambda but *not* a log group Lambda created for itself, so such groups pile up unless
  something deletes them. The daily sweep does, and `check-accumulation.sh` fails if one is missed.

**When designing anything new, ask what it leaves behind.** Not just "what does this run" but "what
does this write, where does it go, and what deletes it". If the answer to the last part is nothing,
that is a gap in the design, not an operational detail to sort out later. The
[design section template](../../designs/README.md#section-template) asks this under Technical
considerations for exactly this reason.

## The stack

Prefer these over introducing something new; if a new dependency is genuinely better, say why in the
design.

| Layer | Choice |
|---|---|
| API | AWS AppSync (GraphQL), Java 25 Lambda handlers |
| Data | DynamoDB, with GSIs rather than table scans |
| Auth | Amazon Cognito, with a `post_confirmation` trigger creating the Person record |
| Web | React 19, TypeScript 6, MUI 9, Apollo Client 4, Vite 8 |
| Android | Kotlin, Jetpack Compose, Apollo Kotlin; minimum Android 8.0 |
| Hosting | S3 + CloudFront, Route 53, ACM |
| Mail | SES, for sign-up and password-reset flows |
| Infrastructure | Terraform, remote state in a shared S3 bucket, one state key per environment |
| Testing | JUnit, Vitest, Playwright, Robolectric and Roborazzi, Compose UI tests, Maestro |
| CI and releases | GitHub Actions, AWS access by OIDC only |
| Orchestration | bash — deploy, undeploy, verify, and environment lifecycle scripts |

**No long-lived credentials anywhere.** Local work uses AWS SSO; anything automated should use OIDC
rather than an access key. The account guardrails in `mootmaker-bootstrap-aws-accounts` exist to
enforce this. The one exception is `RELEASE_TAG_PAT`, a fine-grained GitHub token that release tagging
needs because a workflow's own token can only write to its own repository; see
[security](../overview/security.md#github-and-aws).

## How much human review the code actually gets

This is the project's position on the "how much vibe coding is acceptable" question, and it is
deliberately an experiment rather than a settled rule, expected to move as evidence accumulates.

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
passing unit suite, not a successful deploy. See [testing](../overview/testing.md) for how the layers
fit together.

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

**Archive designs; correct or delete everything else.** A shipped or superseded design moves to
`designs/archive/`, where it records why things are the way they are. Any other document or comment
that stops being true is corrected or deleted, not kept for the record: git history keeps the record.
Repositories are archived, not deleted; the account's GitHub token deliberately lacks `delete_repo`.

**Git history is the honest record.** Do not rewrite it to make the story look tidier. The mistakes
are part of what this project is demonstrating.
