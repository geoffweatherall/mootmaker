# Glossary

Terms that mean something specific here, where the general meaning would mislead. Not a dictionary
of software terms.

## Project

**mootmaker** — the whole project: nine repositories, one deployed system. Also the name of the hub
repository, which confusingly contains no deployed code. "The hub" is clearer when the distinction
matters.

**The hub** — the `mootmaker` repository. Designs, process, reference documentation, showcase.

**Satellite repository** — any mootmaker repository other than the hub. Used mostly when talking
about changes that touch many repos at once.

## Environments

**Environment** — a complete, isolated copy of the stack, identified by a name. Not a stage in a
pipeline: there is no registry, and any name works. `production` and `bob-260829-a1b2` are the same
kind of thing.

**Ephemeral environment** — an environment created for one piece of work and destroyed when it is
done. Named `<kind>-<YYMMDD>-<rand4>`. Anything older than 24 hours is a **leak**.

**production** — the public demo at www.mootmaker.com. The only long-lived environment. Its data is
disposable and its passwords are deliberately weak, because it is a demo rather than a business.

**`test`** — a long-lived environment that existed until 2026-08-29, when it was retired. If you find
a reference to it, that reference is stale.

**Resource prefix** — `<environment>-<project>`, from which every AWS resource name derives. What
keeps environments from colliding in one account.

## Documents

**Design** — a document in `designs/`, written before code, carrying a `Status:` of `Drafting`,
`Ready`, `Building` or `Shipped`. Not a diagram or an architecture description.

**Ready** — a design status meaning "build this as written". The one transition only Geoff makes. A
design does not become `Ready` by looking thorough.

**Shipped** — implemented, deployed, and verified against a real environment. Not "code written".

**Reference document** — something in `docs/reference/` describing what is true *today*, updated when
reality changes. Distinct from a design, which describes an intention.

**Hat** — a kind of work, with a role document in `docs/roles/`. One person wears all of them.

## Testing

**Acceptance test** — a Playwright suite in a frontend's `acceptance/` directory, run against a real
deployed environment, derived from the use-case catalogue. Not a unit or mocked test.

**e2e test** — also Playwright against a real deployment, in `e2e/`, but covering flows rather than
catalogued use cases.

**Integration test** — in `webapp/tests/`, against a mocked API. Real browser, fake backend.

**Green** — the acceptance suite passing against a real deployed environment. The project's
definition of working.

**Instrumentable** — a problem where you can attach a probe and observe real state while it fails.
Determines whether to iterate empirically or reason carefully, and therefore which model to use. See
[`../showcase/debugging-techniques.md`](../showcase/debugging-techniques.md).

## Data

**Person** — a DynamoDB record for someone who can attend a meeting. Created automatically by a
Cognito `post_confirmation` trigger. A Person may exist without a Cognito account; a confirmed
Cognito account should always have a Person.

**cognitoSub** — the Cognito user identifier, and the key linking a Cognito account to its Person
record. The join between the two halves of the data model.

**Participant** — a fully derived, materialised record linking a Person to a Meeting. Not a source of
truth: it is rebuilt from meetings, and `database-repair` exists partly to reconcile it.

**Demo account** — the shared account whose credentials are published on the home page, so a visitor
can try the system without signing up. Exists in every environment including production.
