# Android app

## Summary

Start building `mootmaker-android`: a native Android app that reaches feature parity with
mootmaker-webapp, using the same GraphQL API and the same Cognito user pool. Day-to-day
development happens in Claude Code **cloud sessions**, paid for from a US$100 cloud-session credit
that **expires on 2026-11-05** and then from the Pro plan. Those sessions build and run JVM-level
tests but cannot run an Android emulator, so emulator tests run in **GitHub Actions**, which is
free for this public repo and has hardware virtualization. The session pushes, Actions runs the
emulator suites, and the session reads the results back and fixes what failed
([the cloud–CI loop](#the-cloudci-loop)). An emulator or a real phone is only for Geoff's hands-on
spot checks. The design also
covers what a third deployable component does to the release pipeline, how the app gets published
for sideloading, and how it is smoke-tested. The path to parity is split into
[eleven milestones](#milestones). Each is a thin vertical slice that ends with a published APK, so
token spend can be paused or paced at any milestone boundary.

This doc offers **options rather than single answers** in several places, at Geoff's request. Each
one is lettered so a reply can be as short as "Q3: B". Geoff last did Android development about ten
years ago, so [Appendix A](#appendix-a--android-in-2026-for-someone-who-last-looked-in-2016)
explains what has changed since then, and terms are explained where they first appear.

## Status

**Ready** — 2026-10-07. Approved by Geoff. All seven blocking questions (Q1–Q7) are answered, and
N3 and N6 are decided. M0 starts once the GitHub and cloud-environment steps under "Before M0" in
the [Implementation checklist](#implementation-checklist) are done.

**Milestone progress:** M0 is done: [mootmaker-android PR #5](https://github.com/geoffweatherall/mootmaker-android/pull/5)
is merged and green on `main`. Its results are under [M0 results](#m0-results-2026-10-06). M1 is
built and green, with a real sign-in proven against an ephemeral environment; the release keystore
is in place and releases publish the APK (v5.10.4 was the first). See [M1 results](#m1-results-2026-10-07).
M2 to M8 are built, green against an ephemeral environment, and merged; each milestone's results are
under it in [Milestones](#milestones). v5.10.6 published the APK with M1 to M7, and v5.10.7 adds M8.

History: first drafted 2026-10-05. Revised 2026-10-07 after checking the draft against the code
and the current cloud-session docs: AWS access from pull requests (Q7), where the signing secrets
have to live, the release tag token's scope, multi-repository cloud sessions, the credit's expiry
date, and the cloud–CI loop.

## Scope / non-goals

**In scope**

- A phone app covering every use case in [`use-cases.md`](../docs/reference/use-cases.md) that
  makes sense on a phone. That is all of it except the webapp-specific parts (see
  [Feature parity](#feature-parity)).
- The same API, schema, Cognito pool and demo user as the webapp. The app is a second frontend,
  not a fork of the backend.
- A development workflow across three places: cloud sessions, GitHub Actions and the laptop.
- The app's own test layers, including emulator acceptance tests against real ephemeral
  environments.
- Joining the app to the release pipeline, smoke tests included.
- Publishing a signed APK somewhere Geoff, or anyone, can sideload it from.

**Non-goals**

- **iOS.** Q1 option B keeps the door open but does not walk through it.
- **Push notifications.** The webapp has none, and they would need Firebase Cloud Messaging plus a
  server-side sender. This is a new feature, not parity.
- **Offline use.** The webapp does not work offline either. The app shows an error state when it
  cannot reach the API, and that is all.
- **Google sign-in.** [`google-sign-in.md`](google-sign-in.md) is a webapp design that hasn't been
  started. Q2 records which auth options make it easier or harder later. Building it is not part of
  this design.
- **Tablets, foldables, Wear OS, Android TV.** A phone layout that is not broken on a tablet is
  enough.
- **Google Play production listing.** Q4 discusses Play, but the default path is sideloading.

## Trade-offs and decisions

These follow from the discussion that led to this doc, or from project rules that already exist.

### 1. Development runs in cloud sessions, with no emulator there

Cloud sessions run on an Anthropic-managed VM: Ubuntu 24.04 on x86_64, 4 vCPUs, 16 GB of RAM and
30 GB of disk, with OpenJDK 21 and Gradle pre-installed. That is plenty for Gradle builds, JVM
unit tests, Robolectric and screenshot tests ([Appendix A](#appendix-a--android-in-2026-for-someone-who-last-looked-in-2016)
explains each). The docs say nothing about nested virtualization (`/dev/kvm`), and the Android
emulator needs that to run at a usable speed, so **the design assumes no emulator in cloud
sessions**. The first checklist item confirms this cheaply. If KVM does turn out to be available,
nothing here gets worse.

According to the docs, the VM itself has no separate compute charge, so the credit pays for
**tokens**, not machine time. claude.ai's Usage page (checked 2026-10-07) describes it as
"Cloud session credits: applies automatically to cloud sessions. After it's used or expires, your
plan's regular usage applies". It is US$100 and **expires 2026-11-05** (8:59 PM NZDT). Laptop
sessions never touch it, and usage credits are switched off, so nothing is ever charged beyond the
plan. The expiry date drives the [pacing](#pacing-summary): credit left on 5 November is lost.

### 2. Emulator tests run in GitHub Actions on Linux runners

`mootmaker-android` is public, so standard GitHub-hosted runners are free with unlimited minutes.
The `ubuntu-*` runners expose KVM; one udev-rule step makes it usable, and
`reactivecircus/android-emulator-runner` boots an emulator inside the job. This is the standard way
to run Android instrumented tests in CI. The macOS (Apple Silicon) runners cannot do this, so the
emulator jobs are Linux-only.

#### The cloud–CI loop

This is how a cloud session works on anything it cannot run itself:

1. The session pushes its branch and opens or updates the PR. `pr-checks.yml` runs on every push.
   Emulator acceptance runs when the session asks for it: it adds the `run-acceptance` label through
   the REST API (`gh api repos/{owner}/{repo}/issues/{n}/labels`; the GitHub proxy blocks most
   GraphQL, which `gh pr edit` uses), or runs `gh workflow run acceptance.yml --ref <branch>`.
   Acceptance runs also need AWS (Q7).
2. The session waits with `gh run watch <run-id> --exit-status`, a single command that blocks until
   the run finishes, so waiting costs almost nothing in tokens. Bash commands that outlive their
   timeout move to the background and report back when they exit, and an acceptance run takes about
   25–30 minutes, including creating the environment. With **auto-fix** turned on for the PR, a
   failed check also arrives as an event that wakes the session if it has gone idle.
3. The session reads why it failed, fixes it, pushes, and goes back to step 2.

What the session can actually read back was checked in M0; see [M0 results](#m0-results-2026-10-06). `gh run view` and the
check-runs API go through `api.github.com`, which the GitHub proxy serves. But the **full job log
and uploaded artifacts** (screenshots, test reports, logcat) are served from GitHub's blob storage
hosts. Those are not on the cloud environment's Trusted allowlist, which includes only `raw.`,
`objects.`, `pkg-npm.` and `release-assets.githubusercontent.com`. So the workflows are written so
that nothing depends on downloading logs or artifacts:

- **Failures are summarised where the API serves them directly.** A final step parses the JUnit
  XML and writes failing test names, assertion messages and the relevant logcat lines into the
  check run's annotations (M0 found the output title and summary come back empty, so annotations
  carry it). `gh api repos/{owner}/{repo}/check-runs/{id}/annotations` returns them as JSON, and
  they are short enough to read without filling context.
- **Artifacts stay for Geoff and for later.** The full reports, screenshots of failures and logcat
  are still uploaded as normal Actions artifacts.
- **If M0 shows the session needs more than the summary,** add the artifact host M0 finds
  (`gh run download` reports which one it was refused) to the environment's Custom allowlist, next
  to `dl.google.com`.

M0 also confirms that a paused VM resumes cleanly when `gh run watch` returns or auto-fix wakes it.
The docs say an idle VM pauses after a few minutes with its files saved.

Screenshot tests (Roborazzi, under Robolectric) run **inside** the cloud session and produce PNGs
it can look at directly. Emulator screenshots of a failure are the only images that come through
CI. Geoff uses an emulator or his phone only for hands-on checks: the
[end-of-milestone two-minute check](#milestones) and anything the CI summary cannot explain.

### 3. The laptop is for hands-on testing, not the main loop

Geoff's laptop has `/dev/kvm` (checked 2026-10-05: 16 cores, 14 GB of RAM), so a local emulator
runs at full speed. It can also install builds onto a real phone over USB or Wi-Fi. That makes it
the place for "does this feel right" testing and for debugging something CI shows but cannot
explain. See [Manual testing](#manual-testing).

### 4. Build once, configure at runtime

The release pipeline promotes **the exact artifact it tested**: [ci-cd-pipeline.md](archive/ci-cd-pipeline.md)
Decision 8. The webapp gets this by writing `env-config.js` after the build. The app does the
equivalent: one signed APK, with the environment chosen **at runtime** rather than compiled in. So
the APK the pipeline tested against an ephemeral environment is the APK that gets smoke-tested
against `test` and then published. The mechanism is under
[Choices you had me make](#choices-you-had-me-make), item 3.

### 5. The API must now stay backward compatible with installed apps

This is the biggest structural change Android brings. When the webapp and API deploy together,
browsers fetch the new webapp on their next load. **An installed APK is not replaced.** Someone who
sideloaded v6.1.0 keeps running it against every later API until they update by hand. So:

- Removing or renaming a schema field, or tightening an argument, breaks installed apps silently,
  even though every suite in the release is green.
- [graphql-schema-sharing.md](archive/graphql-schema-sharing.md) Decisions 5 and NB-4 both named
  "when Android lands" as the trigger for adding `graphql-inspector` breaking-change detection.
  **This design pulls that trigger.**
- The release pipeline gains an **n-1 smoke check**: the *previously published* APK against the
  newly deployed `test` API. See [Release pipeline](#release-pipeline).
- The app should handle unknown enum values and unexpected nulls without crashing. Apollo Kotlin
  generates an `UNKNOWN__` enum case for exactly this.

### 6. Real verification emails come from the shared pipeline, never a Kotlin copy of it

Sign-up and forgot-password tests need real emailed codes. The `mootmaker-email-testing` npm
package already encodes hard-won rules about queue ordering and leaving other tests' messages alone.
mootmaker-release#5 is what happened when a divergent copy existed. So device tests get codes
**through that package, running on the host** (the CI runner or the laptop), not through a Kotlin
port. Q5 covers how a test running on the device reaches it.

### 7. Thin vertical slices, each ending in a published APK

Geoff's stated preference (2026-10-05). Every milestone delivers user-visible functionality **and**
everything needed to ship it: tests at every layer that applies, the release pipeline, smoke tests
and a published APK. Consequences:

- The build/test/publish path is built in the **first** functional milestone (M1), not at the end.
  The early milestones are heavier for this reason, and the later ones are lighter.
- The app is always shippable, and stopping after any milestone leaves something real.
- **The web app covers the gaps.** Users are assumed to have the webapp too, so sign-up and forgot
  password come late (M8). Until a feature exists in the app, it can open the webapp for it (choice
  10).
- The order is constrained by the API, which already exists in full. Every slice uses it as-is, so
  no milestone waits on backend work except M1's small, additive touch points.

## Choices you had me make

None of these were worth blocking on. Each can be overridden cheaply.

1. **File name and placement:** `designs/android-app.md`, following
   [`mootmaker-android/AGENTS.md`](https://github.com/geoffweatherall/mootmaker-android/blob/main/AGENTS.md)'s
   "write a design document before any code".
2. **Application ID `com.mootmaker.android`.** This is the app's permanent identity on every
   device and store, and it cannot change after the first install. It matches the
   `com.mootmaker:mootmaker-schema` Maven group and the owned domain. Debug builds append `.debug`,
   so a debug build and a released build can sit side by side on one phone.
3. **Runtime configuration comes from the webapp's domain.** The webapp's `deploy.sh` already writes
   `env-config.js` with the GraphQL URL, pool ID, client ID and demo credentials. It gains a sibling
   **`mobile-config.json`**, with the same values plus the Android client ID, in plain JSON rather
   than as a JavaScript assignment. The app then:
   - defaults to `https://www.mootmaker.com/mobile-config.json`;
   - for any other environment, fetches `https://www.<env>.mootmaker.com/mobile-config.json`, where
     `<env>` is typed into a hidden developer setting (tap the version number on the About screen
     several times, like Android's own developer options);
   - caches the last good config so a cold start does not depend on it.

   Alternatives considered: compiling the URL in (breaks build-once), and serving config from the
   API stack (AppSync cannot serve static files, so this would mean a new bucket or distribution in
   mootmaker-api). This option couples the app's config to the webapp being deployed, but every
   environment that has the API also has the webapp: `create-ephemeral-env.sh` deploys both, and so
   do `test` and `production`.
4. **A separate Cognito app client for Android** (`aws_cognito_user_pool_client.android`, public,
   no secret), rather than reusing the webapp's. This lets the Android client enable auth flows the
   webapp's does not (Q2), keeps its token lifetimes separate, and makes Cognito metrics show which
   frontend signed in. It is published to SSM as `/mootmaker/<env>/api/cognito/android-client-id`,
   beside the existing `cognito/webapp-client-id` in `published-config.tf`'s `published_config`
   map.
5. **Schema consumption via the npm tarball, not GitHub Packages.** The schema is published to both
   registries. GitHub Packages needs a token **even for public packages**, and a cloud session has
   no GitHub token inside its VM (git credentials stay behind a proxy). `registry.npmjs.org` is
   public and on the cloud session's default allowlist. So a small Gradle task downloads
   `@mootmaker/schema@<pinned version>` and hands `mootmaker.graphql` to Apollo Kotlin's code
   generator. On the laptop, an optional property can point it at the sibling `../mootmaker-api`
   checkout instead, which is what the webapp does. Alternative: use the Maven package with a
   personal access token stored as a cloud-environment variable. It works, but that token would be
   visible to anyone using the environment, and it is one more secret to rotate.
6. **GraphQL client: Apollo Kotlin.** This is the standard choice. It generates Kotlin types from
   the schema (the counterpart of the webapp's `npm run codegen`), has a normalized cache like
   Apollo Client's, and speaks AppSync's WebSocket protocol for subscriptions
   (`AppSyncWsProtocol`).
7. **`versionCode` derived from the release version:** `major × 1,000,000 + minor × 1,000 + patch`.
   Android refuses to install an update whose `versionCode` (an integer) is not higher than the
   installed one. Release numbers only ever increase (failed attempts burn their number), so
   this always increases. `versionName` is the plain `6.1.0` string.
8. **Milestone order** (see [Milestones](#milestones)): sign-in and the home agenda first, then
   the read-only screens, then creating and changing meetings, then live updates, settings, account
   lifecycle and admin. M7–M9 are independent of each other and can be reordered freely.
9. **minSdk 26 (Android 8.0).** This covers effectively every phone still in use and gives native
   `java.time`, which the date handling needs (see Technical considerations). `targetSdk` follows
   the latest stable API level. Non-blocking; raising minSdk later is easy.
10. **Unbuilt features open the webapp.** While parity is incomplete, an entry point for a feature
    the app does not have yet (Add Meeting before M4, Settings before M7, "Create an account" before
    M8) opens the matching `www.<env>.mootmaker.com` page in a Chrome Custom Tab, an in-app browser
    tab. The web session is separate, so the user may have to sign in there too. Alternative: hide
    the entry point until the feature exists. Linking is more honest about what the product can do,
    and each link is deleted when its milestone lands.

## Open questions

### Blocking

Each question lists options and a leaning. The leaning is a recommendation, not a decision. All seven
were answered by Geoff on 2026-10-07, each matching its leaning. Each answer is recorded above its
leaning, which is kept as the reasoning.

#### Q1. What is the app built with?

| | Option | What it means | For | Against |
|---|---|---|---|---|
| **A** | **Native Kotlin + Jetpack Compose** | Kotlin code with Compose for UI (React-like, declarative). The mainstream Android stack in 2026 | What `mootmaker-android`'s README already promises ("native"). Best tooling, docs and Claude familiarity. Robolectric and screenshot tests are mature | Nothing shared with the webapp except the schema. Every screen is written again |
| **B** | Kotlin Multiplatform + Compose Multiplatform | Same as A, but with shared code in a module that could also target iOS later | iOS becomes possible without a rewrite | More build complexity now for an iOS app that is a non-goal. Thinner docs |
| **C** | Trusted Web Activity (TWA) | The existing webapp, wrapped as an installable app running in Chrome without browser UI (Google's Bubblewrap tool generates it) | Parity on day one, for almost no work. The webapp is already mobile-first | Not really an Android app: no native UI, nothing new to show or learn. Needs `assetlinks.json` on the domain |
| **D** | React Native or Capacitor | A JavaScript/React app compiled or wrapped for Android | Could reuse some React logic | A third UI toolkit to learn. MUI components do not carry over to React Native |

**Answered 2026-10-07: A** (native Kotlin + Jetpack Compose).

**Leaning: A.** The project exists to explore building real software with Claude Code, and a
native app is the version of that worth showing. C is worth knowing about as a fallback that costs
almost nothing: it could be shipped in a day if the native app stalls.

#### Q2. How does the app authenticate against Cognito?

Background: the webapp uses `amazon-cognito-identity-js` with the **SRP** flow (Secure Remote
Password, where the password itself never leaves the device). Sign-up, confirmation codes and
password reset are all drawn by the webapp itself, calling Cognito's API directly. The webapp's app
client allows only `ALLOW_USER_SRP_AUTH` and `ALLOW_REFRESH_TOKEN_AUTH`.

| | Option | What it means | For | Against |
|---|---|---|---|---|
| **A** | AWS Amplify Android (Auth category) | AWS's own mobile library. Handles SRP, token storage and refresh | Same SRP flow as the webapp. Maintained by AWS | A large dependency that wants to own configuration (its own JSON format) and pulls in more of Amplify than needed. Runtime environment switching needs care |
| **B** | **Call Cognito's API directly, with a thin Kotlin client** | Cognito's user-pool API is JSON over HTTPS (`InitiateAuth`, `SignUp`, `ConfirmSignUp`, `ForgotPassword`…). Call it with OkHttp or Ktor, implementing SRP, or enabling `USER_PASSWORD_AUTH` on the Android client only | Small and fully under our control. Screens match the webapp's flows exactly. Config switching is trivial | SRP is about 150 lines of careful maths to get right. `USER_PASSWORD_AUTH` avoids that but sends the password to Cognito (over TLS) |
| **C** | Cognito managed login (hosted UI) in a Custom Tab | The app opens Cognito's own sign-in page in a Chrome Custom Tab, then receives tokens via an OAuth redirect (PKCE) back to the app | Least auth code. Makes Google sign-in nearly free later. The user pool already has a domain | Sign-up and reset screens are Cognito's, themed only lightly, so they would not match the webapp. Each environment's pool needs the app's redirect URI registered. Tests have to drive a browser page |

**Answered 2026-10-07: B** (call Cognito's API directly). N1 is still open.

**Leaning: B**, with the SRP versus `USER_PASSWORD_AUTH` choice made at implementation time
(non-blocking N1). It mirrors what the webapp does, keeps the use-case catalogue's sign-up and
reset flows identical across frontends, and is easy to test. C is the better choice if Google
sign-in becomes a priority before the app is finished.

#### Q3. How does the app relate to the release pipeline?

Background: [`release.yml`](https://github.com/geoffweatherall/mootmaker-release/blob/main/.github/workflows/release.yml)
releases api, webapp and demo-data **together under one version**. It builds each once, tests it
against an ephemeral environment, tags all repos, deploys to `test` and smoke-tests it, promotes to
`production` and smoke-tests again, rolls back on failure, and records a GitHub Release. The app
differs in one important way: **there is nothing to deploy**. Releasing it means publishing an APK,
and an APK cannot be rolled back off people's phones.

| | Option | What it means | For | Against |
|---|---|---|---|---|
| **A** | **Fourth component in the bundle** | `build-android` joins the parallel builds; the android repo gets tagged; smoke jobs use the new APK; the APK is published only in `record-outcome`'s success branch | One version number means one thing everywhere. Every API release is proven against the current app. Fits the existing pattern | Emulator flakiness can now fail a whole release, and failed releases burn version numbers. Every API release waits on an Android build, though it runs in parallel |
| **B** | Independent release | `mootmaker-android` has its own release workflow and version line; the bundle doesn't know it exists | Releases decouple. An app fix doesn't need an API release | API releases are no longer checked against the app at all except through the n-1 check, which would then need to live in `release.yml` anyway. Two version lines to explain |
| **C** | Bundled testing, independent publishing | `release.yml` builds and smoke-tests the app every time (protecting it), but publishing an APK is a separate decision | Protects the app on every API change without forcing an app release | The most moving parts. Unclear what "the app's version" means |

**Answered 2026-10-07: A** (fourth bundled component, from M1). M1 stays whole rather than splitting into M1a/M1b.

**Leaning: A, from M1.** Decision 7 puts publishing in the first functional slice, so the app
joins `release.yml` in M1, and every milestone after that ships through an ordinary release. If
Geoff picks B instead, M1 builds `mootmaker-android`'s own release workflow in place of the
`release.yml` changes, and the milestone plan is otherwise unchanged.

Two consequences of A that are easy to miss:

- **The signing secrets live on `mootmaker-release`, not on `mootmaker-android`.** A reusable
  workflow called with `uses:` from another repository sees the **caller's** secrets, never its own
  repository's. So `build-android` passes them explicitly
  (`secrets: { ANDROID_KEYSTORE_BASE64: ..., ... }`), and `release-build.yml` declares them under
  `on.workflow_call.secrets`. The same applies to AWS: the call presents mootmaker-release's OIDC
  subject, which the deploy role already trusts (`github-actions-deploy-role.yaml`), so
  `build-android` needs no trust change.
- **`RELEASE_TAG_PAT` must be widened to `mootmaker-android`.** It is a fine-grained token scoped
  to exactly the repositories `tag` writes to ([ci-cd-pipeline.md](archive/ci-cd-pipeline.md)
  Decision 3). Geoff edits the token's repository list; its value does not change.

#### Q4. Where is the APK published for sideloading?

**Sideloading** means installing an APK from outside an app store. The user downloads the file,
and Android asks once to allow installs from that source (the browser or a file manager). Every
option needs a **release signing key** (see Technical considerations).

| | Option | Cost | For | Against |
|---|---|---|---|---|
| **A** | **Attached to the GitHub Release** that `record-outcome` already creates | Free | Zero new infrastructure. The release record and the binary sit together. **Obtainium** (an open-source app) can watch GitHub Releases and offer updates on the phone | GitHub's release page is a developer-ish place to send a visitor |
| **B** | **A download page on www.mootmaker.com** | Pennies (S3 egress for a ~10–20 MB file) | A clean public link for the README and home page ("Get the Android app") | Something has to put the file there. Simplest is the page linking to option A's asset rather than hosting it |
| **C** | Firebase App Distribution | Free | Testers get an invite and an installer app with update notifications | A Google/Firebase project to set up. Invite-based, so not public |
| **D** | Google Play | US$25 once | The normal way people install apps. Automatic updates. Play manages the signing key | New personal developer accounts must run a closed test with **12+ testers for 14 days** before any production listing. Identity verification. Store listing, privacy policy, data-safety form. Ongoing target-SDK deadlines |
| **E** | F-Droid | Free | The open-source app store | The main repository needs reproducible builds and no proprietary dependencies, and reviews submissions slowly. A self-hosted F-Droid repo is possible but is yet more infrastructure |

**Answered 2026-10-07: A + B** (GitHub Release asset, plus a download page on www.mootmaker.com).

**Leaning: A + B.** Option A is the real distribution channel, and option B is a small page on the
webapp linking to the latest release's APK. D is the right answer if the app ever needs to be
"real" to a non-technical audience. The 12-tester rule is the main thing standing in the way.

**Something to watch: Android developer verification.** Google is introducing a requirement that
apps installed on certified Android devices, sideloaded ones included, are registered to a verified
developer. As of this writing:

- verification opened in March 2026;
- a free **limited-distribution** account for students and hobbyists (email only, up to 20
  devices) launched globally in August 2026;
- enforcement started September 2026 in Brazil, Indonesia, Singapore and Thailand, and rolls out
  globally from 2027;
- installs via `adb`, the development path, are exempt, and there is an "advanced" flow that lets
  people install unverified apps after an extra step.

For NZ this has no effect today. Before 2027, decide between registering the app (likely free,
through the limited-distribution account) and telling people to use the advanced flow. Tracked as
non-blocking N4.

#### Q5. What tool drives the app in device tests?

| | Option | What it means | For | Against |
|---|---|---|---|---|
| **A** | **Compose UI tests / Espresso (instrumented)** | Kotlin tests compiled into a test APK, running on the device alongside the app with access to its internals | The standard. Fast, can wait on app state precisely, same language as the app | To get an email code, a test on the device must reach the host. Solved with a tiny helper on the host that wraps `mootmaker-email-testing`, exposed to the emulator with `adb reverse tcp:PORT tcp:PORT` |
| **B** | **Maestro** | Black-box flows in YAML, run from the host, tapping the UI by visible text, like a person would | Tests the exact release APK without a test build. Host-side, so it can call the npm email client directly. Very readable, close to how the release smoke suite reads | Coarser waiting and assertions. Another tool. Less suited to a large suite |
| **C** | Appium | WebDriver for mobile apps | Familiar to Selenium users | Heavy, slow, and nothing it does is needed here |

Note that the email helper is only needed from **M8** (sign-up and forgot password). M1–M7 sign in
with accounts created through the admin API, so they need no email, and this question can be
answered for M1 without settling the email half.

**Answered 2026-10-07: as leaning** (Compose/Espresso for acceptance, Maestro for release smoke).

**Leaning: A for the acceptance suite, B for release smoke.** Acceptance is large and benefits from
precision. Smoke is about five minutes of black-box clicking on **the exact published artifact**,
which is what Maestro is for, and it is also how the n-1 check runs an *old* APK that has no
matching test APK. Choosing A for both is a coherent simpler alternative: one tool, at the cost of
building and keeping a test APK for every release.

#### Q6. When do emulator acceptance tests run?

Each run needs an ephemeral environment (API plus webapp, so that `mobile-config.json` exists),
which takes about 10 minutes to create and costs real AWS money. The
[cost investigation of October 2026](../docs/reference/running-costs.md) found September's bill was
5× normal, driven by test volume. Each run also fetches one Cognito M2M token (US$0.00225 each)
for the admin API.

| | Option | Feedback | AWS cost |
|---|---|---|---|
| **A** | Every PR push | Fastest | Highest. Every push creates and destroys an environment |
| **B** | **On demand** (a `run-acceptance` PR label or `workflow_dispatch`), plus release time | Quick when wanted | Low |
| **C** | Release time only, which is what the webapp does today | Slowest: breakage found mid-release | Lowest |

**Answered 2026-10-07: B** (on demand by label or dispatch, plus release time).

**Leaning: B.** PR checks always run the free layers (build, lint, unit, Robolectric, screenshot),
so most mistakes are caught without AWS. The label is for PRs that change how the app talks to the
backend. This also fits what [pr-time-smoke-verification.md](pr-time-smoke-verification.md) is
working out for the webapp. If that design lands an approach, Android should follow it rather than
invent a second one.

**A and B both need Q7 answered**: today no pull-request workflow in any repository can create an
environment. Until Q7's change is live, Android acceptance can run only at release time (C), and
the milestones' "green labelled acceptance run" step becomes "green `build-android` in a release".

#### Q7. How do pull-request workflows get AWS access?

Background: the deploy role `mootmaker-release-github-actions-deploy` trusts only these OIDC
subjects ([`github-actions-deploy-role.yaml`](https://github.com/geoffweatherall/mootmaker-bootstrap-aws-accounts/blob/main/workload-account/github-actions-deploy-role.yaml)):
component repositories at `refs/tags/v*`, and mootmaker-release and mootmaker-ephemeral-envs at
`refs/heads/main`. A `pull_request` workflow presents `repo:<owner>/<repo>:pull_request` and is
refused. [pr-time-smoke-verification.md](pr-time-smoke-verification.md) found the same thing on
2026-10-05. Cloud sessions have no AWS credentials either, and should not get any. So **every
emulator run against a real environment happens in Actions**, and before M1's acceptance runs can
happen, something has to trust pull requests.

| | Option | For | Against |
|---|---|---|---|
| **A** | Add `repo:...mootmaker-android:pull_request` (and the webapp's) to the existing deploy role | One line per repository | A PR branch's workflow, which anyone with push access can edit, gets the full deploy role, including `test` and `production` state |
| **B** | **A second, narrower role for PR workflows**, shared with pr-time-smoke-verification | Can be limited to ephemeral resources. Terraform state keys start `<env>/` and resource names `<env>-` (`resource_prefix` in mootmaker-api's `locals.tf`), so `test` and `production` can be denied explicitly | A second policy to keep in step with the first as components gain resources |
| **C** | No PR access; acceptance only at release time (Q6-C) | No security change | Failures show up mid-release and burn version numbers. The cloud–CI loop can't check the backend half of a milestone before merging |

GitHub withholds OIDC tokens from fork PRs by default, so outside contributors get no access under
any option. Push access to these repositories is Geoff's alone (and the cloud sessions acting for
him).

**Answered 2026-10-07: B** (a new, narrower pull-request role, shared with pr-time-smoke-verification).

**Leaning: B**, built once, in `mootmaker-bootstrap-aws-accounts`, by whichever of this design or
pr-time-smoke-verification gets there first. It blocks M1, not M0. M0 needs no AWS.

### Non-blocking

- **N1.** ~~SRP versus `USER_PASSWORD_AUTH` on the Android client, if Q2 is B.~~ **Decided in M1: SRP.**
- **N2.** ~~Per-frontend tags in `use-cases.md`~~ **Already done.** Every case is tagged
  **[All frontends]** (119) or **[Webapp-specific]** (18), and carries an "android: not yet
  automated" slot for its Android test-case link. `mootmaker-android/AGENTS.md`'s note that this
  still needs untangling is out of date and gets corrected in M0. What's left is minor: some
  [All frontends] cases describe browser behaviour (URLs as state, tab visibility) that needs an
  Android reading. Decide case by case as each milestone reaches them.
- **N3.** A parity rule going forward: once Android has parity, does a new feature count as done
  only when both frontends have it, or can Android lag? **Decided 2026-10-07: Android may lag**,
  tracked as an issue in `mootmaker-android` per feature.
- **N4.** Developer verification before global enforcement in 2027 (see Q4).
- **N5.** Android App Links: tapping `https://www.mootmaker.com/meetings/<id>` on a phone opens the
  app. Needs `/.well-known/assetlinks.json` on the webapp's domain. Nice later, not parity.
- **N6.** Which cloud-session model per milestone. **Decided 2026-10-07: Sonnet by default, Opus
  for auth, caching and subscriptions**, to make the credit last. See
  [Using the cloud credit](#using-the-cloud-credit-well).

## Feature parity

Mapped against the webapp's routes (`webapp/src/App.tsx`) and the use-case catalogue's sections.

| Webapp | Use cases | Android | Milestone |
|---|---|---|---|
| `/signin`, sign out | B | Sign-in screen; sign-out in the menu | M1 |
| `/signup` | A | Sign-up plus verification-code screen | M8 |
| `/forgot-password` | C | Same two-step flow | M8 |
| `/` home, with demo login pre-filled | D | Home; demo credentials pre-filled from `mobile-config.json`, as on the web; Today/Tomorrow agenda | M1 (agenda), M5 (Needs your response) |
| `/rooms/:date/availability` | E | Room availability, day by day | M2 |
| `/persons/:personId/calendar` | G | Person calendar | M3 |
| `/meetings/:meetingId` | H | Meeting details | M3 |
| `/meetings/add`, `/meetings/:id/edit` | F, O | Add (M4), edit and cancel (M5) meeting; room suggestion | M4–M5 |
| Attendee response | (attendee-response-status) | Going / Maybe / Not going control | M5 |
| `/settings`: name, date/time format, avatar, delete account | I, N | Settings screen; avatar via the Android **Photo Picker** (no storage permission needed); delete account in M8 | M7 |
| `/rooms`, `/persons` (admin) | J, K, P, Q | Admin screens behind the same `custom:class` check as `RequireAdmin` | M9 |
| Live updates (`daysInvalidated` subscription) | M | AppSync subscription while the app is in the foreground | M6 |
| Authorization boundaries | L | Enforced server-side already; app tests mirror the web's | M1–M9 |
| `/about` | — | About screen with version, licences, and the hidden environment switcher | M1 |

Webapp-specific: browser-only behaviour in section M (tab visibility, URLs as state) has a
counterpart (app foreground/background, the back stack), but the tests are written differently.

## Milestones

Eleven milestones from nothing to parity. **Each one is a thin vertical slice:** user functionality
plus its unit, integration and screenshot tests, its acceptance cases on an emulator against a real
ephemeral environment, any smoke-test change, and a release that publishes the APK. Stopping after
any milestone leaves a working, published app that covers everything up to that point, with the
webapp covering the rest.

**Sizes** are rough, so Geoff can pace spending. They will be recalibrated after M1:

| Size | Roughly |
|---|---|
| **S** | One cloud session |
| **M** | Two or three sessions |
| **L** | Four to six sessions |

**Every milestone ends the same way** ("done" for a milestone):

1. PR checks green: build, lint, unit, Robolectric, screenshots.
2. A green labelled acceptance run on an emulator against an ephemeral environment, covering the
   milestone's use cases. Until Q7's role exists, this is the acceptance suite inside a release's
   `build-android` job instead.
3. The `android:` slot of each covered case in `use-cases.md` links to its Android test case.
4. A release that publishes the APK, with smoke tests green (from M1 on).
5. Geoff installs the published APK on his phone and tries the new slice. It's a two-minute check
   and the cheapest UX review there is.
6. A spend check: a line in this doc recording roughly what the milestone used, so the next
   milestone's estimate gets better.

### M0 — Toolchain spike · S · no user functionality

The one milestone that is not a vertical slice. It exists to find out cheaply whether the cloud plus
Actions approach works before spending on anything else.

- **Cloud session:** check `/dev/kvm`, `nproc`, `free -g`, and that `dl.google.com` and
  `registry.npmjs.org` are reachable. Write `scripts/cloud-setup.sh` and time it under 5 minutes,
  including the Gradle warm-up (there are no hooks in a two-repository session).
- **The cloud–CI loop**, end to end: push, `gh run watch` until the emulator job finishes, read its
  result through `gh run view` and the check-runs API, then try `gh run view --log-failed` and
  `gh run download` and record which hosts they are refused. Deliberately break the trivial test
  once to prove that a failure summary reaches the session and auto-fix wakes it. Record what works
  under [the cloud–CI loop](#the-cloudci-loop).
- **App:** an empty Compose app, with Apollo Kotlin generating types from the npm-tarball schema
  (proves codegen without using it yet).
- **CI:** `pr-checks.yml` (build, lint, one unit test, one Robolectric test, one screenshot) and an
  emulator job running one trivial instrumented test (proves KVM in Actions).
- **Docs:** fix `mootmaker-android`'s README and AGENTS.md (the placeholder text and the stale N2
  note).
- **Exit:** PR checks and the emulator job are green on `main`. Nothing is published.

### M0 results (2026-10-06)

**Status:** done. [mootmaker-android PR #5](https://github.com/geoffweatherall/mootmaker-android/pull/5)
merged and is green on `main`. Nothing is published. Build job 3m32s, emulator job 4m22s on the last commit.

**Spend:** read from claude.ai's Usage page on 2026-10-07 (Geoff). The $100 included cloud-session
credit (expires 8:59 PM GMT+13 on 5 November) still showed **$100 of $100 left**, so M0 drew nothing
from it. A separate **Project setup credit** showed **4% used** and expires on 2026-10-08; its size
isn't shown, so 4% can't be converted to dollars. The M0 sessions ran on Sonnet 5.5. No projection to
5 November is possible from this: M0 used none of the $100, and the first real rate comes after M1.
The page may lag, and the 4% may include other use, so treat both figures as approximate.

**Versions that worked:** AGP 8.10.1, Kotlin 2.1.21, Gradle 8.14.3, Compose BOM 2025.05.01, Apollo
Kotlin 4.3.1, Robolectric 4.14.1, Roborazzi 1.43.0, compileSdk/targetSdk 35, minSdk 26. Apollo
codegen runs from the `@mootmaker/schema@6.2.0` npm tarball through a small `fetchSchema` Gradle
task. Gradle needs JDK 21 in the cloud session (a `jvmToolchain(17)` fails: no toolchain download
repository); CI uses Temurin 21.

**Cloud session probe**

| | |
|---|---|
| `/dev/kvm` | absent, as expected: emulators run only in Actions |
| `nproc` | 4 |
| Memory | 15 GB, no swap |
| Disk | 252 GB volume, about 30 GB free |
| Preinstalled | JDK 21, Gradle 8.14.3, Node 22, gh 2.89.0. No Android SDK, `ANDROID_HOME` unset |

**Host reachability from the session**

| Host | Result |
|---|---|
| `dl.google.com` | reachable (cmdline-tools, SDK packages) |
| `registry.npmjs.org` | reachable |
| `services.gradle.org`, `plugins.gradle.org` | reachable |
| `maven.google.com` | 301, works for Gradle |
| `repo.maven.apache.org` | reachable, but **intermittent 429 Too Many Requests** under parallel resolution on a cold cache |
| `api.github.com` | reachable via `gh api` |

The 429s failed the first build four times running. With `--max-workers=1` and retries it
resolves, because Gradle caches what it has already fetched. The setup script retries its warm-up
up to five times.

**Setup-script timing** (`scripts/cloud-setup.sh` in mootmaker-android): SDK install alone 13 s. A
cold run including the Gradle warm-up (`assembleDebug assembleDebugUnitTest lintDebug`, single
worker, empty Gradle home) **3m56s**, under the 5-minute target. Caveat: timed inside an
already-running session, not as the environment's setup-script phase. The warm-up runs only if
`gradlew` sits next to the script, so pasted into the environment's setup field it installs the SDK
and skips the warm-up.

**What the cloud–CI loop could and could not read**

| Works | Refused |
|---|---|
| `git push` triggering `pr-checks.yml` | `gh run view --log`, `--log-failed`: Forbidden from `results-receiver.actions.githubusercontent.com` |
| `gh run list`, `gh run watch <id> --exit-status`, `gh run view <id>` | `gh api .../actions/jobs/{id}/logs`: Forbidden from `productionresultssa9.blob.core.windows.net` |
| `gh api repos/{o}/{r}/commits/{sha}/check-runs` and `.../check-runs/{id}/annotations` | `gh run download`: Forbidden, same blob host (the artifacts API lists them fine) |
| GitHub MCP `get_job_logs` (see below) | |

- **A failure summary reaches the session through annotations.** Deliberately breaking
  `GreetingTest` produced a `failure` annotation reading
  `com.mootmaker.app.GreetingTest.greetingNamesTheApp: org.junit.ComparisonFailure: expected:<Moot[]> but was:<Moot[maker]>`,
  written by `.github/scripts/summarise-failures.py` (JUnit XML to `::error` annotations). The
  check run's `output.title` and summary are empty; **the annotations carry the content**, and the
  [loop description](#the-cloudci-loop) above now says so.
- **`get_job_logs` is a workaround**, not a verified one: it returned log content for a failed run
  with `failed_only` and a tail, but was tried only with `tail_lines=5`, so its size limits are
  unknown.
- **Blob-storage hosts are not allowlisted.** The two refused hosts above are what to add to the
  environment's Custom allowlist if annotations prove not enough. M0 did not need them.
- `gh auth status` reports the token invalid, yet `gh api` and `gh run` work through the proxy.

**Not proven in M0**, so still open for M1:
- **Auto-fix wake.** The session was blocked inside `gh run watch` during the deliberate failure,
  so whether a failed check wakes an idle session is untested.
- **Paused-VM resume** after `gh run watch` returns.
- **The `run-acceptance` label and `gh workflow run`**: there is no acceptance workflow yet.

### M1 results (2026-10-07)

**Status:** built and green; **not yet exited.** The exit criterion also needs the first APK on a GitHub
Release and Geoff signed in on his phone, which waits on Geoff creating the release keystore.
[mootmaker-android PR #6](https://github.com/geoffweatherall/mootmaker-android/pull/6) is merged (CI: build 3m15s,
emulator 5m07s, 3 emulator tests, 43 data and 24 app JVM tests, none skipped). Pipeline changes are in
mootmaker-release PRs #76 and #77. The backend touch points (api#106, webapp#161) are merged and went out in release v5.10.x.

**Proven against a real environment:** an ephemeral environment signed in through the Android Cognito client after reading
its own `mobile-config.json` (3 emulator tests, 0 failed). The acceptance suite (B.7, B.9, B.10, B.13, D.22, D.23, D.24;
B.14 and B.15 are web routes, so not automated) passed 6/6 on the release build against a second ephemeral environment.
Both were torn down.

**Left for Geoff:** create the keystore and add it as four secrets on mootmaker-release (`ANDROID_KEYSTORE_BASE64`,
`ANDROID_KEYSTORE_PASSWORD`, `ANDROID_KEY_ALIAS`, `ANDROID_KEY_PASSWORD`), back it up offline, add mootmaker-android to
`RELEASE_TAG_PAT`, run a release, and sign in on his phone. Until the secret exists every Android release stage skips, so
releases still ship the backend.

**Spend:** unknown. Geoff was away, so the Usage page wasn't read. M1 ran on Opus (approved by Geoff), which spends credit
faster than Sonnet. To fill in: read the $100 credit (expires 5 November) and the project setup credit from the Usage page,
then project to 5 November as the checklist asks.

**Decisions taken while building**

- **N1 decided: SRP** (`USER_SRP_AUTH`), as the webapp does. The Android client needs only `ALLOW_USER_SRP_AUTH` and
  `ALLOW_REFRESH_TOKEN_AUTH`. `SrpTest` pins values produced by `amazon-cognito-identity-js` 6.x, and a real SRP sign-in to
  production's pool passed.
- **Application id is `com.mootmaker.android`** (`.debug` on debug builds), per choice 2. M0 had used `com.mootmaker.app`;
  the Kotlin namespace stays `com.mootmaker.app`.
- **Modules `app`, `data`, `testing`.** `testing` holds `FakeBackend`, an OkHttp interceptor serving mobile-config.json,
  Cognito and GraphQL to Robolectric and the emulator alike. The host-side email helper (Q5-A) isn't built; M8 needs it.
- **No custom scalar adapter.** Schema 6.2.0 types `startTime`/`endTime` as `String`; times are parsed as `LocalDateTime`
  where formatted, never as Instant.
- **Acceptance and release pipeline.** `acceptance.yml` runs on a PR labelled `run-acceptance` (it must be a `pull_request`
  event, since the ephemeral AWS role trusts only that). It calls `release-build.yml`, which builds and signs the release APK
  once (versionCode = major*1e6 + minor*1e3 + patch), creates an environment, resets its database to create fixture users,
  runs the suite against the release build, tears down, and uploads the APK with its SHA-256. `smoke.yml` runs a Maestro demo
  sign-in.
- **Screenshots are verified in CI** (`verifyRoborazziDebug`); PNGs rendered in the cloud matched CI's first time.
- **Demo-user e2e** reads `https://www.<env>.mootmaker.com/mobile-config.json`, falling back to `env-config.js`, and
  annotates which it used. Switching environment now refills that environment's demo login.
- **Android 12+ doesn't finish a root activity on Back**, so tests check "no longer resumed".
- CI writes compile errors and Gradle failures as annotations and counts skipped tests, so green can't hide a skip.

**`mobile-config.json` contract:** `GRAPHQL_API_URL`, `COGNITO_USER_POOL_ID`, `COGNITO_CLIENT_ID` (webapp),
`COGNITO_ANDROID_CLIENT_ID`, and optional `DEMO_USER_EMAIL` / `DEMO_USER_PASSWORD`. The app requires the GraphQL URL (https),
the pool id and the Android client id, and ignores unknown keys.

**Cloud loop findings**

- The setup script took 8m46s (Maven Central 429s forced five Gradle warm-up attempts), over the 5-minute snapshot target.
  M0 measured 3m56s.
- `www.mootmaker.com` isn't reachable from the cloud session (proxy 403), so config fetches are exercised only in CI or on a phone.
- `get_job_logs` with `job_id`, `return_content` and `tail_lines=120` returns a passing job's tail too. `gh run watch` blocks
  about 5 minutes and returns cleanly.

### M1 — Sign in and see your day · L · use cases B, D.22–D.24

The walking skeleton: thin on features, but every layer of the build/test/publish path exists by
the end of it.

- **User sees:**
  - A sign-in screen with the demo credentials pre-filled, as on the web.
  - A home screen with your name and the **Today/Tomorrow agenda**. Rows are not tappable yet;
    meeting details come in M3.
  - Sign out.
  - An About screen with the version and the hidden environment switcher.
  - "Create an account" and other unbuilt entry points open the webapp (choice 10).
- **App:** config loader (`mobile-config.json`, cached, switchable), Cognito client (Q2), encrypted
  token storage and refresh, Apollo client (the schema types times as `String`, so there is no scalar adapter; see [M1 results](#m1-results-2026-10-07)), the
  `workspace { me days }` query, navigation, Material 3 theme in mootmaker's colours.
- **Backend (separate sessions in those repos):**
  - `mootmaker-api`: Android Cognito client plus SSM parameter, and the `graphql-inspector` PR check.
  - `mootmaker-webapp`: `mobile-config.json` in `deploy.sh`.
  - Both are additive and released in the same release as the first APK.
- **Tests:**
  - Unit: config parsing, date formatting, error mapping.
  - Robolectric: sign-in validation and error states, agenda empty state (D.23), the no-linked-Person
    message (D.24).
  - Screenshots: sign-in, home with data, home empty.
  - Acceptance: B and D.22–24, against an ephemeral environment with accounts created through the
    admin API.
  - e2e: config fetch, real Cognito sign-in, a real query.
- **Pipeline and publish:**
  - Geoff creates the keystore.
  - `acceptance.yml` (labelled), `release-build.yml`, and the `release.yml` changes (Q3).
  - Maestro smoke for `test` and `production`: demo sign-in, then the agenda renders.
  - The APK is attached to the GitHub Release, labelled "preview".
- **Exit:** the per-milestone checklist above. The first APK is on a GitHub Release, and Geoff has
  signed in to production with it on his phone.
- **Can be split** if Geoff wants a smaller first bite:
  - **M1a**: everything except the release integration. Ends with an APK installable from a CI
    artifact, but not yet published.
  - **M1b**: keystore, `release-build.yml`, `release.yml`, smoke, publish.

  M1a alone bends the vertical-slice rule, which is why the default is to keep them together.

### M2 — Room availability · M · use cases E (10), D.25

- **User sees:** "Room availability today" from home; a day-by-day view of every room's bookings in
  room colours; moving between days; times shown in the user's chosen date/time format (read-only
  here, editable in M7).
- **Tests:** room-colour fallback and availability layout logic as unit tests (ported cases from
  `roomAvailabilityLogic.test.ts`), plus screens under Robolectric with screenshots, and acceptance
  for E.
- **Pipeline:** smoke flows add "availability renders". **The n-1 smoke check starts here**, the
  first release where a previous APK exists.
- **Publish extra:** the download page on www.mootmaker.com (Q4-B), if chosen. It's small and worth
  having before the app is shown to anyone.
- **Built (2026-10-07), as it differs from the plan:**
  - No backend change: one `workspace { me rooms days boundaries }` query for one day. The day
    navigation is bounded by `boundaries` (earliest retained to latest bookable), as the webapp's is.
  - The status, timeline and room-colour logic is a Kotlin port of `roomAvailabilityLogic.ts`, with
    its test cases ported alongside. Times stay naive `LocalDateTime` strings.
  - Date jump uses the Material 3 date picker; Add meeting still opens the webapp until M4, and
    booking rows are not tappable until M3 (E.32's navigation half moves to M3).
  - Acceptance covers D.25, E.26–E.28 and E.31–E.34 (passed against an ephemeral environment; the run's one failure was M1's D.22 order check, a test bug fixed in mootmaker-android#8). E.29 (the picker) and E.30 (no rooms, which an
    environment with other cases' rooms can't show) are Robolectric-only. E.35 and E.36 are
    webapp-specific.
  - Still to do: the smoke flow's "availability renders" step and the n-1 smoke check, which need
    the first published APK (the keystore).

### M3 — Meeting details and person calendar · M · use cases H (6), G (7)

- **User sees:** tapping an agenda row or an availability booking opens meeting details. A person's
  calendar opens from meeting details or the menu ("my calendar").
- **Notes:** the first real navigation graph with arguments. Back-stack behaviour gets an Android
  reading of the use cases about URL state.
- **Built (2026-10-07), as it differs from the plan:**
  - No backend change. Two new queries: `MeetingDetails` (`meeting(id)` plus `workspace { me rooms }`,
    the rooms only for the room's colour) and `PersonCalendar` (`workspace(dates)` for the five
    working days, with `people`, `rooms` and `boundaries`). Meetings are filtered to the person on the
    device, as the webapp does.
  - Agenda rows and room-card bookings open meeting details. "Calendar" on home opens your own week
    (the webapp link is gone). A person's name on a meeting opens that person's calendar.
  - The calendar is Monday to Friday of one week, with a person dropdown, Previous/Next/This week
    bounded by `workspace.boundaries`, and rows that open the meeting. Switching person stays on the
    same screen, so Back leaves the calendar rather than stepping through people.
  - Meeting details shows the room (with its colour), the date once in the viewer's format, the time as
    a range, the organiser and each attendee's response, with "You" on the caller's own row, and a
    Share action that hands the system share sheet the webapp's meeting link. Avatars are initials
    until M7. The attendee response control, Edit and Cancel are M5.
  - Verified: pr-checks and the labelled acceptance run are green on mootmaker-android#9 (merged
    2e06191), against an ephemeral environment that the run created and tore down. The first
    acceptance run's two failures were one test-ordering mistake in the new H.70 case (another case's
    room sorted ahead of its room) and M2's D.22 order check, already fixed by #8. Covered by
    acceptance: G.59, G.60, G.62, G.63, G.65, G.67, H.68 to H.71. Robolectric-only: G.64 and H.73
    (no way to stage them against a real environment). Webapp-specific: G.61, G.66, H.72.
  - **Spend:** not visible from inside a session; read it from claude.ai's Usage page. Sonnet, and
    one cycle of find-and-fix, so about the same as M2.
  - Still to do: the smoke flow's "meeting details open" step, with the rest of the smoke work that
    waits on the first published APK.
  - Back-stack: details and calendars are plain pushed destinations, so Back retraces the path taken
    (home, calendar, meeting, calendar of the organiser, and so on). There is no URL state to
    reproduce, so the use cases about browser history have no Android counterpart.

### M4 — Add a meeting · L · use cases F (19)

The largest functional slice: the most use cases, and the first write.

- **User sees:** Add Meeting from home and availability, with date and time pickers, attendee
  picker, capacity, **room suggestion** (`suggestRoom`) and validation errors mapped from
  `MeetingError`. On success, the user lands on the new meeting's details.
- **Tests:** add-meeting validation as unit tests (ported cases from `addMeetingLogic.test.ts`), the
  form under Robolectric, acceptance for F.
- **Pipeline:** the `test`-stage smoke flow creates a meeting and reads it back, using a room
  created over the admin API as the webapp smoke suite does (mootmaker-release#64). Production
  smoke stays read-only.
- **Could split** into M4a (create with a manually picked room) and M4b (room suggestion and the
  rest of F's edge cases) if spend needs pacing.
- **Built (2026-10-07), as it differs from the plan:**
  - No API or webapp change, so no release. New operations: `MeetingForm` (`workspace { me people
    rooms }`), `SuggestRoom` and the `CreateMeeting` mutation. A rejected booking is a successful
    response with `errors`, and the app words each `MeetingError` as the webapp does, all in one banner.
  - Add meeting opens the native form from home and from room availability (which passes the viewed
    date, E.37); the webapp link is gone. The form: subject, organiser (defaults to you), attendees,
    date (Material 3 date picker), start and end, room, and Suggest a room. Saving replaces the form with
    the new meeting's details, so Back returns to where Add was opened, and shows a toast.
  - **Times are chosen from a menu of the 96 quarter hours**, not a clock dial. That makes F.41 true by
    construction and avoids the webapp's snapping workaround; the cost is a long list. Start and end
    default as the webapp does (next boundary, an hour, clamped before midnight).
  - The form's logic is ported from `addMeetingLogic.ts` into `data` (organiser/attendee exclusivity,
    the suggested-room cache and its key, default times). Edit mode, same-room priority and
    `excludingMeetingId` are M5.
  - Verified: pr-checks and the labelled acceptance run are green on mootmaker-android#10 (merged
    854cf49), against an ephemeral environment the run created and tore down. Acceptance covers F.38,
    F.39, F.44, F.46, F.47, F.49, F.50, F.51, F.53 and F.55. Unit-tested only: F.40, F.41, F.54, F.56.
    Robolectric flow: F.52. Not covered: F.45 (the form can't pick the organiser as an attendee) and
    F.42 (the API rule exists, so it is shown as the server words it). Webapp-specific: F.57, F.58.
  - **Find-and-fix:** the first acceptance run failed because the form is taller than an emulator
    screen and the cases tapped controls below the fold (use `performScrollTo`), and because the rooms
    these cases created sorted ahead of the `A-` rooms other cases look for, pushing them off the lazy
    list (name new rooms `Z-`). Separately, `AppFlowTest` and the availability order acceptance case
    booked meetings at fixed hours and failed whenever the suite ran during that hour; both now avoid
    the current hour.
  - **Spend:** not visible from inside a session; read it from claude.ai's Usage page. Sonnet, three
    rounds of find-and-fix.
  - Still to do: the `test`-stage smoke step that creates a meeting and reads it back needs a
    mootmaker-release change (a room created over the admin API, as mootmaker-release#64 does for the
    webapp); production smoke stays read-only. Deferred, with the other smoke work.

### M5 — Edit, cancel and respond · M · use cases O (12), D.107, attendee response

- **User sees:** edit and cancel your own meetings; Going/Maybe/Not going on meetings you're invited
  to; the home screen's "Needs your response" section.
- **Notes:** reuses M4's form for editing. The meeting-version conflict handling
  (`meetingVersion.ts` in the webapp) needs the same behaviour here.
- **Built (2026-10-07), as it differs from the plan:**
  - No backend or webapp change, so no release. New operations: `EditMeeting` (the meeting with its
    `version`), `UpdateMeeting`, `CancelMeeting`, `RespondToMeeting`; `SuggestRoom` now sends
    `excludingMeetingId` when editing. Home asks for three days and its agenda rows gain the viewer's
    own response.
  - Edit is M4's form, opened on the meeting. It sends `expectedVersion`, so a save from a stale copy
    comes back `MeetingChanged` and the form shows the server's words. Edit and Cancel are icons on the
    details, shown to the organiser or an admin (`custom:class` in the ID token); the API enforces it
    regardless. Cancel asks first, naming the meeting; a meeting already gone shows "no longer exists".
  - An attendee answers Going / Maybe / Not going on the details ("Your response") and from home's
    "Needs your response" cards, which name the range they cover and can "Search further ahead" in steps
    of three days. The organiser has no control.
  - Verified: pr-checks and the labelled acceptance run are green on mootmaker-android#12 (merged
    b621b7a), against an ephemeral environment the run created and tore down. Acceptance covers D.107,
    H.108, O.112 to O.115, O.117 to O.119. Robolectric flows (`EditCancelRespondFlowTest`) cover the same
    plus the stale-version refusal. Not automated: O.116 (the app cannot send that request), O.120 (no
    timing rule exists to test), O.121 (date change) and O.113's suggest-a-room half (unit-tested).
  - **Find-and-fix:** home became a longer lazy list, so older acceptance cases that tap an agenda row
    or check the entry points broke twice: rows below the fold are not composed (use
    `scrollHomeTo`), and home keeps its scroll position after Back. Two rounds, Sonnet.
  - **Spend:** not visible from inside a session; read it from claude.ai's Usage page.
  - Still to do: live responses on an open details screen (O/M.111) arrive with M6.

### M6 — Live updates · M · use cases M (live-update cases)

- **User sees:** a meeting someone else books appears without refreshing, while the app is open.
- **App:** AppSync subscription tied to the foreground lifecycle, invalidating everything held on
  reconnect or return to the foreground (Technical considerations). This is also where the
  webapp's Day-cache behaviour is ported deliberately.
- **Tests:** acceptance makes a change over the API and asserts the app shows it without user
  action. That's the Android counterpart of `live-updates.spec.ts`.
- **Can move** anywhere after M4. Before M4 there is little in the app that changes.
- **Built (2026-10-07), as it differs from the plan:**
  - No backend or webapp change. A hand-rolled AppSync realtime client (`AppSyncRealtime`, the twin of
    `appsyncSocket.ts`: AppSync refuses `graphql-transport-ws`, so Apollo cannot carry it) feeds
    `AppContainer.liveEvents`. It runs only while the app is signed in and STARTED, so leaving the
    foreground closes the socket. It reconnects with backoff and a fresh ID token each time.
  - **Decision: no normalized cache.** Every screen already refetches when it becomes visible, so the
    Android form of the webapp's evict-and-refetch is "refetch the open screen". Home, availability,
    calendar and meeting details refetch on a `daysInvalidated` broadcast and on every `start_ack`.
    The `start_ack` refetch is sent on the first connection too, because a screen loads a moment before
    the socket is up and AppSync does not replay. Broadcast dates are not used to filter: the refetch is
    cheap, and a filter is where the webapp's own-write and date-matching bugs lived.
  - The in-flight race is handled on home and meeting details: a broadcast during a load queues exactly
    one more load, so stale data landing after the broadcast is never left standing.
  - Verified: pr-checks and the labelled acceptance run are green on mootmaker-android#13 (merged
    6515d76), against an ephemeral environment the run created and tore down. Acceptance
    (`LiveUpdatesAcceptanceTest`) makes each change through the API as a second user and touches nothing
    in the app afterwards: a booking appearing on home, an edit then a cancellation reaching an open
    meeting (O.122, O.123), an attendee's response reaching an open meeting (M.111). Unit tests run the
    protocol against MockWebServer; Robolectric flows use a fake channel.
  - **Find-and-fix:** one round. The instrumented app-flow test uses a fake HTTP backend that cannot play
    a WebSocket upgrade, so the real channel crashed it; it now runs with the channel off.
  - **Spend:** not visible from inside a session; read it from claude.ai's Usage page. Sonnet.
  - Not covered: the no-flash checks of the webapp's recorder-based `live-updates.spec.ts` (no
    "cancelled" or empty state flashing mid-update). Android keeps stale data on screen during a refetch,
    so there is no equivalent frame to record.

### M7 — Settings · M · use cases I (3), N (7), avatars

- **User sees:** change your name, your date and time format, and your avatar (Photo Picker, then
  the API's two-step upload: `requestAvatarUpload`, PUT to the presigned URL,
  `confirmAvatarUpload`). Removing your avatar.
- **Notes:** avatars mean image loading and caching appear for the first time (Coil, Compose's
  usual image library). They show up in the agenda, details and calendar retroactively.
- **Built (2026-10-07), as it differs from the plan:**
  - Settings opens from Home's overflow menu. It has three sections: photo, name, and date and time
    format. The two formats save together in one call, as the API replaces the pair. `weekStart` is not
    offered (nothing in the app uses it yet) and is sent back unchanged so a save never resets it.
  - **Avatars:** Coil 3 with the app's own OkHttp client, so a test's fake backend plays the avatar host
    too. `Avatar` shows initials until the photo has loaded and whenever there is none or it fails, so a
    missing image never leaves a hole. It replaces the initials circles on meeting details (organiser and
    attendees) and adds a photo to Home's greeting when the caller has one. Calendar's person picker is
    still names only.
  - **Upload:** the Photo Picker's result is decoded, scaled to at most 1024 pixels a side and re-encoded
    as a JPEG under 2 MiB before it is sent, whatever format it was in (the picker also offers WebP and
    HEIC, which the API refuses). The PUT to the presigned URL carries exactly the declared Content-Type
    and length and no Authorization header. The API still validates and normalises the bytes.
  - Accounts with no linked Person get disabled controls with the webapp's explanation.
  - Verified: pr-checks and the labelled acceptance run are green on mootmaker-android#14. Acceptance
    (`SettingsAcceptanceTest`) covers I.74 to I.76, N.100 to N.102, N.105 and Q.143's display and removal,
    against an ephemeral environment. The fixture users are shared and the app cannot sign up until M8, so
    each test that changes one puts it back in a `finally`. Not covered: choosing a photo through the Photo
    Picker itself (the upload is exercised through the repository's tests and the API in acceptance
    setup), N.103 (Add Meeting parsing input in your own format: the app uses pickers, not typed input),
    N.104 and N.106.
  - **Find-and-fix:** none needed on the pipeline. Locally, the existing meeting-details screenshots were
    re-recorded for sub-pixel circle edge changes, and Coil's decoder is pinned to BitmapFactory because
    Robolectric's ImageDecoder cannot decode files.
  - **Spend:** not visible from inside a session; read it from claude.ai's Usage page. Sonnet.

### M8 — Account lifecycle · M · use cases A (6), C (5), delete account

- **User sees:** sign up with an emailed code, forgot password, delete my account. The webapp
  links from choice 10 for these are removed.
- **Tests:** the host-side email helper (Q5) arrives here, with acceptance for A and C using real
  emails through `mootmaker-email-testing`.
- **Pipeline:** the `test`-stage smoke flow switches to the full **sign up with a real code → use →
  delete account** shape, matching `test-stage.spec.ts`. That makes it the most valuable smoke
  assertion, as on the web.
- **Built (2026-10-07), as it differs from the plan:**
  - Sign-up and forgot password are native two-step screens, as on the webapp, calling Cognito's
    `SignUp`, `ConfirmSignUp`, `ForgotPassword` and `ConfirmForgotPassword` directly (Q2-B). Both
    sign in when they finish. Cognito's messages are shown as the webapp shows them, and a PreSignUp
    name-collision rejection loses Cognito's wrapper, like `readableSignUpError`. The two choice-10
    web links are gone, and so is the Custom Tabs dependency: nothing in the app opens the webapp now.
  - Delete account is a section of Settings with the webapp's confirmation wording, then
    `deleteMyAccount` and sign-out. A refusal (the demo user is reserved) shows in the dialog.
  - **The email helper (Q5-A, Decision 6)** is `email-helper/` in mootmaker-android: a small Node
    server the workflows start on the runner, wrapping `mootmaker-email-testing@v1.0.0`'s own client.
    The emulator reaches it on `localhost:8787` through `adb reverse`; Maestro calls it directly.
    Both poll it, because neither can hold a request open for the queue's long polls. The device
    side reads it over a plain socket, so the shipped app's cleartext policy is untouched. No IAM
    change was needed: the ephemeral and release roles could already read the queue.
  - **Smoke:** `test` now runs `smoke/sign-up-lifecycle.yaml` (sign up with a real code, home, room
    availability, delete account, the old password refused); production keeps the read-only demo
    sign-in. `release-build.yml` also runs the lifecycle flow against its own ephemeral environment
    after the acceptance suite, so a labelled PR proves it before a release depends on it. It does
    not create a meeting as `test-stage.spec.ts` does: acceptance A.6 covers that. `smoke.yml` now
    asks for `id-token: write`, granted by mootmaker-release#84.
  - Verified: pr-checks, the labelled acceptance run (environment `and-acc-261007-id65`, created and
    torn down by the run) and the production smoke are green on mootmaker-android#16 (merged
    e142078). `AccountAcceptanceTest` covers A.1 to A.6, C.16 to C.20 and delete account with real
    emailed codes; every case uses a fresh identity and deletes any account it creates. The
    catalogue has no use case for deleting your own account, so that test is linked from nowhere.
    Before the PR, the real Cognito wording each test waits for was checked by hand against a
    `claude-*` ephemeral environment, then torn down.
  - **Find-and-fix:** three rounds, all in the new test harness, none in the app. Node chunked the
    helper's replies, which a bare socket read as broken JSON; the keyboard covered the sign-up and
    reset forms' submit buttons, so taps landed on it (Robolectric has no keyboard, so the flow
    tests never saw it); and it covered Maestro's "Switch environment" button too. Separately,
    `main` failed O.119 after M6 (a live update can beat the cancel click); M7 fixed that in
    mootmaker-android#15 and this PR carried the identical change until it merged.
  - **Release:** v5.10.7 (mootmaker-release run 91, 2026-10-08), with the APK attached and every
    stage green, including the new sign-up smoke on `test` and the read-only smoke on production.
    The first attempt (run 90, 2026-10-07 at about 23:30 UTC) failed in `build-android`: the
    lifecycle acceptance case booked through Add Meeting, whose latest default slot (23:30) had
    started by the time the account was deleted, and the API cancels only meetings from now on
    (mootmaker-android#17, fixed in #18). That fix's run also hit a race in `FakeBackend`'s request
    log (read by a test while OkHttp appended), now a copy-on-write list.
  - **Spend:** not visible from inside a session; read it from claude.ai's Usage page. Opus.
  - Not covered: a meeting created in the `test` smoke (above); an unconfirmed account resuming its
    sign-up later (the app, like the webapp, has no "resend code" path, and sign-in now just says
    the account isn't confirmed); a code that has expired.

### M9 — Admin: rooms and people · L · use cases P (8), Q (12), L (3)

- **User sees (admins only):** rooms (create, edit, colour, delete) and people (rename, admin flag,
  delete), behind the same `custom:class` check as the webapp's `RequireAdmin`.
- **Tests:** acceptance for P and Q with an admin account, and L's authorization boundaries for a
  standard account. The server already enforces them; these tests prove the app does not offer
  what the server refuses.
- **Smoke:** unchanged. The smoke account is a standard user, and admin flows are not part of the
  five minutes.

### M10 — Parity close-out · S

- The remaining cross-cutting cases in M, an accessibility pass (TalkBack labels, large font
  scaling), dark-mode screenshots for every screen, and any [All frontends] case still showing
  "not yet automated" for Android.
- Remove the "preview" label. Do the outstanding [Documentation impacts](#documentation-impacts).
  Move this design to Shipped and archive it.

### Pacing summary

| Milestone | Size | Cumulative [All frontends] cases covered (approx.) |
|---|---|---|
| M0 Toolchain spike | S | 0 |
| M1 Sign in, see your day | L | ~9 |
| M2 Room availability | M | ~20 |
| M3 Details and calendar | M | ~33 |
| M4 Add a meeting | L | ~52 |
| M5 Edit, cancel, respond | M | ~66 |
| M6 Live updates | M | ~70 |
| M7 Settings | M | ~81 |
| M8 Account lifecycle | M | ~93 |
| M9 Admin | L | ~116 |
| M10 Close-out | S | 119 |

**The credit expires on 2026-11-05**, four weeks after this revision, and anything unspent is lost.
So the aim is to **use it all by then**, not to stretch it out:

- Start M0 as soon as Q1 is answered and the cloud environment exists. M0 needs nothing else, so
  Q2–Q7 can be settled while it runs.
- After M0 and again after M1, project forward: at the rate so far, which milestone will the
  credit reach by 5 November? Early milestones overstate the rate, because a new Android project
  uses a lot of tokens up front.
- After 5 November, work continues on the Pro plan's regular limits, in cloud or laptop sessions,
  but more slowly, because those limits also cover all of Geoff's other Claude use.

The natural stopping points, if the credit (or the plan) runs short:
- **after M3:** a read-only companion app;
- **after M5:** the app does everything a non-admin does day to day, except sign-up;
- **after M7:** everything except account creation and admin, both of which the webapp covers.

## Impacts on components

**`mootmaker-android`** (all new)

- Gradle project, Kotlin DSL, with a version catalog (`gradle/libs.versions.toml`).
- Modules:
  - `app`: Compose UI, navigation, ViewModels;
  - `data`: Apollo client, Cognito client, config loader, token storage;
  - `testing`: fakes, plus the host-side email helper for Q5-A.
  Splitting further is not worth it at this size.
- `.github/workflows/pr-checks.yml`: assemble, lint, unit plus Robolectric, Roborazzi screenshot
  verification, and the `graphql-inspector` check against the pinned schema version.
- `.github/workflows/acceptance.yml`: label- or dispatch-triggered (Q6-B). Creates an
  `and-acc-<date>-<rand>` ephemeral environment, boots an emulator, runs instrumented tests, uploads
  diagnostics, and tears down whatever happens.
- `.github/workflows/release-build.yml` (Q3-A): `workflow_call`, mirroring the webapp's. Builds a
  signed release APK once, proves it against an `rel-and-…` environment, and uploads it as the
  artifact.
- A cloud-environment setup script (`scripts/cloud-setup.sh`), pasted into the cloud environment's
  setup-script field and kept in the repo so changes are reviewed. `.claude/settings.json` for
  laptop sessions only, since two-repository cloud sessions don't read it.
- The CI summary step that writes failures into check-run output (see
  [the cloud–CI loop](#the-cloudci-loop)), shared by `pr-checks.yml` and `acceptance.yml`.
- README, AGENTS.md and `testing-strategy.md` rewritten from "placeholder".

**`mootmaker-api`**

- `deploy/terraform/cognito.tf`: an `android` app client (choice 4); flows per Q2.
- `published-config.tf`: publish `cognito/android-client-id` beside `cognito/webapp-client-id`.
- `pr-checks.yml`: `graphql-inspector diff` against the last published schema, failing on breaking
  changes unless the PR carries an explicit override label (Decision 5).
- A short deprecation rule in the README: a field is marked `@deprecated` and kept until no
  published APK in the last *N* releases uses it. *N* to be decided when it first matters.

**`mootmaker-webapp`**

- `deploy.sh`: write `mobile-config.json` beside `env-config.js` (choice 3).
- If Q4-B: a small `/android` page, or a section on About, linking to the latest APK.
- Unchanged otherwise.

**`mootmaker-release`** (if Q3-A, from M1)

- `compute-version` pins `mootmaker-android`'s `main` SHA.
- `build-android` job calling `mootmaker-android/.github/workflows/release-build.yml@main`.
- `tag` pushes `vX.Y.Z` to the android repo too.
- New smoke jobs; see [Release pipeline](#release-pipeline).
- `record-outcome` attaches `mootmaker-android-X.Y.Z.apk` and its SHA-256 to the GitHub Release.
- New repository secrets for the release keystore and its passwords, passed to `build-android`
  explicitly (Q3). `RELEASE_TAG_PAT`'s repository list gains `mootmaker-android`.

**`mootmaker-bootstrap-aws-accounts`** (Q7, before M1's first acceptance run)

- The pull-request role (Q7-B) and its trust policy for `mootmaker-android` (and
  `mootmaker-webapp`, if pr-time-smoke-verification has not added it already), with `test` and
  `production` denied explicitly.

**`mootmaker-ephemeral-envs`:** no change. The name check (`^[a-z][a-z0-9-]{0,7}-[0-9]{6}-[a-z0-9]{4}$`)
already accepts `and-acc` and `rel-and`. Environments are still created with API plus webapp.

**`mootmaker-email-testing`:** no change to the package. The host helper (Q5-A) lives in
`mootmaker-android/testing` and depends on the package at a pinned tag, as the webapp and release
suites already do.

**`mootmaker-demo-data`:** no change. The app reads the same seeded data.

## Changes to the domain data model and data storage models

**DynamoDB: N/A.** The app reads and writes through the existing API only.

**Cognito:** a new app client (choice 4). No new attributes. The Android client's
`read_attributes` and `write_attributes` must match the webapp client's exactly. In particular,
`custom:class` and `custom:personId` must **never** be writable. `cognito.tf` explains why: every
resolver trusts `custom:personId` to identify the caller. [data-model.md](../docs/reference/data-model.md)
needs no change unless it lists app clients.

## Technical considerations

**Times are naive local strings.** The API's `startTime`/`endTime` are fixed-width
`yyyy-MM-dd'T'HH:mm:ss` **with no zone**, and the webapp treats them as naive local time, never UTC
(see [date-time-format-settings.md](archive/date-time-format-settings.md)). In Kotlin that means
`java.time.LocalDateTime`, **never** `Instant` or `ZonedDateTime`. An Apollo custom-scalar adapter
should enforce this in one place.

**The Day cache semantics are subtle.** The webapp's cache code (`keepDaysWhileRefreshing.ts`,
`referenceDataCache.ts`, the eviction work-around in `useDaysInvalidated.ts`) encodes measured
behaviour, not guesses. Apollo Kotlin's normalized cache differs from Apollo Client 4's. Start
simpler (refetch when a screen becomes visible), and port the cache behaviour deliberately in
M6 rather than reproducing it line by line.

**Subscriptions follow the webapp's rule:** correctness never depends on the socket surviving.
Android pauses background apps more aggressively than browsers freeze tabs, so subscribe only while
the app is in the foreground (tied to the lifecycle), and on every return to the foreground or
reconnect, invalidate everything held and refetch what is on screen. That is the same rule as
`onResubscribed` in the webapp.

**Token storage.** Refresh tokens are stored encrypted, in DataStore with a Keystore-backed key
(Appendix A). If a refresh fails, because the pool was recreated or the token expired, the app
returns to sign-in cleanly rather than crashing or looping. Production's pool is recreated only on
deliberate teardown, but ephemeral and test pools come and go, and the environment switcher makes
this routine.

**The release signing key is forever.** Android accepts an update only if it is signed with the
**same key** as the installed app. Lose the key and every existing install has to be uninstalled and
reinstalled. So:
- Geoff generates the keystore locally;
- it is stored as GitHub Actions secrets (base64 keystore plus passwords) on `mootmaker-release`
  only, because that is the repository whose workflow calls the release build (see Q3);
- it is backed up offline;
- it **never** enters a cloud session, which only ever builds debug variants signed with a
  throwaway debug key.

Signing uses APK Signature Scheme v2/v3, which current tooling does by default. If Q4-D (Play) is
ever chosen, Play App Signing takes custody of the distribution key, which removes this risk for
Play installs.

**Cloud-session environment setup:**
- Network: **Custom**, keeping the Trusted defaults (which already include `maven.google.com`,
  `services.gradle.org`, `plugins.gradle.org`, `registry.npmjs.org` and `raw.githubusercontent.com`)
  and **adding `dl.google.com`**, where the SDK downloads come from. `dl.google.com` is not in the
  Trusted list.
- Setup script: download the SDK command-line tools, accept licences, and install one platform,
  `build-tools` and `platform-tools`. Set `ANDROID_HOME`.
- It must finish in **about 5 minutes or the snapshot isn't cached**. The snapshot is reused by
  every new session and rebuilt about every 7 days or whenever the script changes.
- **Two repositories per session: `mootmaker-android` and `mootmaker`.** A milestone can't be
  finished from `mootmaker-android` alone: its definition of done edits `use-cases.md` and this
  doc's spend line, both here in the hub. Cloud sessions and Claude Code **Projects** can attach
  several repositories, and each clone's `CLAUDE.md` loads. The docs advise adding only the one or
  two repositories nearly every task touches. M1's backend touch points in `mootmaker-api`,
  `mootmaker-webapp`, `mootmaker-release` and `mootmaker-bootstrap-aws-accounts` are separate
  sessions or Project threads, one per repository, each with its own PR.
- **With more than one repository, no repository's `.claude/settings.json` is read**: no hooks, no
  permission rules, no `env`. So:
  - Gradle's dependency cache is warmed by the **setup script**, not a SessionStart hook. If the
    SDK install plus `./gradlew dependencies` doesn't fit in about 5 minutes, warm only the
    largest dependencies there and accept a slower first build per session.
  - Environment variables (`ANDROID_HOME`, `BASH_MAX_TIMEOUT_MS`, and so on) go in the **cloud
    environment's** settings.
  - Standing rules go in `mootmaker-android/AGENTS.md`, which loads either way, and in the
    Project's instructions if a Project is used.
- **Model and effort:** a Project runs every thread on Opus at high effort unless told otherwise,
  which spends the credit fastest. Set the thread model per N6 in Project settings.

**Files are not durable in a cloud session.** Anything not pushed is lost when the VM is reclaimed
after idling. Sessions should commit and push at every green step, which is the project's normal
habit anyway.

**What this leaves behind:**
- **APKs on GitHub Releases:** one per release, about 10–20 MB, kept indefinitely. Release assets
  have no storage charge, and the count is bounded by the number of releases. Accepted.
- **Actions artifacts** (APKs, test reports, screenshots on failure): 30-day retention, matching
  the release repo's setting.
- **Actions cache** (Gradle, AVD snapshots): GitHub evicts after 7 days unused, with a 10 GB cap
  per repo.
- **Ephemeral environments from acceptance runs:** torn down by the workflow `if: always()`, backed
  up by the daily sweep.
- **Cognito users created by tests:** deleted by the tests, as in the webapp's suites. Pools in
  ephemeral environments disappear with the environment.
- **On a phone:** the cached config and encrypted tokens, removed on sign-out or uninstall.

## Manual testing

**On the laptop's emulator**
- Install the command-line SDK plus the emulator, or Android Studio. Studio is the comfortable
  option but uses 2–4 GB of RAM on a 14 GB machine. VS Code plus the command line is enough
  otherwise.
- Create an emulator image with `avdmanager` (Pixel profile, x86_64 system image).
- `./gradlew installDebug` builds and installs. `adb logcat` shows logs.
- A local Claude session can see the screen with `adb exec-out screencap -p > shot.png` and read
  the UI tree with `adb shell uiautomator dump`, so it can drive and inspect the app the way it
  drives Playwright today.

**On Geoff's phone**
- Turn on Developer options (tap Build number seven times — unchanged since 2016).
- Then use either **Wireless debugging** (Android 11+: pair once with a code, then `adb connect`,
  no cable) or USB debugging.
- `scrcpy` mirrors the phone's screen to the laptop, which is useful for screenshots and demos.
- The debug build's `.debug` suffix lets it sit beside the published app.

**Against an ephemeral environment**
1. `../mootmaker-ephemeral-envs/create-ephemeral-env.sh geoff-<yymmdd>-<rand4>` (API plus webapp,
   about 10 minutes). Add `--keep "android manual testing"` for anything spanning more than a day.
2. In the app: About → tap the version repeatedly → enter the environment name. The app fetches
   that environment's `mobile-config.json`, and the demo login works there as it does on the web.
3. Tear it down with `teardown-ephemeral-env.sh` when finished, as with any environment you
   create.

**Trying a PR build on the phone without the laptop:** `pr-checks.yml` uploads the debug APK as an
artifact. GitHub serves artifacts as zips behind a login, which is clumsy on a phone. Two smoother
options: publish PR builds as **pre-releases on `mootmaker-android`** (Obtainium can follow
pre-releases), or Firebase App Distribution (Q4-C). Defer until it is clear this is wanted.

## Release pipeline

Assuming Q3-A and Q5's leaning. The parts that change are marked ★.

```
compute-version ★pins android SHA
  -> build-api | build-webapp | build-demo-data | ★build-android     (parallel)
  -> tag ★(+ android repo)
  -> deploy-test
  -> smoke-test-test | ★smoke-android-test | ★smoke-android-n-1-test
  -> deploy-production
  -> smoke-test-production | ★smoke-android-production
  -> (rollback-production -> smoke-test-rollback, unchanged)
  -> record-outcome ★attaches APK only on success
```

- **`build-android`:** builds and signs the APK **once**, runs JVM tests, deploys API plus webapp
  to `rel-and-<date>-<rand>`, runs the instrumented acceptance suite on an emulator against it,
  tears the environment down, and uploads the APK. It runs in parallel with the other builds, so it
  lengthens the release only if it is the slowest. Expect it to be close to the webapp's time.
- **`smoke-android-test`:** boots an emulator, installs **the release APK**, points it at `test`,
  and runs a Maestro flow, roughly the five minutes a human would spend. Sign up with a real emailed
  code (fetched host-side through `mootmaker-email-testing`), sign in, view room availability,
  create a meeting and read it back, then delete the account. It deliberately mirrors
  `test-stage.spec.ts` and stays this small.
- **`smoke-android-n-1-test`:** the same flow, with the **previously published** APK downloaded
  from the last successful GitHub Release, against the new `test` API. This is the check that
  catches the "browsers update, phones don't" failure in Decision 5. It is skipped on the very
  first release that publishes an APK.
- **`smoke-android-production`:** read-only. Demo login on production with the new APK, then the
  home and availability screens render. It mirrors `production-stage.spec.ts`'s read-only rule.
- **No Android rollback.** The APK is published **last**, only in `record-outcome`'s success
  branch, so a release that rolls production back never published an app. If a bad APK does get
  out, the fix is the next release. There is no un-publishing an installed app, which is why the n-1
  check exists.
- **Cost:** Actions minutes are free for public repos. AWS adds one more ephemeral environment per
  release (for `build-android`) and a few M2M tokens.
- **Flakiness budget:** emulator boot is the usual source of flakes. Give the emulator boot step
  one automatic retry; the tests themselves get none. Per the project's rule, an intermittent test
  failure is a bug to fix, not to retry past. Track failures against
  [release-confidence.md](https://github.com/geoffweatherall/mootmaker-release/blob/main/docs/release-confidence.md).

## Using the cloud credit well

The credit applies only to cloud sessions and expires on 2026-11-05 (see Decision 1 and the
[pacing summary](#pacing-summary)).

- **One milestone at a time, started deliberately.** Start each cloud session, with both
  `mootmaker-android` and `mootmaker` attached, with "read `mootmaker/designs/android-app.md`,
  continue milestone MN". That is what this folder's design pattern is for, and it keeps the
  context small.
- **Push as you go.** See "Files are not durable" above.
- **Cheaper model for scaffolding, stronger one for the tricky parts** (N6). Gradle setup and
  screen layouts are boilerplate-heavy; auth, caching and subscriptions are where a stronger model
  earns its cost. In a Project, set this in Project settings, since threads default to Opus at
  high effort.
- **Let CI do the waiting.** `gh run watch` blocks in one command, so a 30-minute emulator run costs
  almost no tokens. Turn on **auto-fix** for each PR so a failed check wakes the session.
- **Read summaries, not logs.** The check-run summary ([the cloud–CI loop](#the-cloudci-loop))
  costs a few hundred tokens. A raw Gradle or logcat dump can cost tens of thousands.
- **Hands-on debugging stays on the laptop.** When CI's emulator job fails in a way the summary
  does not explain, a laptop session with a local emulator is a faster loop, and it uses the Pro
  plan rather than the credit. Before 5 November that means saving the credit for building; after
  it, there is no difference in what pays.
- **Check spend after M0 and M1** on claude.ai's Usage page and project it to 5 November.

## Testing impacts

By layer, following [testing-strategy.md](../docs/reference/testing-strategy.md)'s terms. All new,
in `mootmaker-android` unless stated.

- **Unit (JVM, no environment):** pure logic, such as date/time formatting per the user's format
  setting, error-enum to message mapping, room-colour fallback and add-meeting validation. Several
  have direct webapp counterparts (`formatDateTime.test.ts`, `errorMessages.test.ts`,
  `addMeetingLogic.test.ts`) whose cases should be **ported as cases**, not as code, so the two
  frontends agree. Runs in cloud sessions in seconds.
- **Integration (JVM, mocked backend):** Compose screens rendered under **Robolectric** with a fake
  GraphQL layer (Apollo's `MockServer`, or fakes behind a repository interface). Proves things like
  "the right query fires, a validation error renders, success navigates, admin screens are hidden
  from standard users". This is the counterpart of the webapp's Playwright plus MSW layer, and it
  is the right layer for those cases because it is deterministic and runs in cloud sessions.
  **Screenshot tests** (Roborazzi) live here too: they record PNGs of key screens in light and dark
  mode and fail on unexpected visual change. They are what lets a session without an emulator
  actually *see* its UI.
- **e2e (emulator, real ephemeral environment):** deliberately thin. Config is fetched from
  `mobile-config.json`, Cognito sign-in works with the Android client, a GraphQL query returns, and
  a subscription delivers an invalidation. Proves the wiring that only a real environment can show.
- **Acceptance (emulator, real ephemeral environment):** the use-case catalogue, through the real
  UI, using Q5's tool. Grows milestone by milestone. Shares no code with the webapp's suite, by
  testing-strategy.md's rule that each frontend owns its own, but it uses the same use-case IDs.
- **Release smoke (mootmaker-release):** new Android jobs as described above. The existing
  `test-stage.spec.ts` and `production-stage.spec.ts` are **unchanged**: the webapp's flows do not
  change.
- **mootmaker-api `verify/`:** unchanged, except a check that the Android client exists with the
  right attribute permissions, since that is a security boundary. The new `graphql-inspector` PR
  check is a CI gate, not a test layer.
- **mootmaker-webapp suites:** unaffected. `mobile-config.json` is written by `deploy.sh` and read
  by nothing in the webapp. One assertion in the webapp's e2e suite that the file is served would
  be cheap, but the Android e2e suite covers it anyway.

## Documentation impacts

- [`architecture.md`](../docs/development/architecture.md): an Android row in the shape diagram;
  the repository table no longer says "Not started"; "How the webapp reaches the API" gains
  `mobile-config.json`; the contract section names Android as the first independently-released
  consumer.
- [`testing-strategy.md`](../docs/reference/testing-strategy.md): Android rows in the layers table.
- [`use-cases.md`](../docs/reference/use-cases.md): each milestone fills in the `android:` links for
  the cases it covers (the tags already exist; see N2).
- [`environments.md`](../docs/process/environments.md): the `and-acc` and `rel-and` kinds in the
  naming table.
- [`running-costs.md`](../docs/reference/running-costs.md): the extra environment per release and
  per labelled PR.
- `mootmaker/README.md`: a "Get the Android app" link once an APK is published.
- `mootmaker-android` README, AGENTS.md, `testing-strategy.md`: written for real.
- `mootmaker-release` README: the stage table and the "four components" wording.
- `mootmaker-api` README: the Android client, the new SSM parameter, the deprecation rule.
- [`tools/workstation/`](../tools/workstation/): Android SDK as an optional workstation tool.

## Rollout & migration

No data migration: the app is a new client of existing data.

1. **M0 ships nowhere.** It proves the toolchain only.
2. **M1's release publishes the first APK**, labelled "preview" in its release notes (and on the
   download page from M2). The same release carries the API's new Cognito client and the webapp's
   `mobile-config.json`.
3. **M2–M9** each go out in an ordinary release. Releases between milestones (API or webapp work)
   republish the current APK unchanged in behaviour. That is expected under Q3-A, and it's what
   the n-1 check is for.
4. **M10** removes the "preview" label.

There is no feature flag. The app's presence is the flag, and the API changes (a new Cognito
client, a JSON file) are additive and invisible to the webapp.

## Risks

- **Losing the signing key** strands every install. This is mitigated by an offline backup and
  repo secrets, and is the single hardest-to-reverse thing in this design.
- **A breaking API change reaches installed apps.** Mitigated by `graphql-inspector`, the n-1 smoke
  check and the deprecation rule. Residual risk: a semantic change that keeps the schema identical,
  which only the n-1 smoke flow might catch.
- **Emulator flakiness raises the release failure rate** and burns version numbers. Mitigated by
  keeping smoke tiny, retrying only the emulator boot, and treating intermittent failures as bugs.
  Watch the first ten releases.
- **Parity drift:** the webapp keeps moving while Android catches up. N3 decides whether that is
  acceptable.
- **The credit runs out, or expires on 2026-11-05, mid-way.** Every milestone ends published, so
  any boundary is a safe place to stop. See the [pacing summary](#pacing-summary) for the natural
  ones. Work can continue on the Pro plan's regular limits, more slowly.
- **Open decisions eat the credit's four weeks.** Each day Q1 and the cloud environment are
  unsettled is a day of credit unused. Mitigated by M0 needing only Q1, and Q7 blocking only M1.
- **The cloud–CI loop is weaker than assumed:** for example, logs and artifacts can't be read, or a
  paused VM doesn't resume when a run finishes. M0 tests this before any feature work, and the
  check-run summary means artifacts are optional.
- **Developer verification** becomes mandatory for sideloading in NZ from 2027 (N4).
- **Cloud environment assumptions change** (VM size, allowlist, the 5-minute setup cache). All
  are documented product behaviour as of 2026-10-05, not guarantees. The M0 probe re-checks
  them.

## Implementation checklist

Sparse while Drafting. Each milestone's detailed tasks get written into its section above at
the start of that milestone, so the checklist never runs far ahead of what is known.

**Before M0** (only these block it)
1. ~~`[Geoff]` Answer Q1.~~ Done 2026-10-07.
2. `[Geoff]` Install the Claude GitHub App on `mootmaker-android` and `mootmaker` (auto-fix and
   Projects need it). Create a cloud environment with Custom network access (Trusted plus
   `dl.google.com`), and `BASH_MAX_TIMEOUT_MS=600000` in its environment variables. Use a Claude
   Code **Project** with those two repositories if Projects has reached the account; otherwise
   attach both to each session. (Claude Code Projects are in the sidebar at claude.ai/code. They
   are not the chat Projects in claude.ai's main menu, and per the docs they reach accounts
   without chat projects first.)

**M0:** `[Claude]` as described in [M0](#m0--toolchain-spike--s--no-user-functionality).
Probe results recorded in
[M0 results](#m0-results-2026-10-06). Done pending the merge of mootmaker-android PR #5.

**Before M1** (while M0 runs)
3. ~~`[Geoff]` Answer Q2–Q7.~~ Done 2026-10-07.
4. `[Geoff]` Generate the release keystore locally, add it as `mootmaker-release` repo secrets (Q3),
   and back it up offline.
5. `[Geoff]` Add `mootmaker-android` to `RELEASE_TAG_PAT`'s repository list.
6. `[Claude]` Q7's pull-request role in `mootmaker-bootstrap-aws-accounts`, unless
   pr-time-smoke-verification has already built it. `[Geoff]` applies it with that
   repository's `deploy-stack.sh`, as for every stack there.

**M1–M10:** `[Claude]` one milestone at a time, each started explicitly by Geoff, each finishing
with the per-milestone checklist under [Milestones](#milestones). `[Geoff]` does the phone check
at the end of each.

## Definition of done

- M0–M10 are complete. Every **[All frontends]** case in `use-cases.md` links to an Android test
  case, and the Android acceptance suite is green against a real ephemeral environment.
- The webapp's and API's existing suites are still green. The `graphql-inspector` check is live on
  `mootmaker-api`.
- A release run built, tested, smoke-tested (test, n-1 and production) and published an APK, and
  Geoff installed it on a physical phone from the public location and signed in to production.
- Every item under Documentation impacts is done.
- Any ephemeral environments created along the way are torn down.

---

## Appendix A — Android in 2026, for someone who last looked in 2016

| Then (≈2016) | Now | Why it matters here |
|---|---|---|
| Java | **Kotlin**, Google's preferred language since 2019. Null safety, data classes, much less boilerplate | All new code is Kotlin |
| XML layouts, `findViewById`, Fragments | **Jetpack Compose**: UI as Kotlin functions that describe the screen for the current state, re-run when the state changes. Very like React components | Screens are composable functions; no XML |
| AsyncTask, callbacks, RxJava | **Coroutines** and **Flow**: `suspend` functions and structured concurrency, like async/await | Network calls are `suspend` functions |
| Activities holding everything; state lost on rotation | **ViewModel** survives configuration changes and exposes state as a `StateFlow` that Compose observes. One Activity, with **Navigation Compose** between screens | The standard architecture: Screen → ViewModel → Repository |
| Dagger 2, if you were brave | **Hilt**, a simpler layer on Dagger, or manual dependency injection at this size | Optional; manual is fine for an app this size |
| SharedPreferences | **DataStore** (async, typed). The Android **Keystore** for keys | Token and config storage |
| Groovy `build.gradle`, versions scattered around | **Gradle Kotlin DSL** (`build.gradle.kts`) and a **version catalog** (`libs.versions.toml`) | Where dependencies are declared |
| Holo or early Material | **Material 3** ("Material You"), with dynamic colour from the wallpaper. **Edge-to-edge** layout is now mandatory for apps targeting recent SDKs | Theming; mootmaker's brand colours become a Material 3 colour scheme |
| Permissions granted at install | Runtime permissions (from Android 6), plus **Photo Picker**, which lets you choose images without any storage permission | Avatar upload needs no permissions at all |
| Slow ARM emulator, Genymotion | The official emulator, fast on x86_64 with KVM. **Wireless debugging** to phones | See Manual testing |
| Robolectric (young), Espresso | **Robolectric** (mature: Android framework on the JVM), **Compose UI testing**, **screenshot testing** (Roborazzi, Paparazzi), **Gradle managed devices** | Most testing happens without a device |
| APK everywhere | **AAB** (Android App Bundle) for Play, which builds per-device APKs. Still a plain **APK** for sideloading. Signing schemes v2/v3 | We ship an APK (Q4) |
| Eclipse ADT, early Android Studio | Android Studio (IntelliJ-based) is the IDE. The command-line SDK is enough for builds | Studio is optional on the laptop |
| — | **Predictive back** gesture, per-app language, notification permission (Android 13+) | Mostly framework-handled; worth knowing the names |

API levels you might hear: Android 8.0 = API 26 (proposed minSdk), Android 11 = API 30 (wireless
debugging), Android 13 = API 33, Android 16 = API 36.
