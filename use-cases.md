# Use cases

A starting list of user-focused test use cases across the mootmaker application, drafted during an
earlier planning conversation as a checklist to expand into concrete test cases later. This list is
**client-agnostic** — it describes what must be true of the system, not which frontend proves it or
how. See [testing-strategy.md](testing-strategy.md) for the overall cross-repo layering, and each
frontend's own `testing-strategy.md` (e.g.
[mootmaker-webapp/testing-strategy.md](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/testing-strategy.md#acceptance-tests))
for how its own `acceptance/` suite draws on this list — not every case here applies identically to
every frontend (e.g. a mobile nav flyout is webapp-specific; Android will have its own native nav
patterns for the equivalent scenario), and this doc isn't yet tagged per-frontend.

This is a first pass, not exhaustive, and not yet expanded in detail — expect it to grow.

**Moved here 2026-08-19** from `mootmaker-e2e/use-cases.md` (that repo is now
[mootmaker-test-infra](https://github.com/geoffweatherall/mootmaker-test-infra), and no longer owns
a use-case list or a test suite of its own — see its README's History section). Only a couple of
cases (A.1, F.38) are automated anywhere so far, in
[mootmaker-webapp/acceptance/](https://github.com/geoffweatherall/mootmaker-webapp/tree/main/acceptance) —
the rest of this list is still just a checklist, not a coverage report.

## A. Sign up

1. Sign up with a valid name, email, and password → verification code step → correct code confirms and signs the user in automatically.
2. Password below the minimum (10 chars, needs a lowercase letter + a number) is rejected before submission.
3. Signing up with an email that already has an account.
4. Wrong verification code is rejected; correct code after a wrong attempt still succeeds.
5. Newly confirmed account has a linked Person auto-created with the entered name (visible in sidebar/Settings), and is `standard` class (no admin sections in Settings).
6. Can immediately schedule a meeting as themselves right after signing up (organiser defaults to them).

## B. Sign in / sign out

7. Sign in with correct credentials from `/signin`.
8. Sign in with correct credentials via the embedded form on the signed-out home page.
9. Wrong password shows an error, doesn't sign in.
10. Unknown email shows an error (check whether it distinguishes "no such user" — API's Cognito settings should behave consistently).
11. Sign in via the demo user's pre-filled credentials shown on the home page.
12. Session persists across a page reload (token cached/refreshed from `localStorage`).
13. Sign out clears the session and returns the user to a locked-down state (protected pages redirect to sign-in again).
14. Visiting a protected route while signed out redirects to `/signin`, and signing in returns you to that original destination.
15. Visiting the public pages (`/`, `/signin`, `/signup`, `/forgot-password`, `/about`) while signed out works without redirect.

## C. Forgot password

16. Request a reset code for a valid account → enter code + new password → signed in automatically with the new password.
17. Request a reset code for an email with no account behaves identically (no information leak about account existence).
18. Wrong reset code is rejected.
19. New password failing the strength rule is rejected.
20. Sign-in form links to Forgot Password; Forgot Password flow links back to sign-in.

## D. Home page

21. Signed out: shows sign-in form + demo credentials + sign-up steps.
22. Signed in with a linked Person: shows Calendar/Room availability/Add Meeting entry points plus "Today" and "Tomorrow" agenda lists, sorted by start time, each linking to its meeting's details.
23. Signed in with a linked Person but no meetings today/tomorrow: empty state shown instead of an empty list.
24. Signed in with **no** linked Person (e.g. demo/e2e-style account): "account hasn't been set up" message replaces Calendar/agenda; "Room availability today" and "Add Meeting" still work but Add Meeting has no organiser pre-filled.
25. "Add Meeting" and "Room availability today" both correctly navigate/deep-link (today's date).

## E. Room Availability (viewing a room's schedule)

26. View room availability for today.
27. Navigate to a future date and view that day's schedule.
28. Navigate to a past date and view that day's schedule.
29. Date picker jump to an arbitrary date (not just next/prev day).
30. No rooms exist yet → empty state.
31. Rooms exist but none has meetings that day → grid shows with empty lanes.
32. A meeting block's tooltip shows subject + time range; clicking it navigates to Meeting Details.
33. Multiple overlapping-in-time meetings across different rooms render in their own room's lane without visual confusion.
34. Same room, back-to-back meetings (one ending exactly when another starts) both render distinctly, non-overlapping.
35. Room identity colour is consistent for the same room across this page and Person Calendar.
36. On a narrow/mobile viewport: grid scrolls horizontally, room name column stays pinned, scroll-fade hints appear/disappear correctly at the edges.
37. "Add Meeting" button from this page pre-fills the currently viewed date.

## F. Add Meeting

38. Add a meeting with all required fields filled in correctly → success, navigates to a relevant view with a confirmation toast.
39. Organiser defaults to the signed-in user's own Person (when resolved and not already changed).
40. Start time defaults to the next 5-minute boundary; end time defaults to an hour later, same calendar day.
41. Time pickers only offer 5-minute-boundary minutes.
42. Picking an end time before the start time / equal to it.
43. Picking a start/end time pair that would span midnight.
44. Selecting someone as an attendee removes them from the Organiser dropdown, and vice versa; deselecting frees them up again.
45. Attempting to submit with the organiser also picked as attendee (should be prevented by the UI, but confirm server-side rejection message if forced).
46. Leaving subject blank → validation error.
47. Leaving room unselected → validation error.
48. Leaving organiser unselected (e.g. no linked Person and not manually chosen) → validation error.
49. Selecting a room with capacity less than organiser+attendee count → `InsufficientCapacity` error.
50. Selecting a room/time slot that overlaps an existing meeting in that room → `TimeRangeUnavailable` error.
51. Multiple validation failures at once → all errors listed together in one banner.
52. "Suggest a room" with no rooms free → inline "no room available" message, selection unchanged.
53. "Suggest a room" first press fetches and fills the best-fit (smallest surplus capacity) room; repeated presses cycle through the ranked list and wrap around without repeating early.
54. Changing date/time/attendee count after suggesting a room invalidates the cached suggestion (next press re-fetches).
55. Cancel button discards the form and returns to the previous page.
56. Submit button is disabled and shows a spinner while the mutation is in flight; double-click doesn't double-submit.
57. On mobile width, the form's action buttons stack vertically instead of a cramped row.
58. Error banner and submit-button red flash both appear on a rejected submission, especially noticeable when the banner is scrolled out of view on a long form.

## G. Person Calendar

59. View your own calendar (default when navigating from Home/sidebar).
60. Navigate to a different person's calendar via the person selector (admin and standard user, if permitted).
61. Six-week view shows only work days (Mon–Fri) per week.
62. Navigating between weeks/months.
63. A day with no meetings vs a day with several, sorted correctly.
64. No people exist yet → empty state (edge case, admin-only-created scenario).
65. Clicking a meeting row navigates to its Meeting Details page.
66. Room colour dot next to each meeting matches the same room's colour on Room Availability.
67. "Calendar" nav item disabled for a signed-in user with no linked Person.

## H. Meeting Details

68. View details of a meeting you organise.
69. View details of a meeting you attend but didn't organise.
70. View details of a meeting where you're neither organiser nor attendee (if reachable via a direct link/other calendar).
71. Date shown once, time shown as a start–end range (not two full date-times).
72. "Back" button returns to the previous page (room availability / calendar / home, depending on entry point).
73. Navigating directly to a nonexistent/invalid meeting id.

## I. Settings — Your name (all users)

74. Update your own display name → saved, reflected immediately in the sidebar without a page refresh.
75. Submit a blank name → validation error.
76. Section disabled with an explanatory note for an account with no linked Person.

## J. Settings — Rooms (admin only)

77. Standard user does not see the Rooms section.
78. Admin adds a new room with a valid name + capacity ≥ 2 → appears in the room list and is immediately selectable in Add Meeting / Room Availability.
79. Add a room with a blank name → validation error.
80. Add a room with capacity 1 (or 0/negative) → `CapacityTooLow` error.
81. Edit an existing room's name/capacity → change reflected everywhere it's referenced (existing meetings, availability view) without a manual refresh.
82. Reduce a room's capacity below a meeting already booked into it → allowed (not retroactively validated).
83. A standard user attempting the `updateRoom`/`createRoom` operations directly (bypassing the UI) is rejected server-side regardless of what the UI would show.

## K. Settings — People (admin only)

84. Standard user does not see the People section.
85. Admin adds a new person (e.g. a guest with no login) → appears in People, selectable as organiser/attendee/calendar subject.
86. Add a person with a blank name → validation error.
87. Admin edits another person's name → reflected in their calendar, past/future meetings, and (if linked to a Cognito account) that account's next sign-in / display name.
88. Admin renaming a person NOT linked to a Cognito account (no auth-side propagation needed).

## L. Authorization boundaries

89. Standard user cannot reach admin-only UI (Rooms/People sections hidden) — a presentation-only check.
90. Standard user directly invoking an admin mutation is rejected (belongs more in API-level testing, but worth a UI-adjacent smoke test).
91. Self-rename works for a standard user; renaming someone else does not (UI shouldn't offer it, and server should reject if forced).

## M. Cross-cutting / non-functional

92. Loading states: spinner on first load, slim progress bar on background refetch with stale data still shown.
93. Network/transport error (e.g. API unreachable) surfaces a readable message in the error banner, not a blank/broken page.
94. Expired/invalid session mid-use → next API call fails gracefully, ideally prompting re-authentication.
95. Deep link directly to a client-side route (e.g. `/meetings/add`) loads the SPA correctly rather than 404ing.
96. Light/dark mode follows OS `prefers-color-scheme` correctly on every page.
97. Mobile nav flyout opens/closes correctly, including auto-closing after navigating to any page (Settings included).
98. Data edited in one place (e.g. a room renamed in Settings) is consistent everywhere it's cached (meeting lists, availability grid) without needing a manual refresh.
99. Refreshing the page picks up any changes made outside the current session (cache reset).

## Notes

A few things worth flagging separately since they shape *how* you'd test rather than *what*:

- Several rules (validation messages, `OrganiserIsAttendee`, capacity math) are enforced
  server-side and only mirrored client-side for UX — worth deciding whether these get covered at
  the UI layer, the API acceptance-test layer, or both.
- There's one known-hard-to-automate race called out in the webapp README: the organiser-defaulting
  effect on Add Meeting racing a user picking themselves as an attendee before their own `personId`
  resolves. Automating it needs a real signed-up test account with a linked Person (not the bare
  e2e/demo accounts, which have none), plus a deterministic way to win or lose the race against the
  `myPerson` query.
- `AddRoomPage.tsx` exists in the webapp codebase but isn't wired into any route — dead code, not a
  real use case.
- Not yet tagged per-frontend (universal vs. webapp-only vs. android-only) — e.g. #36 and #97's
  mobile-nav-flyout behaviour is webapp-specific UI and won't apply the same way to Android's own
  native navigation. Worth doing once a second frontend's `acceptance/` suite actually exists and
  the distinction stops being hypothetical.
