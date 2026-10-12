# Glossary

Terms with a specific meaning in Mootmaker, where the general meaning would mislead. Not a dictionary
of software terms.

## The project

**Mootmaker** — the whole system, and the product's name. Also the name of the hub repository.

**The hub** — the `mootmaker` repository: overviews, designs, process, runbooks and tooling. It holds no
deployed code. Every other repository is a **component** repository. See
[repositories](../overview/repositories.md).

**Component** — one of the deployable parts: the API, the web app and demo-data, deployed per
environment, plus the Android app, which is built and published but not deployed.

## Environments and delivery

**Environment** — a complete, isolated copy of the per-environment parts, identified by a name. Any name
works; there is no registry. `production` and `geoff-261012-a1b2` are the same kind of thing.

**`production`** — the public demo at www.mootmaker.com. Changed only by releases.

**`test`** — the release pipeline's rehearsal stage. Changed only by releases, never reset, never used by
hand.

**Ephemeral environment** — one created for a piece of work and destroyed when it is done, named
`<kind>-<YYMMDD>-<rand4>`. Destroyed by the daily **sweep** after 48 hours without a state write, unless
it carries a **KEEP marker**.

**Resource prefix** — every AWS resource name starts with `<environment>-mootmaker`
(`production-mootmaker-resolvers`, `production-mootmaker-webapp-site-...`). What lets environments
share one account.

**Release** — one run of `release.yml` in mootmaker-release: build every component once, tag, deploy
to `test`, smoke test, deploy to `production`, smoke test, publish. A failed one is a **FAILED
prerelease** and its version number is never reused.

**n-1 check** — running the previous release's Android app against the new `test`, because installed
apps are not updated when the API is.

## Testing

**Unit / integration / acceptance / smoke** — the test layers, from no environment at all to the
released build against `test` and `production`. See [testing](../overview/testing.md).

**Green** — the acceptance suite passing against a real deployed environment. The definition of
working.

**Use case** — a numbered requirement in [use-cases.md](use-cases.md), tagged **[All frontends]** or
**[Webapp-specific]**, which tests link back to.

**Fixture users** — three test accounts (admin, standard, and one with no Person) that exist only in
ephemeral environments and are restored by every reset.

**Instrumentable** — a problem where you can attach a probe and watch real state while it fails. Decides
whether to iterate empirically or reason carefully; see
[debugging techniques](../showcase/debugging-techniques.md).

## People and accounts

**Account** — a Cognito user: an email and a password, for signing in.

**Person** — someone who can organise or attend meetings, stored in DynamoDB. Normally linked to an
account; a **guest** Person has none.

**Role** — `standard` or `admin`, held in the account's `custom:class` attribute and carried in its
sign-in token. The Person's `isAdmin` is a display copy.

**Demo account** — `demo@mootmaker.com`, an admin, whose password is shown on the home page so anyone
can try the system.

**Reserved account** — the demo account and the fixture users. They cannot be deleted through the app
and survive a reset.

**Machine client** — a Cognito app client used by a program rather than a person (the test suites,
demo-data), authenticating with the OAuth2 client-credentials flow.

## Data

**Day item** — the one DynamoDB item holding every meeting on one calendar date, with a version number.
See [data](../overview/data.md).

**Pointer** — a small item (`PTR#<meetingId>`) recording which date a meeting is on, so a meeting can be
found by id.

**Booking window** — the dates that can be viewed and booked: from the **retention boundary** (30–37
days back, moved forward weekly by `history-cleanup`) to the **booking horizon** (180 days ahead).

**Meeting version** — a fingerprint of a meeting's editable fields. An edit sends the version it started
from and is refused with `MeetingChanged` if someone else changed the meeting first.

**Workspace query** — `workspace(dates: [...])`, the one query that returns everything a screen needs.

**Broadcast / `daysInvalidated`** — the live-update message: the dates that changed, never the data.
See [concurrent updates](../overview/concurrent-updates.md).

**Reset / repair** — the `database-reset` and `database-repair` Lambdas, run with AWS credentials to wipe
or fix an environment's data.

## Documents

**Design** — a document in `designs/`, written before the work, with a status of Drafting, Ready,
Building or Shipped. Shipped designs move to `designs/archive/`. Only Geoff moves a design to Ready.

**Overview** — a page in `docs/overview/` describing how part of the system works as built.

**Runbook** — a page in `docs/runbooks/` saying what to do about a symptom.
