# App is slow

Screens take a long time to load, or saving takes several seconds. What normal looks like is in
[performance](../overview/performance.md): about a third of a second for a warm request, and two to
three seconds when a request has to start a new Lambda instance.

## Is it the cold start?

The first request after a quiet spell starts a new instance and takes two to three seconds; the next
ones are fast. At demo traffic levels about one request in five is cold. If the user reports "the first
screen is slow and then it is fine", that is this, and it is expected
([mootmaker-api#114](https://github.com/geoffweatherall/mootmaker-api/issues/114) is looking at
shortening it).

## Measure it

Every invocation logs a `REPORT` line; restored (cold) ones also carry `Restore Duration`:

```bash
aws logs filter-log-events --log-group-name /aws/lambda/$ENV-mootmaker-resolvers \
  --start-time $(( ($(date +%s) - 3600) * 1000 )) --filter-pattern '"REPORT RequestId"' \
  --query 'events[].message' --output text \
  | grep -oE 'RequestId: \S+\s+Duration: [0-9.]+ ms' | awk '{print $(NF-1)" ms"}' | sort -n | tail
```

| What you find | Means | Next |
|---|---|---|
| Durations in the hundreds of milliseconds | The API is fine; the time is elsewhere | The user's network, or the client. In a browser, the Network tab shows each request's timing |
| A few 2–3 second requests, each with a `Restore Duration` | Cold starts | Expected |
| Many slow warm requests | Something in the API is slow | Below |
| `Task timed out after 15` | A request hit the 15-second limit | Below; also look for a loop or a stuck downstream call |

## Slow warm requests

```bash
aws logs tail /aws/lambda/$ENV-mootmaker-resolvers --since 1h --filter-pattern '?WARN ?ERROR'
```

- **DynamoDB throttling or errors.** Tables are on-demand, so throttling means an extreme burst, usually a
  runaway test or a bulk job (demo-data) running at the same time.
- **Write contention on one day.** Many simultaneous bookings on the same date retry (up to five times)
  and slow each other down. Only plausible under a load test or a bulk import.
- **A large request.** A calendar asking for six weeks of a busy office returns a lot of data; the limits
  (42 dates, 2,000 meetings) bound it. Room availability for one day is small.
- **AWS itself.** Check the [AWS Health Dashboard](https://health.aws.amazon.com/health/status) for
  Lambda, AppSync or DynamoDB in `us-east-1`.

## Slow in the client

- **Web**: a slow first load with a fast API is usually the network or a cold browser cache; the static
  files come from CloudFront. A slow screen switch should not happen: screens show cached data at once
  and refresh in the background.
- **Android**: the first open after starting the app has nothing cached and shows a full spinner; after
  that, screens draw from the app's store at once.

If a specific action is reproducibly slow with fast API timings, open an issue in the client's
repository with the steps and a recording.
