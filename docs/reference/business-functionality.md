# What Mootmaker does

The product's rules, in plain language, for a reader who does not need to know how it is built. The
web app and the Android app offer the same features. The numbered, testable version of these rules is
[use-cases.md](use-cases.md); when the two disagree, the use cases and their tests are right and this
page should be corrected.

## Accounts and signing in

- Anyone can create an account with a name, an email address and a password. No approval is needed.
- A new account is confirmed by a code emailed to the address. Until it is confirmed it cannot sign in.
- Passwords need at least 10 characters, including a lowercase letter and a number. This is deliberately
  easy, because Mootmaker is a public demo.
- Names must be unique. Signing up with a name someone already has (ignoring capitals and spaces) is
  refused, because people are chosen by name throughout the app.
- Anyone can sign in straight away with the **demo account**, whose email and password are shown on the
  home page. The demo account is an administrator, so visitors can try every feature.
- A forgotten password is reset with a code sent by email. The reset screen never reveals whether an
  email address has an account.
- Everything except the home page, sign-in, sign-up, password reset and the About page needs the user
  to be signed in. Opening a page while signed out leads to sign-in and then back to that page.
- Every account is **standard** or **administrator**. New accounts are standard. Only an administrator
  can change someone's role, and nobody can remove their own administrator access.
- Users can **delete their own account** from Settings. Their upcoming meetings are cancelled, they are
  removed from meetings they were invited to, and their account, profile and photo are deleted. This
  cannot be undone. The demo account cannot be deleted.

## People

- Everyone who can be in a meeting is a **person**. Signing up creates one automatically.
- Administrators can add people who have no account (for example a visitor), so they can be booked into
  meetings.
- Users can change their own name in Settings; administrators can rename anyone. A new name appears
  everywhere at once.
- Administrators can delete a person. Their upcoming meetings are cancelled and they are removed from
  meetings they were invited to; past meetings are left alone. Deleting a person who has an account
  deletes the account too.
- A person may have a photo; otherwise their initials are shown. Photos are set through the API (the
  demo uses this); neither app has an upload screen yet.

## Rooms

- A room has a name, a capacity (at least 2 people, counting the organiser) and optionally a colour.
- Administrators add, edit and delete rooms. A room with any meeting from now on cannot be deleted.
- Reducing a room's capacity does not affect meetings already booked into it.

## Meetings

- A meeting books one room, for one block of time, for an organiser and any number of attendees up to
  20.
- Every meeting needs a subject.
- A room can hold only one meeting at a time. A meeting may start exactly when another ends.
- The organiser plus the attendees cannot exceed the room's capacity. The organiser cannot also be an
  attendee.
- Start and end times are on the quarter hour (:00, :15, :30, :45), and a meeting starts and ends on the
  same day.
- Meetings can be booked from about a month in the past up to 180 days ahead.
- Any signed-in user can book a meeting and can make anyone the organiser.
- **Suggest a room** offers the free rooms that fit the meeting, smallest first, one at a time.
- When a booking breaks a rule, every problem is listed at once.
- The **organiser** or an **administrator** can edit or cancel a meeting, including moving it to another
  day or room. Cancelling deletes it. If someone else changed the meeting after it was opened for editing,
  the edit is refused rather than undoing their change.
- Each **attendee** answers Going, Maybe or Not going, and can change their answer. Nobody can answer
  for someone else. The organiser has no answer of their own. Editing a meeting keeps everyone's answers.
- A day can hold at most 320 meetings across all rooms. Beyond that a booking is refused even if a room
  is free.
- Meeting times are the office's local time. Mootmaker models one office and never converts times
  between time zones.
- Meetings older than about a month are deleted automatically.

## Screens

- **Home** shows, for the signed-in person, the meetings waiting for their answer (with a way to look
  further ahead) and their meetings today and tomorrow. Signed out, it shows the demo login and how to
  sign up.
- **Room availability** shows every room for a chosen day, with whether it is free now and its meetings.
- **Calendar** shows one person's meetings for a working week (Monday to Friday), a week at a time. It
  opens on the signed-in person; any person can be chosen.
- **Meeting details** shows the room, organiser, attendees and their answers, with a link that can be
  shared with another signed-in user.
- **Settings**: your name; date format (2026-10-14, 14/10/2026 or 10/14/2026), time format (24-hour or
  AM/PM) and which day weeks start on; delete account.
- **Rooms** and **Persons** (administrators only): manage rooms and people, and grant or remove
  administrator access.
- Changes made by other people to meetings appear on screen within about a second, without reloading.
- Both apps follow the device's light or dark setting.
- The web app's Feedback link opens the project's GitHub issues.

## Email

- Mootmaker sends email only for sign-up confirmation and password reset codes.
- There are no meeting invitations, reminders or cancellation emails.

## Not offered

- Recurring meetings.
- Sign-in with Google or another provider ([a design exists](../../designs/google-sign-in.md)).
- Uploading a photo from the app.
- Usage reports.
- Time zones per person or per room.
