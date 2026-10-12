# Booking refused

A user cannot save a meeting and wants to know why, or thinks the refusal is wrong. Every refusal comes
with a reason code from the API; both apps show a message for each. Background:
[concurrent updates](../overview/concurrent-updates.md) and [data](../overview/data.md#limits).

## What each message means

| Message the user sees | Code | Why | What they can do |
|---|---|---|---|
| The room already has a meeting scheduled during that time range | `TimeRangeUnavailable` | Another meeting overlaps in that room. Back-to-back is fine | Pick another time or room. "Suggest a room" lists free rooms that fit |
| The room does not have enough capacity for all attendees | `InsufficientCapacity` | Organiser plus attendees is more than the room holds | A bigger room, or fewer attendees |
| This day is fully booked… even if a room looks free | `DayIsFull` | 320 meetings already on that date: a storage limit on one day, not a room | Another day. If this happens in real use, raise it: the limit is in `Limits.java` |
| That date is outside the range meetings can be booked in | `OutsideBookableRange` | More than 180 days ahead, or before the retention boundary (30–37 days back) | Another date |
| Start/End time must fall on a 15 minute boundary | `StartMisaligned`, `EndMisaligned` | Times must be :00, :15, :30 or :45 | Fix the time |
| A meeting cannot span midnight | `SpansMultipleDays` | Start and end must be on the same date | Split it |
| End time must be after the start time | `EndBeforeStart` | | Fix the times |
| The organiser cannot also be listed as an attendee | `OrganiserIsAttendee` | The organiser is counted already | Remove them from attendees |
| That is too many attendees for one meeting | `TooManyAttendees` | More than 20 | Fewer attendees |
| The subject is too long | `SubjectTooLong` | Over 280 bytes. Emoji and accented letters use several bytes each | Shorten it |
| …could not be found | `RoomNotFound`, `OrganiserNotFound`, `AttendeeNotFound` | Deleted by an admin since the form loaded | Reload and choose again |
| This meeting no longer exists | `MeetingNotFound` | Cancelled, or older than the retention window | Nothing to edit |
| Someone else changed this meeting after you opened it | `MeetingChanged` | Another edit landed first. Their edit is kept; this one was not saved | Reload, look at their change, edit again |

An error that is *not* one of these (a red banner about the network, a permission message, or "could
not be saved (SomeCode)") is a different problem:

| Sees | Means | Go to |
|---|---|---|
| Couldn't reach Mootmaker / network error | The API did not answer | [Site is down](site-is-down.md) |
| A permission message when editing | Only the organiser or an admin may edit or cancel a meeting | [Admin access](admin-access.md) if they should be an admin |
| "could not be saved (SomeCode)" on Android | A code newer than this app version | [Android app problems](android-app-problems.md#errors-after-an-update) |

## If the refusal looks wrong

Look at the day as the API sees it. As an admin in the app, open Room availability for that date. Or
through the API, with a token for any user (the web app's developer tools show one on every request):

```bash
curl -s "$API" -H "Authorization: $TOKEN" -H 'content-type: application/json' \
  -d '{"query":"{ workspace(dates:[\"2026-10-14\"]) { days { date meetings { subject startTime endTime room { name } } } } }"}'
```

- **A meeting the user cannot see is blocking the room.** Room availability shows every meeting; the
  user's own calendar shows only theirs.
- **The user's screen is stale.** It refreshes when a change is broadcast, but a missed broadcast is
  caught only on reconnect or return to the app. See [changes not showing](changes-not-showing.md).
- **Two people booked at the same moment.** The second was re-checked against the first and refused,
  as designed.

If the API genuinely refused a valid booking, that is a bug: open an issue in mootmaker-api with the
input, the response and the day's contents.
