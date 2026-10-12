# Admin access

Granting or removing admin access, or an admin change that has not taken effect. Roles are explained in
[identity and access](../overview/identity-and-access.md#roles-and-what-they-allow).

## Granting or removing admin

An admin does it in the app: **Persons → edit → Admin**. It needs the person to have an account (a
guest Person has nothing to grant), and nobody can remove their own admin access.

Without an admin to hand, an operator can set it directly. Do both, in this order, as the API does:

```bash
# 1. Find the account and its Person id
aws cognito-idp admin-get-user --user-pool-id "$POOL" --username someone@example.com \
  --query 'UserAttributes[?Name==`custom:personId`].Value' --output text

# 2. The display copy on the Person
aws dynamodb update-item --table-name $ENV-mootmaker-people --key '{"id":{"S":"<personId>"}}' \
  --update-expression 'SET isAdmin = :t' --expression-attribute-values '{":t":{"BOOL":true}}' \
  --condition-expression 'attribute_exists(id)'

# 3. The role the API actually checks
aws cognito-idp admin-update-user-attributes --user-pool-id "$POOL" --username someone@example.com \
  --user-attributes Name=custom:class,Value=admin
```

Use `standard` and `false` to remove it.

## A change that has not taken effect

| Symptom | Cause | Fix |
|---|---|---|
| Granted admin, but the person cannot see Rooms and Persons | The role is read from their sign-in token, which was issued before the change | Sign out and in again, or wait up to an hour for the token to refresh |
| The Persons page offered **Retry** after saving | The Person was updated but Cognito was not (`cognitoSyncFailed`). The badge shows admin, the token does not grant it | Press Retry. If it keeps failing, set `custom:class` by hand (step 3 above) and look at the resolver log for the Cognito error |
| Removed admin, but they can still use admin features | Their current token still says admin, for up to an hour | Wait. `aws cognito-idp admin-user-global-sign-out` stops them getting new tokens, but a token already issued stays valid until it expires |
| The Admin switch is disabled | The person is a guest with no account, or it is your own Person | Expected |

## The demo account is an admin

`demo@mootmaker.com` is an admin in every environment, so any visitor can change rooms and people in the
public demo. That is deliberate. If the demo has been vandalised, see
[demo data missing or wrong](demo-data-missing.md).
