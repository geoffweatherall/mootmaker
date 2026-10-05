# Android app

## Summary

Start building `mootmaker-android`: a native Android app that reaches feature parity with
mootmaker-webapp, using the same GraphQL API and the same Cognito user pool. Day-to-day
development happens in Claude Code **cloud sessions** (paid for from a US$100 cloud-session
credit plus the Pro plan). Those sessions build and run JVM-level tests but cannot run an Android
emulator, so emulator tests run in **GitHub Actions**, which is free for this public repo and has
hardware virtualization. Hands-on testing happens on Geoff's laptop or phone. The design also
covers what a third deployable component does to the release pipeline, how the app gets published
for sideloading, and how it is smoke-tested.

This doc offers **options rather than single answers** in several places, at Geoff's request. Each
one is lettered so a reply can be as short as "Q3: B". Geoff last did Android development about ten
years ago, so [Appendix A](#appendix-a--android-in-2026-for-someone-who-last-looked-in-2016)
explains what has changed since then, and terms are explained where they first appear.

## Status

**Drafting** — 2026-10-05. First draft. The blocking questions under "Open questions" need Geoff's
answers before this can move to Ready.

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

According to the docs, the VM itself has no separate compute charge. Cloud sessions draw on the same
usage and rate limits as the rest of the account, so the credit pays for **tokens**, not machine
time.

### 2. Emulator tests run in GitHub Actions on Linux runners

`mootmaker-android` is public, so standard GitHub-hosted runners are free with unlimited minutes.
The `ubuntu-*` runners expose KVM; one udev-rule step makes it usable, and
`reactivecircus/android-emulator-runner` boots an emulator inside the job. This is the standard way
to run Android instrumented tests in CI. The macOS (Apple Silicon) runners cannot do this, so the
emulator jobs are Linux-only.

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
   frontend signed in. It is published to SSM as `/mootmaker/<env>/api/cognito-android-client-id`,
   following the existing pattern.
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
8. **Phase order** in the [Implementation checklist](#implementation-checklist): auth, then
   read-only screens, then writes, then settings, admin and live updates. Each phase is usable on its
   own and roughly sized for one or two cloud sessions.
9. **minSdk 26 (Android 8.0).** This covers effectively every phone still in use and gives native
   `java.time`, which the date handling needs (see Technical considerations). `targetSdk` follows
   the latest stable API level. Non-blocking; raising minSdk later is easy.

## Open questions

### Blocking

Each question lists options and a leaning. The leaning is a recommendation, not a decision.

#### Q1. What is the app built with?

| | Option | What it means | For | Against |
|---|---|---|---|---|
| **A** | **Native Kotlin + Jetpack Compose** | Kotlin code with Compose for UI (React-like, declarative). The mainstream Android stack in 2026 | What `mootmaker-android`'s README already promises ("native"). Best tooling, docs and Claude familiarity. Robolectric and screenshot tests are mature | Nothing shared with the webapp except the schema. Every screen is written again |
| **B** | Kotlin Multiplatform + Compose Multiplatform | Same as A, but with shared code in a module that could also target iOS later | iOS becomes possible without a rewrite | More build complexity now for an iOS app that is a non-goal. Thinner docs |
| **C** | Trusted Web Activity (TWA) | The existing webapp, wrapped as an installable app running in Chrome without browser UI (Google's Bubblewrap tool generates it) | Parity on day one, for almost no work. The webapp is already mobile-first | Not really an Android app: no native UI, nothing new to show or learn. Needs `assetlinks.json` on the domain |
| **D** | React Native or Capacitor | A JavaScript/React app compiled or wrapped for Android | Could reuse some React logic | A third UI toolkit to learn. MUI components do not carry over to React Native |

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

**Leaning: A**, but **only once the app reaches its first usable phase** (auth plus read-only
screens). Until then, the app is built and tested only by its own PR checks, and `release.yml` is
unchanged. Joining is a checklist item, not day one.

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

**Leaning: B.** PR checks always run the free layers (build, lint, unit, Robolectric, screenshot),
so most mistakes are caught without AWS. The label is for PRs that change how the app talks to the
backend. This also fits what [pr-time-smoke-verification.md](pr-time-smoke-verification.md) is
working out for the webapp. If that design lands an approach, Android should follow it rather than
invent a second one.

### Non-blocking

- **N1.** SRP versus `USER_PASSWORD_AUTH` on the Android client, if Q2 is B.
- **N2.** Whether `use-cases.md` gets per-frontend tags (`[web]`, `[android]`, `[both]`), or the
  android acceptance suite keeps its own mapping. The android repo's AGENTS.md already flags that
  "some cases are webapp-specific in ways that will need untangling". Leaning: tags.
- **N3.** A parity rule going forward: once Android has parity, does a new feature count as done
  only when both frontends have it, or can Android lag? Leaning: allowed to lag, tracked as an issue
  in `mootmaker-android` per feature.
- **N4.** Developer verification before global enforcement in 2027 (see Q4).
- **N5.** Android App Links: tapping `https://www.mootmaker.com/meetings/<id>` on a phone opens the
  app. Needs `/.well-known/assetlinks.json` on the webapp's domain. Nice later, not parity.
- **N6.** Which cloud-session model per phase (Sonnet for scaffolding and screens, Opus for auth,
  caching and subscriptions), to make the credit last. See
  [Using the cloud credit](#using-the-cloud-credit-well).

## Feature parity

Mapped against the webapp's routes (`webapp/src/App.tsx`) and the use-case catalogue's sections.

| Webapp | Use cases | Android | Phase |
|---|---|---|---|
| `/signin`, sign out | B | Sign-in screen; sign-out in the menu | 1 |
| `/signup` | A | Sign-up plus verification-code screen | 1 |
| `/forgot-password` | C | Same two-step flow | 1 |
| `/` home, with demo login pre-filled | D | Home; demo credentials pre-filled from `mobile-config.json`, as on the web | 1–2 |
| `/rooms/:date/availability` | E | Room availability, day by day | 2 |
| `/persons/:personId/calendar` | G | Person calendar | 2 |
| `/meetings/:meetingId` | H | Meeting details | 2 |
| `/meetings/add`, `/meetings/:id/edit` | F, O | Add, edit and cancel meeting; room suggestion | 3 |
| Attendee response | (attendee-response-status) | Going / Maybe / Not going control | 3 |
| `/settings`: name, date/time format, avatar, delete account | I, N | Settings screen; avatar via the Android **Photo Picker** (no storage permission needed) | 4 |
| `/rooms`, `/persons` (admin) | J, K, P, Q | Admin screens behind the same `custom:class` check as `RequireAdmin` | 5 |
| Live updates (`daysInvalidated` subscription) | M | AppSync subscription while the app is in the foreground | 6 |
| Authorization boundaries | L | Enforced server-side already; app tests mirror the web's | 1–5 |
| `/about` | — | About screen with version, licences, and the hidden environment switcher | 1 |

Webapp-specific: browser-only behaviour in section M (tab visibility, URLs as state) has a
counterpart (app foreground/background, the back stack), but the tests are written differently.

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
- `.claude/settings.json` and a cloud-environment setup script (`scripts/cloud-setup.sh`), so
  cloud sessions work from the repo alone.
- README, AGENTS.md and `testing-strategy.md` rewritten from "placeholder".

**`mootmaker-api`**

- `deploy/terraform/cognito.tf`: an `android` app client (choice 4); flows per Q2.
- SSM: publish `cognito-android-client-id` beside the existing parameters.
- `pr-checks.yml`: `graphql-inspector diff` against the last published schema, failing on breaking
  changes unless the PR carries an explicit override label (Decision 5).
- A short deprecation rule in the README: a field is marked `@deprecated` and kept until no
  published APK in the last *N* releases uses it. *N* to be decided when it first matters.

**`mootmaker-webapp`**

- `deploy.sh`: write `mobile-config.json` beside `env-config.js` (choice 3).
- If Q4-B: a small `/android` page, or a section on About, linking to the latest APK.
- Unchanged otherwise.

**`mootmaker-release`** (if Q3-A, at the phase described there)

- `compute-version` pins `mootmaker-android`'s `main` SHA.
- `build-android` job calling `mootmaker-android/.github/workflows/release-build.yml@main`.
- `tag` pushes `vX.Y.Z` to the android repo too.
- New smoke jobs; see [Release pipeline](#release-pipeline).
- `record-outcome` attaches `mootmaker-android-X.Y.Z.apk` and its SHA-256 to the GitHub Release.

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
Phase 6 rather than reproducing it line by line.

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
- it is stored as GitHub Actions secrets (base64 keystore plus passwords) on `mootmaker-android`
  only;
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
- Gradle's dependency cache is warmed by an async SessionStart hook rather than the setup script, to
  stay under the limit.
- A cloud session clones **one repo**. The hub's designs are reachable as raw GitHub URLs, and
  AGENTS.md already links that way. Work that also changes `mootmaker-api` or `mootmaker-webapp`
  (Phase 0b) needs its own session in that repo, or a laptop session.

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

- **One phase per session.** Start each cloud session with "read
  `mootmaker/designs/android-app.md`, do Phase N". That is what this folder's design pattern is for,
  and it keeps the context small.
- **Push as you go.** See "Files are not durable" above.
- **Cheaper model for scaffolding, stronger one for the tricky parts** (N6). Gradle setup and
  screen layouts are boilerplate-heavy; auth, caching and subscriptions are where a stronger model
  earns its cost.
- **Keep emulator debugging off the credit where possible.** When CI's emulator job fails in a way
  the logs do not explain, a laptop session with a local emulator is a faster loop than a cloud
  session reading CI logs, and it uses the Pro plan instead.
- **Check spend after Phases 0 and 1** on claude.ai's usage page before committing to the rest.
  Setting up a new Android project uses a lot of tokens up front, so early spend overstates the
  per-phase rate.
- Cloud sessions can **Auto-fix** a PR: watch CI and push fixes for failures. Useful for the
  emulator job, which a cloud session cannot run itself.

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
  UI, using Q5's tool. Grows phase by phase. Shares no code with the webapp's suite, by
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
- [`use-cases.md`](../docs/reference/use-cases.md): per-frontend tags if N2 goes that way.
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

1. **Phases 0–2 ship nowhere.** They are built and tested by `mootmaker-android`'s own CI, and the
   APK is installed by hand from PR builds or the laptop.
2. **The app joins `release.yml`** (Q3-A) once Phase 2 is done, and the first release afterwards
   publishes the first APK, labelled "preview" in its release notes and on the download page.
3. **Phases 3–6** go out in ordinary releases. The "preview" label comes off at parity.

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
- **The credit runs out mid-way.** Phase boundaries are natural stopping points, each phase leaves
  something usable, and the work can continue in laptop sessions on the Pro plan.
- **Developer verification** becomes mandatory for sideloading in NZ from 2027 (N4).
- **Cloud environment assumptions change** (VM size, allowlist, the 5-minute setup cache). All
  are documented product behaviour as of 2026-10-05, not guarantees. The Phase 0 probe re-checks
  them.

## Implementation checklist

Sparse while Drafting. It will be filled in properly once the open questions are answered.

**Phase 0a — prove the toolchain** (no app code yet)
1. `[Geoff]` Answer Q1–Q6.
2. `[Geoff]` Install the Claude GitHub App on `mootmaker-android`, and create a cloud environment
   with Custom network access (Trusted plus `dl.google.com`).
3. `[Claude]` In a throwaway cloud session: check `ls /dev/kvm`, `nproc`, `free -g`, and that
   `dl.google.com` and `registry.npmjs.org` are reachable. Record the results here.
4. `[Claude]` `scripts/cloud-setup.sh`, timed under 5 minutes. Skeleton Gradle project with Compose
   and an Apollo Kotlin build generating from the npm-tarball schema.
   `pr-checks.yml` (build, lint, unit, Robolectric, one Roborazzi screenshot). An emulator job
   running one trivial instrumented test, proving KVM in Actions.
5. `[Geoff]` Generate the release keystore locally, add it as repo secrets, and back it up offline.

**Phase 0b — backend touch points** (separate sessions in `mootmaker-api` and `mootmaker-webapp`)
6. `[Claude]` Android Cognito client plus SSM parameter. `mobile-config.json` in the webapp's
   `deploy.sh`. The `graphql-inspector` check in the api's `pr-checks.yml`. Proven on one ephemeral
   environment.

**Phases 1–6** follow the [Feature parity](#feature-parity) table. Each phase adds its unit,
integration and screenshot tests, extends the acceptance suite, and ends with a green labelled
acceptance run.

**Phase 7 — release and distribution** (after Phase 2; see Rollout)
7. `[Claude]` `release-build.yml` in android. The `release.yml` changes. Maestro smoke flows
   (test, n-1, production). APK attached in `record-outcome`. The download page (if Q4-B).
8. `[Geoff]` Install the published APK on his own phone from the public link.

## Definition of done

- Every use case tagged for Android (N2) is covered by the Android acceptance suite, and that suite
  is green against a real ephemeral environment.
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
