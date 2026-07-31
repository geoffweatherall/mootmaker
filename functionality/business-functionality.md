# Mootmaker — Business Functionality

This document is the authoritative record of the business rules and functionality provided by the Mootmaker system. It is written for a non-technical audience and deliberately excludes technical implementation detail.

Going forward, this file is the source of truth for what the system does. New functionality is added here first, in the same bullet style, before any corresponding code or test changes are made. Each commit to this file is intended to double as a release note for stakeholders — a summary of what changed for users, and why.

## Accounts and Sign-In

- Anyone can create their own account (self-service sign-up) by providing a name, email address, and password — no administrator approval is required.
- A new account must be verified before it can be used: after signing up, the user receives a confirmation code by email which they must enter before they can sign in.
- Passwords must be at least 10 characters long and include a lowercase letter and a number. This is deliberately loose (there's no requirement for uppercase letters or a special character) because this is a demo system rather than a real business, and the policy is set to match the demo account below.
- Since this is a demo system, anyone can sign in immediately using a shared, publicly-known demo account instead of creating their own — no sign-up needed. Its email and password are shown directly on the home page for signed-out visitors, next to a sign-in form ready to submit with those details already filled in. The password is randomly generated (not a fixed, guessable word — an earlier one turned out to appear on a public list of compromised passwords) but stays easy to type: lowercase letters and digits only. This applies in every deployment, including a "production" one, since making the system easy to try is the whole point.
- Users who forget their password can reset it themselves without contacting support: they request a reset code by email, then enter that code along with a new password to regain access.
- Requesting a password reset never reveals whether a given email address actually has an account — the same response is shown either way, to protect user privacy.
- Every part of the system other than the home page, sign-in, sign-up, and password-reset screens requires the user to be signed in.
- If someone tries to open a page without being signed in, they are taken to the sign-in screen and automatically returned to the page they originally wanted once they've signed in.
- Every account is one of two roles: "standard" or "administrator." A new account is standard by default. This role cannot be changed by the account holder — only granted directly against the underlying system, not through any screen in the product.
- There is currently no self-service way for a user to close or delete their own account.

## People

- Everyone who uses the system — whether they have their own login or not — is represented as a "Person," and a Person's name is required.
- Signing up for an account automatically creates a matching Person record, using the name given at sign-up.
- The system also supports adding people who do not have their own account or login (for example, a visiting guest), and they can then be booked as the organiser or an attendee of a meeting on their behalf. Adding a person this way is an administrator-only action, done from the Settings screen (see [Administration](#administration)).
- Any signed-in user can change their own name at any time, from the Settings screen. An administrator can also change any person's name, whether or not that person has their own account. Wherever a person's name is used elsewhere in the system — meeting listings, calendars — the updated name appears immediately.

## Rooms

- A room is defined by a name and a capacity — the maximum total number of people, including the organiser, that the room can hold for a meeting.
- A room's capacity must be at least 2 people.
- Adding a new room, or editing an existing room's name or capacity, is an administrator-only action, done from the Settings screen (see [Administration](#administration)). Reducing a room's capacity below the size of a meeting already booked into it is allowed — the existing meeting is simply not re-checked against the new, smaller capacity.
- Rooms cannot currently be removed once created.

## Business Hours

- The business day runs from 08:00 to 17:00. This is the one definition of "business hours" used throughout this document and the system — for example, it is the window shown on the daily room-availability view described below.

## Meetings

- A meeting reserves a specific room for a specific block of time, on behalf of an organiser, with an optional list of other attendees.
- Every meeting must have a subject; it cannot be left blank.
- A room can only host one meeting at a time: the system will not allow a new meeting whose time overlaps with an existing meeting for the same room. A meeting is allowed to start the instant an earlier meeting in the same room ends.
- The total number of people at a meeting — the organiser plus all attendees — cannot exceed the room's capacity.
- A meeting's start and finish times must fall on a five-minute boundary (for example 10:15 or 10:20, but not 10:13), keeping scheduling consistent across the system.
- There is no limit on how far in advance, or how far in the past, a meeting can be scheduled.
- Any signed-in user can create a meeting and may organise it on behalf of any person in the system, not only themselves.
- If a meeting or room can't be saved because it breaks one or more rules, every problem is reported back at once, so it can be corrected in a single attempt rather than discovered one issue at a time.
- Once a meeting has been made there is currently no way to cancel or change it.
- The system currently assumes all users share the same time zone; meeting times are not converted or adjusted between time zones.
- Booking a meeting is now available directly from the home page ("Add Meeting"), as well as from the daily room-availability view, and is a two-step process: the meeting's subject, time, and attendees are entered first, and the room is chosen last, once those are known — the room step needs to know how many people are coming and when before it can help pick one. The form defaults the organiser to the signed-in user (when they have a linked Person), the start time to the next 15-minute boundary from now, and the length to one hour.
- On the room step, a "Suggest a room" button finds the smallest room with enough capacity for the organiser plus all attendees that has no other meeting booked over the chosen time, and fills it in. Pressing it again when a room is already chosen suggests a different room with just sufficient capacity, rather than repeating the same one. If no room qualifies, the user is told so and can adjust the attendees or time themselves.

## Calendar Views

- A daily room-availability view shows every room for a chosen day (defaulting to today) as a row spanning business hours, with each existing meeting shown as a blocked-out segment across the portion of the day it occupies, labelled with as much of the meeting's subject as fits.
- A person calendar view shows the meetings a chosen person is organising or attending, as a wall calendar covering the current work week and the five following work weeks (Monday to Friday only). Each day lists its meetings in time order, showing the start and end time, the subject, and the room. The person is chosen from a searchable list — typing any part of a name narrows it down to matching people, which keeps this usable as the number of people grows.
- Once signed in, both views can be reached from the home page and from the main navigation menu ("Availability" and "Calendar"), and each has its own URL reflecting the day or person being viewed, so it can be shared with another signed-in user to show them the same view. Both places default the calendar view to the signed-in user's own calendar.
- These calendar views replace the earlier flat lists of every person, every room, and every meeting, which have all been removed — rooms and meetings are now browsed through the daily room-availability view rather than as undifferentiated lists. A form to add a meeting remains available, reached from that view; adding or editing a room has moved to the Settings screen (see [Administration](#administration)).
- Signed-in users also see two agenda lists on the home page: the meetings they're organising or attending "Today" and "Tomorrow", each sorted by start time and showing the subject, time, and room.
- Signing in doesn't always mean there's a Person to show a calendar for — the demo account and the e2e test account are both examples of a sign-in with no matching Person. Rather than guessing (which used to mean showing a different, unrelated person's private calendar and meetings), the home page shows a clear "your account hasn't been set up properly" message instead, and the navigation menu's "Calendar" item is disabled.
- Signed-out visitors to the home page see none of the above — since every part of the system requires sign-in, there's nothing to show them yet. Instead the home page offers two ways in: an embedded sign-in form pre-filled with the demo account's details (see Accounts and Sign-In) ready to submit, and a "sign up for your own account" section that spells out the three steps involved before showing the sign-up button.

## Notifications

- Users receive an automated email containing a verification code when they sign up, and again if they request a password reset.
- There are currently no email or in-app notifications for meetings — no meeting confirmations, no reminders before a meeting, and no cancellation notices.

## Design and User Experience

- The application's visual design follows Google's Material Design language, for a clean, consistent, and familiar look and feel.
- Screens that list information show a clear loading indicator while data is being fetched, and a similar indicator while data is being refreshed in the background.
- Save buttons disable themselves and show a progress indicator while a submission is in progress, preventing accidental duplicate submissions.
- When something goes wrong — whether a connection problem or a broken business rule — the user sees a clear, dismissible message explaining what happened or what needs to be fixed.
- Navigation is a vertical menu down the left of the page (Home, Calendar, Availability, then Sign in/Sign up or Sign out, then About and Feedback), always visible on wider screens; on a narrow screen it collapses behind a menu button that opens the same menu as a flyout. Once signed in, the signed-in user's name and a settings shortcut appear at the bottom of the menu.

## Administration

- The Settings screen, reached from a shortcut at the bottom of the main navigation menu (see [Design and User Experience](#design-and-user-experience)), is where every account manages its own name. Administrators see two additional sections on the same screen: a list of every room, with the ability to edit a room's name/capacity or add a new one, and a list of every person, with the ability to edit anyone's name or add a new person (including a guest with no account of their own — see [People](#people)). Standard users see only the name section.
- There is still no separate reporting or usage-metrics dashboard.
- A data-reset function exists that erases all rooms and meetings, and every person without a linked account. It is intended for testing purposes, and is not reachable by any user of the product — it's an operational tool (`mootmaker-tools/database-reset`) invoked directly with AWS credentials, not part of the API surface at all.

## Not Yet Implemented

The following functionality has been discussed but is not yet built. It is recorded here as a starting point for future enhancements to this document:

- Recurring meetings (for example, a weekly standup).
- Editing or cancelling an existing meeting.
- Removing a room once created.
- Closing/deleting one's own account.
- Signing up or signing in using an existing Google account.
- Usage metrics and reporting.
- A custom brand theme, including a dark mode, in place of the current default Material Design styling.
- An Android app offering the same functionality as the web application.
