# Ephemeral environment problems

An ephemeral environment will not create, will not tear down, or is left over. How they work is in
[delivery](../overview/delivery.md#ephemeral-environments).

## See what exists

```bash
mootmaker-ephemeral-envs/list-ephemeral-envs.sh
```

It lists every environment with Terraform state, how many resources each component's state holds, and
whether those resources really exist in AWS. `0 (empty)` means a state file left by a finished teardown:
nothing to destroy. Kept environments carry a `KEEP` marker with a reason.

## Creation failed

`create-ephemeral-env.sh` deploys the API, then the web app, then optionally demo-data, each with its own
`deploy.sh`. Read which one failed and see [deploy failed](deploy-failed.md). Then tear the half-created
environment down rather than leaving it; the sweep would otherwise remove it after 48 hours.

From a cloud session, `ephemeral-env.yml` tears down a failed create in the same run.

## Teardown failed or stuck

```bash
mootmaker-ephemeral-envs/teardown-ephemeral-env.sh <name>
```

| Error | Cause | Fix |
|---|---|---|
| Refuses the name | Not `<kind>-<YYMMDD>-<rand4>` | Deliberate: the script never touches a non-ephemeral name. `test` and `production` are never torn down this way |
| A component it does not recognise | State exists for a repository it does not know how to undeploy | Undeploy that component by hand with its own `undeploy.sh <name> --yes`, then run teardown again |
| `Error acquiring the state lock` | A deploy or teardown of the same environment is running, possibly the sweep | Wait. Only if nothing is running, `terraform force-unlock` in that component |
| It finished, but resources remain | A destroy that partly failed earlier, or resources made by hand | `list-ephemeral-envs.sh` and `mootmaker-bootstrap-aws-accounts/list-unmanaged-resources.sh` find them |

After a teardown, check nothing is left:

```bash
aws lambda list-functions --query "Functions[?starts_with(FunctionName,'<name>-')].FunctionName"
aws dynamodb list-tables --query "TableNames[?starts_with(@,'<name>-')]"
aws s3 ls s3://remote-state-431071856068/<name>/      # should not exist
```

## Left over

Anything idle for 48 hours is destroyed by the daily sweep unless it is kept. To remove one now, tear it
down. To keep one you are still using:

```bash
mootmaker-ephemeral-envs/keep-env.sh <name> "why it is kept"
mootmaker-ephemeral-envs/unkeep-env.sh <name>
```

A kept environment is listed with its reason and age on every sweep. Remove the keep when you are done;
nothing else will.

## Environment exists but does not work

An environment that half-exists (state but missing resources, or the reverse) is quicker to replace than
to repair: tear it down and create a new one.
