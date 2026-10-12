# Flaky test

A test passes and fails on the same code. In this project every intermittent failure investigated so far
has been a real bug, in the product or in the test, so treat "flaky" as a hypothesis to disprove, not a
reason to re-run.

## Before re-running

1. **Save the evidence.** The failure message, the run link, and any artifact (Playwright traces,
   screenshots, Android check-run annotations). A green re-run destroys the most useful information you
   will get.
2. **File an issue** in the repository the test lives in, labelled `flaky-test`, with the evidence. Note
   the time in UTC and in New Zealand time: several failures here depended on the time of day.
3. **Then** re-run, if the release or the pull request needs to move.

## Where flakiness has come from

The causes found so far, roughly in order of how often:

| Pattern | Example | What to look for |
|---|---|---|
| **Racing the live update or a refetch** | A test checks the screen before a broadcast-driven refetch lands, or a stale in-flight response overwrites fresh data | A wait on a fixed delay; a check right after an action without waiting for the result. Wait on what the user would see |
| **Time of day** | Late in the evening, a default meeting slot is clamped to the end of the day and has already started | Failures clustered at a time. Book for tomorrow in tests that need a future meeting |
| **Shared state between tests** | Tests depending on data another test left, or on demo data | A test that does not reset or make its own data. Each test should create what it needs with unique names |
| **Something off screen** | A lazy list does not compose items off screen; an error banner scrolled out of view | Asserting presence in the tree rather than what is displayed |
| **The environment's data, not the code** | A test against `production` that assumed how many invitations the demo user has | Any test reading data it did not create |
| **Real email timing** | A code that takes longer than the poll to arrive | See below |
| **Cold starts** | A first request after deploy taking a few seconds | Timeouts shorter than about 5 seconds on a first call. Cold starts are now about 2.5 seconds, so a cold start alone rarely explains a failure |

## Tests that read real email

Sign-up and password-reset tests send to a unique address under `mail.mootmaker.com` and poll the shared
SQS queue for a message to that address.

| Symptom | Check |
|---|---|
| No message ever arrives, for every run | `aws ses describe-active-receipt-rule-set --query Metadata.Name` should be `mootmaker-e2e-inbound`. Also check SES sending (see [verification email not arriving](verification-email-not-arriving.md)) |
| Sometimes no message | Another run consumed it: each test must read only messages to its own address and leave others. Check the queue's visibility handling in the email-testing client |
| The wrong code | Two emails to the same address (a resend). Use the newest |

```bash
QUEUE=$(aws ssm get-parameter --name /mootmaker/email-testing/sqs-queue-url --query Parameter.Value --output text)
aws sqs get-queue-attributes --queue-url "$QUEUE" --attribute-names ApproximateNumberOfMessages ApproximateNumberOfMessagesNotVisible
```

## Reproducing

- **Run it in a loop** against an ephemeral environment: `for i in $(seq 20); do ./acceptance/run.sh <env> -g "<test name>" || break; done`
  (web app; similar for the others).
- **Change the timing deliberately**: slow the network in the browser's developer tools, or hold a fake
  server's response, as the web app's `reconcileLink` tests do.
- **Run it at the time it failed.** A failure that only happens at 23:30 needs a clock set to 23:30.

When the cause is found, fix it, add a test that fails deterministically without the fix where possible,
and close the issue with what it was.
