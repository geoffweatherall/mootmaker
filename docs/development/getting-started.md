# Getting started

Your first hour on mootmaker. If you are an AI agent, read
[`../process/README.md`](../process/README.md) first — this page is about getting a machine working.

## 1. Check your machine

```bash
mootmaker/tools/workstation/check.sh
```

Install anything it reports as missing. See [workstation.md](workstation.md).

## 2. Get the repositories

Every repository expects the others as **siblings in one directory**. Scripts resolve
`../mootmaker-api` and similar relative paths, so a flat layout is not optional.

```
mootmaker-workspace/
  mootmaker/               mootmaker-api/             mootmaker-webapp/
  mootmaker-android/       mootmaker-demo-data/       mootmaker-release/
  mootmaker-ephemeral-envs/  mootmaker-email-testing/  mootmaker-domain/
  mootmaker-bootstrap-terraform/  mootmaker-bootstrap-aws-accounts/
```

```bash
mkdir mootmaker-workspace && cd mootmaker-workspace
for r in mootmaker mootmaker-api mootmaker-webapp mootmaker-android \
         mootmaker-demo-data mootmaker-release \
         mootmaker-ephemeral-envs mootmaker-email-testing mootmaker-domain \
         mootmaker-bootstrap-terraform mootmaker-bootstrap-aws-accounts; do
  git clone "https://github.com/geoffweatherall/$r.git"
done
```

## 3. Authenticate

```bash
aws sso login                      # no long-lived credentials by design
gh auth login                      # then: gh auth refresh -s project
```

## 4. Stand up your own environment

An environment is just a name. Pick one nobody else is using, following the ephemeral naming
convention in [`../process/environments.md`](../process/environments.md):

```bash
cd mootmaker-api      && ./deploy.sh geoff-260829-a1b2
cd ../mootmaker-webapp && ./deploy.sh geoff-260829-a1b2   # prints a site URL
```

Optionally add demo data. Deploying it does not populate anything — the Lambda only runs when
invoked — so seeding is a second, deliberate step:

```bash
cd ../mootmaker-demo-data && ./deploy.sh geoff-260829-a1b2
aws lambda invoke --function-name geoff-260829-a1b2-mootmaker-demo-data \
  --cli-read-timeout 900 --payload '{}' /dev/stdout
```

`--cli-read-timeout 900` matters: the function's ceiling is 900 seconds and the CLI defaults to 60,
so without it a full seed is reported to you as a failure while the Lambda finishes regardless.

(`create-ephemeral-env.sh claude --with-demo-data` does all of the above in one command.)

**Tear it down when you are done. This is not optional** — see
[`../process/environments.md`](../process/environments.md).

```bash
cd ../mootmaker-ephemeral-envs && ./teardown-ephemeral-env.sh geoff-260829-a1b2
```

That script discovers what is actually deployed from the environment's Terraform state prefix, so
it tears down demo-data too if you deployed it, and refuses to finish quietly if anything is left
behind.

## 5. Run the tests

```bash
cd mootmaker-api      && mvn -f impl/pom.xml test    # unit
cd ../mootmaker-webapp && npm --prefix webapp test   # unit + mocked integration
cd ../mootmaker-webapp && ./acceptance/run.sh        # real deployment, creates and destroys its own env
```

`acceptance/run.sh` with no argument creates a fresh ephemeral environment and tears it down
afterwards. Pass an environment name to reuse one instead — faster when iterating, but be aware that
a reused environment accumulates state, which has caused confusing failures before.

**`npm install` at the repository root as well as in `webapp/`.** They are separate `package.json`
files; missing the root one produces a silent "playwright: not found".

## Where to go next

| You want to | Read |
|---|---|
| Understand how work is done | [`../process/README.md`](../process/README.md) |
| Understand the system | [architecture.md](architecture.md) |
| Understand the tests | [`../reference/testing-strategy.md`](../reference/testing-strategy.md) |
| Understand the data | [`../reference/data-model.md`](../reference/data-model.md) |
| Know what it does | [`../reference/business-functionality.md`](../reference/business-functionality.md) |
| Build something | [`../../designs/README.md`](../../designs/README.md) |
