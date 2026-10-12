# Wrong time or date

A meeting shows at an unexpected time, "today" seems to be the wrong day, or a date shows in an
unexpected format. The rules are in [time and time zones](../overview/time-and-time-zones.md).

| Symptom | Cause | What to do |
|---|---|---|
| A meeting shows at the time it was booked, but the user is in another time zone and expected it converted | By design: a meeting time is the office's wall-clock time, never converted | Explain. Mootmaker models one office |
| Dates show as `10/14/2026` or `14/10/2026` and the user expected the other | The user's date-format preference | Settings → Date and time format |
| 12-hour versus 24-hour times | The time-format preference | Same place |
| The calendar starts on Sunday | The week-start preference (date pickers only; the weekly calendar is Monday to Friday) | Same place |
| A time shifted by whole hours, on one client only | A client parsed a zone-less time as an instant. A bug | Open an issue in that client's repository with the meeting, what was booked and what is shown |
| "Today" on the home page is the wrong day | The device's date or time zone is wrong. The apps use the device's clock for "today" | Fix the device clock |
| The booking window ends a day earlier or later than expected | The window is computed from the server's UTC date, not the user's | Expected; the window is wide enough not to matter |
| Deleting an account or person removed meetings from earlier the same day, or deleting a room is refused because of a meeting that already happened | The server decides "upcoming" by its UTC clock ([mootmaker-api#113](https://github.com/geoffweatherall/mootmaker-api/issues/113)) | Known. Wait until the end of the day (NZ evening), or delete the meeting first |
| A test that books "now" fails late in the evening | The default slot is clamped to the end of the day and has already started | See [flaky test](flaky-test.md); book for tomorrow in the test |

To see what the API stored, ask for the day (see [booking refused](booking-refused.md#if-the-refusal-looks-wrong)).
A stored time is exactly what the user picked, `2026-10-14T10:00:00`, with no zone.
