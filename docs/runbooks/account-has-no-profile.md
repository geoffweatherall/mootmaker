# Account has no profile

The user signs in, but the home page says **"Your account hasn't been set up properly — no profile
could be found for your sign-in."** Calendar is disabled, they cannot be organiser or attendee by
default, and they cannot change their name, preferences or responses.

## Why it happens

Every account should have a Person, created by the post-confirmation trigger when the sign-up is
confirmed. The account has no Person when:

| Cause | How to tell |
|---|---|
| The trigger failed (a DynamoDB error, a throttle). It logs and carries on rather than failing the sign-up | An `ERROR` in the trigger's log at the sign-up time |
| An admin deleted the user's Person, but the deletion of the account itself failed | The account exists; no Person names it |
| The account was confirmed by an admin in a way that skipped the trigger, or created directly | No trigger log line at all for that time |
| It is `e2e-no-person-user@mail.mootmaker.com` in an ephemeral environment | Deliberate: it exists to test this screen |

```bash
aws logs filter-log-events --log-group-name /aws/lambda/$ENV-mootmaker-post-confirmation-create-person \
  --start-time $(( ($(date +%s) - 86400*7) * 1000 )) --filter-pattern ERROR \
  --query 'events[].message' --output text
```

## Fix

`database-repair` creates a Person for every confirmed account whose link is missing or points at a
Person that no longer exists, and writes the link back to the account. The new Person is named after
the part of the email before the `@`; the user can rename themselves in Settings afterwards. Run it as
a dry run first:

```bash
aws lambda invoke --function-name $ENV-mootmaker-database-repair \
  --cli-binary-format raw-in-base64-out --payload '{"dryRun": true}' \
  --cli-read-timeout 900 /dev/stdout

aws lambda invoke --function-name $ENV-mootmaker-database-repair \
  --cli-binary-format raw-in-base64-out --payload '{}' \
  --cli-read-timeout 900 /dev/stdout
```

The user then needs to **sign out and in again**: the link to their Person (`custom:personId`) travels
in their token, and their current token was issued without it.

In an ephemeral environment the repair also gives the deliberate no-Person fixture user a Person,
which breaks the tests of this screen until the next `database-reset` puts it back.

## If it keeps happening

More than one new account in a week without a Person means the trigger is failing, not that a user was
unlucky. Read the trigger's errors (above) and open an issue in mootmaker-api with them.
