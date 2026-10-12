# Changes not showing

One person changes a meeting and another person does not see it, or sees it late. How live updates
work is in [concurrent updates](../overview/concurrent-updates.md).

## What is expected

| Change | Reaches other screens |
|---|---|
| Booking, editing, moving, cancelling a meeting; responding; deleting a person or account | Within about a second, if the other screen is open and connected |
| Renaming or adding a room or person; changing a room's capacity or colour | **Not live.** On the next reconnect, return to the app or tab, or page load |
| Anything, on a screen that was in the background or asleep | When it comes back to the foreground, which refetches everything shown |

So the first question is whether the change was a meeting change at all. A renamed room not appearing
until the other person switches tabs is expected.

## Checks

**1. Reload.** On the web, a page reload. On Android, leave the screen and come back, or put the app in
the background and bring it back. If the change appears, the data was saved and the live update was
missed or not sent. Continue below. If it still does not appear, the change was probably not saved:
ask the person who made it what they saw.

**2. Same environment?** Both must be using the same site. On Android, check the About screen.

**3. Was the broadcast sent?** A failed broadcast is logged and the write still succeeds:

```bash
aws logs filter-log-events --log-group-name /aws/lambda/$ENV-mootmaker-resolvers \
  --start-time $(( ($(date +%s) - 3600) * 1000 )) --filter-pattern '?"Day invalidation broadcast" ?"Failed to broadcast day invalidation"' \
  --query 'events[].message' --output text
```

Any warning here ("Failed to broadcast day invalidation…", "Day invalidation broadcast returned
HTTP…" or "…was rejected by AppSync") means nobody received that change live. They catch up on their
next refetch.

**4. Is the subscription connecting?** In the web app's developer tools, Network, filter `realtime`:
there should be one open WebSocket to `api.<env>.mootmaker.com/graphql/realtime`. If it keeps closing
and reopening, look for errors in the browser console. Corporate proxies sometimes block WebSockets;
the app then works but never live-updates.

**5. The web app's own-write window.** A tab ignores broadcasts for a date it wrote itself for
5 seconds, so a different change to the same date by someone else within those 5 seconds is not shown
until the next refetch. This is a known, accepted trade-off.

## If it is reproducible

Two browsers side by side (or a browser and the Android app) on the same day, one booking and one
watching, is the test. The acceptance suites do exactly this (`live-updates.spec.ts`,
`cross-client-updates.spec.ts` in the web app; `LiveUpdatesAcceptanceTest` and `CacheAcceptanceTest`
on Android). A reproducible miss is a bug: open an issue in the client's repository with the steps.
