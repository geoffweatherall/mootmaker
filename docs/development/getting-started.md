# Getting started

Your first hour on Mootmaker: a working machine, the code, credentials, your own copy of the system,
and the tests. If you are an AI agent, read the [process](../process/README.md) first; this page is
about the machine.

Development targets Ubuntu. Nothing here is tested on macOS or Windows.

## 1. Get the repositories

Every repository expects the others checked out side by side in one directory, because scripts use
paths like `../mootmaker-api`.

```bash
mkdir mootmaker-workspace && cd mootmaker-workspace
for r in mootmaker mootmaker-api mootmaker-webapp mootmaker-android mootmaker-demo-data \
         mootmaker-release mootmaker-ephemeral-envs mootmaker-email-testing mootmaker-domain \
         mootmaker-bootstrap-terraform mootmaker-bootstrap-aws-accounts; do
  git clone "https://github.com/geoffweatherall/$r.git"
done
```

What each one is: [repositories](../overview/repositories.md).

## 2. Check and set up the machine

```bash
mootmaker/tools/workstation/check.sh                     # what is installed, what is missing, how to install it
mootmaker/tools/install-workspace-config.sh --force      # VS Code and Claude Code settings, extensions
```

`check.sh` reads [`tools/workstation/manifest.yaml`](../../tools/workstation/manifest.yaml); see
[workstation](workstation.md). The usual set is git, the GitHub CLI, the AWS CLI v2, Terraform 1.10+,
JDK 25 and Maven, Node 20 or later, Python 3, and jq. Android work also needs JDK 21 and the Android SDK.

Each Node project needs `npm install`. mootmaker-webapp has **two** `package.json` files, at the root
(test suites) and in `webapp/` (the app); install both.

## 3. Sign in to AWS and GitHub

```bash
aws sso login          # after setting up ~/.aws/config as in the AWS accounts overview
aws sts get-caller-identity
gh auth login
gh auth refresh -s project     # to read the project board
```

The exact `~/.aws/config` is in [AWS accounts](../overview/aws-accounts.md#getting-access). There are no
access keys.

## 4. Stand up your own environment

```bash
mootmaker-ephemeral-envs/create-ephemeral-env.sh geoff --with-demo-data
```

This creates an environment named like `geoff-261012-a1b2`: the API, the web app, and demo data, about ten
minutes. It prints the site URL; the demo login is on the home page. Deploying costs a few cents.

To change something and see it: edit, then redeploy just that component, for example
`mootmaker-api/deploy.sh geoff-261012-a1b2`. Deploy the API before the web app.

**Tear it down when you are done:**

```bash
mootmaker-ephemeral-envs/teardown-ephemeral-env.sh geoff-261012-a1b2
```

If you will be away more than two days, either tear it down or keep it with
`keep-env.sh <name> "<reason>"`; otherwise the daily sweep destroys it. See
[delivery](../overview/delivery.md#ephemeral-environments).

## 5. Run the tests

| Repository | Fast tests | Against your environment |
|---|---|---|
| mootmaker-api | `mvn -f impl/pom.xml test` | `./verify.sh <env>` |
| mootmaker-webapp | `npm --prefix webapp run test:unit` and `npm --prefix webapp run test:integration` | `./acceptance/run.sh <env>` |
| mootmaker-demo-data | `mvn -f impl/pom.xml test` | `./verify.sh <env>` (it resets the environment) |
| mootmaker-android | `./gradlew :app:assembleDebug :app:lintDebug :data:testDebugUnitTest :app:verifyRoborazziDebug` (with JDK 21) | GitHub Actions only: label the PR `run-acceptance` |

`acceptance/run.sh` with no environment creates a fresh one and tears it down afterwards.

Java formatting is checked in CI; `mvn -f impl/pom.xml spotless:apply` fixes it. See
[Java code style](../process/java-code-style.md).

## Where next

| To | Read |
|---|---|
| Understand the system | [System overview](../overview/system.md), then the other [overviews](../overview/) |
| Know how work is done here | [Process](../process/README.md) |
| Build something | [Designs](../../designs/README.md) |
| Fix something that is broken | [Runbooks](../runbooks/README.md) |
| Know what the system must do | [Use cases](../reference/use-cases.md) |
