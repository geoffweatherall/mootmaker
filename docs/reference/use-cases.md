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

**Detailed test-case designs added 2026-08-22**: every one of the 99 cases below now has a full,
reviewable test-case design (Given/When/Then, UI-level steps, assertions, explicit "out of scope"
notes) in
[mootmaker-webapp/acceptance/test-cases/](https://github.com/geoffweatherall/mootmaker-webapp/tree/main/acceptance/test-cases) —
"designed" is not the same as "automated": see that catalog's own README for which of the 99 are
actually implemented yet (still just the same two as before), the rest being designs ready to build
from. Every item below now links forward to its own webapp test case (`webapp: ...`); an `android:
...` link will follow the same pattern once `mootmaker-android` has an `acceptance/` suite of its
own (the app itself isn't written yet). Each webapp test case links back here too, via a stable
`#uc-N` anchor on this exact item — **renumbering an item here breaks that anchor and the forward
link both**, so prefer adding new items at the end of a section (or the end of the whole list) over
renumbering existing ones. If an item's own wording changes, its anchor and the forward link both
stay valid; only its *content* is now out of sync with what the linked test case was designed
against — that catalog is expected to be re-checked against changes here, not the other way round.

## A. Sign up

1. <a id="uc-1"></a>Sign up with a valid name, email, and password → verification code step → correct code confirms and signs the user in automatically. *(webapp: [A.1](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/a-sign-up.md#tc-a1) · android: not yet automated)*
2. <a id="uc-2"></a>Password below the minimum (10 chars, needs a lowercase letter + a number) is rejected before submission. *(webapp: [A.2](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/a-sign-up.md#tc-a2) · android: not yet automated)*
3. <a id="uc-3"></a>Signing up with an email that already has an account. *(webapp: [A.3](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/a-sign-up.md#tc-a3) · android: not yet automated)*
4. <a id="uc-4"></a>Wrong verification code is rejected; correct code after a wrong attempt still succeeds. *(webapp: [A.4](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/a-sign-up.md#tc-a4) · android: not yet automated)*
5. <a id="uc-5"></a>Newly confirmed account has a linked Person auto-created with the entered name (visible in sidebar/Settings), and is `standard` class (no admin sections in Settings). *(webapp: [A.5](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/a-sign-up.md#tc-a5) · android: not yet automated)*
6. <a id="uc-6"></a>Can immediately schedule a meeting as themselves right after signing up (organiser defaults to them). *(webapp: [A.6](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/a-sign-up.md#tc-a6) · android: not yet automated)*

## B. Sign in / sign out

7. <a id="uc-7"></a>Sign in with correct credentials from `/signin`. *(webapp: [B.7](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/b-sign-in-sign-out.md#tc-b7) · android: not yet automated)*
8. <a id="uc-8"></a>Sign in with correct credentials via the embedded form on the signed-out home page. *(webapp: [B.8](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/b-sign-in-sign-out.md#tc-b8) · android: not yet automated)*
9. <a id="uc-9"></a>Wrong password shows an error, doesn't sign in. *(webapp: [B.9](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/b-sign-in-sign-out.md#tc-b9) · android: not yet automated)*
10. <a id="uc-10"></a>Unknown email shows an error (check whether it distinguishes "no such user" — API's Cognito settings should behave consistently). *(webapp: [B.10](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/b-sign-in-sign-out.md#tc-b10) · android: not yet automated)*
11. <a id="uc-11"></a>Sign in via the demo user's pre-filled credentials shown on the home page. *(webapp: [B.11](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/b-sign-in-sign-out.md#tc-b11) · android: not yet automated)*
12. <a id="uc-12"></a>Session persists across a page reload (token cached/refreshed from `localStorage`). *(webapp: [B.12](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/b-sign-in-sign-out.md#tc-b12) · android: not yet automated)*
13. <a id="uc-13"></a>Sign out clears the session and returns the user to a locked-down state (protected pages redirect to sign-in again). *(webapp: [B.13](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/b-sign-in-sign-out.md#tc-b13) · android: not yet automated)*
14. <a id="uc-14"></a>Visiting a protected route while signed out redirects to `/signin`, and signing in returns you to that original destination. *(webapp: [B.14](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/b-sign-in-sign-out.md#tc-b14) · android: not yet automated)*
15. <a id="uc-15"></a>Visiting the public pages (`/`, `/signin`, `/signup`, `/forgot-password`, `/about`) while signed out works without redirect. *(webapp: [B.15](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/b-sign-in-sign-out.md#tc-b15) · android: not yet automated)*

## C. Forgot password

16. <a id="uc-16"></a>Request a reset code for a valid account → enter code + new password → signed in automatically with the new password. *(webapp: [C.16](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/c-forgot-password.md#tc-c16) · android: not yet automated)*
17. <a id="uc-17"></a>Request a reset code for an email with no account behaves identically (no information leak about account existence). *(webapp: [C.17](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/c-forgot-password.md#tc-c17) · android: not yet automated)*
18. <a id="uc-18"></a>Wrong reset code is rejected. *(webapp: [C.18](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/c-forgot-password.md#tc-c18) · android: not yet automated)*
19. <a id="uc-19"></a>New password failing the strength rule is rejected. *(webapp: [C.19](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/c-forgot-password.md#tc-c19) · android: not yet automated)*
20. <a id="uc-20"></a>Sign-in form links to Forgot Password; Forgot Password flow links back to sign-in. *(webapp: [C.20](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/c-forgot-password.md#tc-c20) · android: not yet automated)*

## D. Home page

21. <a id="uc-21"></a>Signed out: shows sign-in form + demo credentials + sign-up steps. *(webapp: [D.21](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/d-home-page.md#tc-d21) · android: not yet automated)*
22. <a id="uc-22"></a>Signed in with a linked Person: shows Calendar/Room availability/Add Meeting entry points plus "Today" and "Tomorrow" agenda lists, sorted by start time, each linking to its meeting's details. *(webapp: [D.22](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/d-home-page.md#tc-d22) · android: not yet automated)*
23. <a id="uc-23"></a>Signed in with a linked Person but no meetings today/tomorrow: empty state shown instead of an empty list. *(webapp: [D.23](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/d-home-page.md#tc-d23) · android: not yet automated)*
24. <a id="uc-24"></a>Signed in with **no** linked Person (e.g. demo/e2e-style account): "account hasn't been set up" message replaces Calendar/agenda; "Room availability today" and "Add Meeting" still work but Add Meeting has no organiser pre-filled. *(webapp: [D.24](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/d-home-page.md#tc-d24) · android: not yet automated)*
25. <a id="uc-25"></a>"Add Meeting" and "Room availability today" both correctly navigate/deep-link (today's date). *(webapp: [D.25](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/d-home-page.md#tc-d25) · android: not yet automated)*

## E. Room Availability (viewing a room's schedule)

26. <a id="uc-26"></a>View room availability for today. *(webapp: [E.26](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/e-room-availability.md#tc-e26) · android: not yet automated)*
27. <a id="uc-27"></a>Navigate to a future date and view that day's schedule. *(webapp: [E.27](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/e-room-availability.md#tc-e27) · android: not yet automated)*
28. <a id="uc-28"></a>Navigate to a past date and view that day's schedule. *(webapp: [E.28](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/e-room-availability.md#tc-e28) · android: not yet automated)*
29. <a id="uc-29"></a>Date picker jump to an arbitrary date (not just next/prev day). *(webapp: [E.29](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/e-room-availability.md#tc-e29) · android: not yet automated)*
30. <a id="uc-30"></a>No rooms exist yet → empty state. *(webapp: [E.30](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/e-room-availability.md#tc-e30) · android: not yet automated)*
31. <a id="uc-31"></a>Rooms exist but none has meetings that day → grid shows with empty lanes. *(webapp: [E.31](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/e-room-availability.md#tc-e31) · android: not yet automated)*
32. <a id="uc-32"></a>A meeting block's tooltip shows subject + time range; clicking it navigates to Meeting Details. *(webapp: [E.32](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/e-room-availability.md#tc-e32) · android: not yet automated)*
33. <a id="uc-33"></a>Multiple overlapping-in-time meetings across different rooms render in their own room's lane without visual confusion. *(webapp: [E.33](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/e-room-availability.md#tc-e33) · android: not yet automated)*
34. <a id="uc-34"></a>Same room, back-to-back meetings (one ending exactly when another starts) both render distinctly, non-overlapping. *(webapp: [E.34](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/e-room-availability.md#tc-e34) · android: not yet automated)*
35. <a id="uc-35"></a>Room identity colour is consistent for the same room across this page and Person Calendar. *(webapp: [E.35](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/e-room-availability.md#tc-e35) · android: not yet automated)*
36. <a id="uc-36"></a>On a narrow/mobile viewport: grid scrolls horizontally, room name column stays pinned, scroll-fade hints appear/disappear correctly at the edges. *(webapp: [E.36](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/e-room-availability.md#tc-e36) · android: not yet automated)*
37. <a id="uc-37"></a>"Add Meeting" button from this page pre-fills the currently viewed date. *(webapp: [E.37](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/e-room-availability.md#tc-e37) · android: not yet automated)*

## F. Add Meeting

38. <a id="uc-38"></a>Add a meeting with all required fields filled in correctly → success, navigates to a relevant view with a confirmation toast. *(webapp: [F.38](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/f-add-meeting.md#tc-f38) · android: not yet automated)*
39. <a id="uc-39"></a>Organiser defaults to the signed-in user's own Person (when resolved and not already changed). *(webapp: [F.39](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/f-add-meeting.md#tc-f39) · android: not yet automated)*
40. <a id="uc-40"></a>Start time defaults to the next 15-minute boundary; end time defaults to an hour later, same calendar day. *(webapp: [F.40](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/f-add-meeting.md#tc-f40) · android: not yet automated)*
41. <a id="uc-41"></a>Time pickers only offer 15-minute-boundary minutes. *(webapp: [F.41](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/f-add-meeting.md#tc-f41) · android: not yet automated)*
42. <a id="uc-42"></a>Picking an end time before the start time / equal to it. *(webapp: [F.42](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/f-add-meeting.md#tc-f42) · android: not yet automated — **⚠ likely unenforced today**: neither the webapp nor the API currently validate this; see the webapp catalog's README)*
43. <a id="uc-43"></a>Picking a start/end time pair that would span midnight. *(webapp: [F.43](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/f-add-meeting.md#tc-f43) · android: not yet automated)*
44. <a id="uc-44"></a>Selecting someone as an attendee removes them from the Organiser dropdown, and vice versa; deselecting frees them up again. *(webapp: [F.44](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/f-add-meeting.md#tc-f44) · android: not yet automated)*
45. <a id="uc-45"></a>Attempting to submit with the organiser also picked as attendee (should be prevented by the UI, but confirm server-side rejection message if forced). *(webapp: [F.45](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/f-add-meeting.md#tc-f45) · android: not yet automated)*
46. <a id="uc-46"></a>Leaving subject blank → validation error. *(webapp: [F.46](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/f-add-meeting.md#tc-f46) · android: not yet automated)*
47. <a id="uc-47"></a>Leaving room unselected → validation error. *(webapp: [F.47](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/f-add-meeting.md#tc-f47) · android: not yet automated)*
48. <a id="uc-48"></a>Leaving organiser unselected (e.g. no linked Person and not manually chosen) → validation error. *(webapp: [F.48](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/f-add-meeting.md#tc-f48) · android: not yet automated)*
49. <a id="uc-49"></a>Selecting a room with capacity less than organiser+attendee count → `InsufficientCapacity` error. *(webapp: [F.49](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/f-add-meeting.md#tc-f49) · android: not yet automated)*
50. <a id="uc-50"></a>Selecting a room/time slot that overlaps an existing meeting in that room → `TimeRangeUnavailable` error. *(webapp: [F.50](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/f-add-meeting.md#tc-f50) · android: not yet automated)*
51. <a id="uc-51"></a>Multiple validation failures at once → all errors listed together in one banner. *(webapp: [F.51](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/f-add-meeting.md#tc-f51) · android: not yet automated)*
52. <a id="uc-52"></a>"Suggest a room" with no rooms free → inline "no room available" message, selection unchanged. *(webapp: [F.52](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/f-add-meeting.md#tc-f52) · android: not yet automated)*
53. <a id="uc-53"></a>"Suggest a room" first press fetches and fills the best-fit (smallest surplus capacity) room; repeated presses cycle through the ranked list and wrap around without repeating early. *(webapp: [F.53](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/f-add-meeting.md#tc-f53) · android: not yet automated)*
54. <a id="uc-54"></a>Changing date/time/attendee count after suggesting a room invalidates the cached suggestion (next press re-fetches). *(webapp: [F.54](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/f-add-meeting.md#tc-f54) · android: not yet automated)*
55. <a id="uc-55"></a>Cancel button discards the form and returns to the previous page. *(webapp: [F.55](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/f-add-meeting.md#tc-f55) · android: not yet automated)*
56. <a id="uc-56"></a>Submit button is disabled and shows a spinner while the mutation is in flight; double-click doesn't double-submit. *(webapp: [F.56](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/f-add-meeting.md#tc-f56) · android: not yet automated)*
57. <a id="uc-57"></a>On mobile width, the form's action buttons stack vertically instead of a cramped row. *(webapp: [F.57](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/f-add-meeting.md#tc-f57) · android: not yet automated)*
58. <a id="uc-58"></a>Error banner and submit-button red flash both appear on a rejected submission, especially noticeable when the banner is scrolled out of view on a long form. *(webapp: [F.58](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/f-add-meeting.md#tc-f58) · android: not yet automated)*

## G. Person Calendar

59. <a id="uc-59"></a>View your own calendar (default when navigating from Home/sidebar). *(webapp: [G.59](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/g-person-calendar.md#tc-g59) · android: not yet automated)*
60. <a id="uc-60"></a>Navigate to a different person's calendar via the person selector (admin and standard user, if permitted). *(webapp: [G.60](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/g-person-calendar.md#tc-g60) · android: not yet automated)*
61. <a id="uc-61"></a>Six-week view shows only work days (Mon–Fri) per week. *(webapp: [G.61](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/g-person-calendar.md#tc-g61) · android: not yet automated)*
62. <a id="uc-62"></a>Navigating between weeks/months. *(webapp: [G.62](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/g-person-calendar.md#tc-g62) · android: not yet automated — **⚠ not currently possible**: this page has no navigation control at all; see the webapp catalog entry)*
63. <a id="uc-63"></a>A day with no meetings vs a day with several, sorted correctly. *(webapp: [G.63](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/g-person-calendar.md#tc-g63) · android: not yet automated)*
64. <a id="uc-64"></a>No people exist yet → empty state (edge case, admin-only-created scenario). *(webapp: [G.64](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/g-person-calendar.md#tc-g64) · android: not yet automated)*
65. <a id="uc-65"></a>Clicking a meeting row navigates to its Meeting Details page. *(webapp: [G.65](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/g-person-calendar.md#tc-g65) · android: not yet automated)*
66. <a id="uc-66"></a>Room colour dot next to each meeting matches the same room's colour on Room Availability. *(webapp: [G.66](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/g-person-calendar.md#tc-g66) · android: not yet automated)*
67. <a id="uc-67"></a>"Calendar" nav item disabled for a signed-in user with no linked Person. *(webapp: [G.67](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/g-person-calendar.md#tc-g67) · android: not yet automated)*

## H. Meeting Details

68. <a id="uc-68"></a>View details of a meeting you organise. *(webapp: [H.68](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/h-meeting-details.md#tc-h68) · android: not yet automated)*
69. <a id="uc-69"></a>View details of a meeting you attend but didn't organise. *(webapp: [H.69](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/h-meeting-details.md#tc-h69) · android: not yet automated)*
70. <a id="uc-70"></a>View details of a meeting where you're neither organiser nor attendee (if reachable via a direct link/other calendar). *(webapp: [H.70](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/h-meeting-details.md#tc-h70) · android: not yet automated)*
71. <a id="uc-71"></a>Date shown once, time shown as a start–end range (not two full date-times). *(webapp: [H.71](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/h-meeting-details.md#tc-h71) · android: not yet automated)*
72. <a id="uc-72"></a>"Back" button returns to the previous page (room availability / calendar / home, depending on entry point). *(webapp: [H.72](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/h-meeting-details.md#tc-h72) · android: not yet automated)*
73. <a id="uc-73"></a>Navigating directly to a nonexistent/invalid meeting id. *(webapp: [H.73](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/h-meeting-details.md#tc-h73) · android: not yet automated)*

## I. Settings — Your name (all users)

74. <a id="uc-74"></a>Update your own display name → saved, reflected immediately in the sidebar without a page refresh. *(webapp: [I.74](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/i-settings-your-name.md#tc-i74) · android: not yet automated)*
75. <a id="uc-75"></a>Submit a blank name → validation error. *(webapp: [I.75](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/i-settings-your-name.md#tc-i75) · android: not yet automated)*
76. <a id="uc-76"></a>Section disabled with an explanatory note for an account with no linked Person. *(webapp: [I.76](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/i-settings-your-name.md#tc-i76) · android: not yet automated)*

## J. Settings — Rooms (admin only)

77. <a id="uc-77"></a>Standard user does not see the Rooms section. *(webapp: [J.77](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/j-settings-rooms.md#tc-j77) · android: not yet automated)*
78. <a id="uc-78"></a>Admin adds a new room with a valid name + capacity ≥ 2 → appears in the room list and is immediately selectable in Add Meeting / Room Availability. *(webapp: [J.78](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/j-settings-rooms.md#tc-j78) · android: not yet automated)*
79. <a id="uc-79"></a>Add a room with a blank name → validation error. *(webapp: [J.79](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/j-settings-rooms.md#tc-j79) · android: not yet automated)*
80. <a id="uc-80"></a>Add a room with capacity 1 (or 0/negative) → `CapacityTooLow` error. *(webapp: [J.80](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/j-settings-rooms.md#tc-j80) · android: not yet automated)*
81. <a id="uc-81"></a>Edit an existing room's name/capacity → change reflected everywhere it's referenced (existing meetings, availability view) without a manual refresh. *(webapp: [J.81](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/j-settings-rooms.md#tc-j81) · android: not yet automated)*
82. <a id="uc-82"></a>Reduce a room's capacity below a meeting already booked into it → allowed (not retroactively validated). *(webapp: [J.82](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/j-settings-rooms.md#tc-j82) · android: not yet automated)*
83. <a id="uc-83"></a>A standard user attempting the `updateRoom`/`createRoom` operations directly (bypassing the UI) is rejected server-side regardless of what the UI would show. *(webapp: [J.83](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/j-settings-rooms.md#tc-j83) · android: not yet automated)*

## K. Settings — People (admin only)

84. <a id="uc-84"></a>Standard user does not see the People section. *(webapp: [K.84](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/k-settings-people.md#tc-k84) · android: not yet automated)*
85. <a id="uc-85"></a>Admin adds a new person (e.g. a guest with no login) → appears in People, selectable as organiser/attendee/calendar subject. *(webapp: [K.85](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/k-settings-people.md#tc-k85) · android: not yet automated)*
86. <a id="uc-86"></a>Add a person with a blank name → validation error. *(webapp: [K.86](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/k-settings-people.md#tc-k86) · android: not yet automated)*
87. <a id="uc-87"></a>Admin edits another person's name → reflected in their calendar, past/future meetings, and (if linked to a Cognito account) that account's next sign-in / display name. *(webapp: [K.87](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/k-settings-people.md#tc-k87) · android: not yet automated)*
88. <a id="uc-88"></a>Admin renaming a person NOT linked to a Cognito account (no auth-side propagation needed). *(webapp: [K.88](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/k-settings-people.md#tc-k88) · android: not yet automated)*

## L. Authorization boundaries

89. <a id="uc-89"></a>Standard user cannot reach admin-only UI (Rooms/People sections hidden) — a presentation-only check. *(webapp: [L.89](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/l-authorization-boundaries.md#tc-l89) · android: not yet automated)*
90. <a id="uc-90"></a>Standard user directly invoking an admin mutation is rejected (belongs more in API-level testing, but worth a UI-adjacent smoke test). *(webapp: [L.90](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/l-authorization-boundaries.md#tc-l90) · android: not yet automated)*
91. <a id="uc-91"></a>Self-rename works for a standard user; renaming someone else does not (UI shouldn't offer it, and server should reject if forced). *(webapp: [L.91](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/l-authorization-boundaries.md#tc-l91) · android: not yet automated)*

## M. Cross-cutting / non-functional

92. <a id="uc-92"></a>Loading states: spinner on first load, slim progress bar on background refetch with stale data still shown. *(webapp: [M.92](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/m-cross-cutting.md#tc-m92) · android: not yet automated)*
93. <a id="uc-93"></a>Network/transport error (e.g. API unreachable) surfaces a readable message in the error banner, not a blank/broken page. *(webapp: [M.93](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/m-cross-cutting.md#tc-m93) · android: not yet automated)*
94. <a id="uc-94"></a>Expired/invalid session mid-use → next API call fails gracefully, ideally prompting re-authentication. *(webapp: [M.94](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/m-cross-cutting.md#tc-m94) · android: not yet automated)*
95. <a id="uc-95"></a>Deep link directly to a client-side route (e.g. `/meetings/add`) loads the SPA correctly rather than 404ing. *(webapp: [M.95](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/m-cross-cutting.md#tc-m95) · android: not yet automated)*
96. <a id="uc-96"></a>Light/dark mode follows OS `prefers-color-scheme` correctly on every page. *(webapp: [M.96](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/m-cross-cutting.md#tc-m96) · android: not yet automated)*
97. <a id="uc-97"></a>Mobile nav flyout opens/closes correctly, including auto-closing after navigating to any page (Settings included). *(webapp: [M.97](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/m-cross-cutting.md#tc-m97) · android: not yet automated)*
98. <a id="uc-98"></a>Data edited in one place (e.g. a room renamed in Settings) is consistent everywhere it's cached (meeting lists, availability grid) without needing a manual refresh. *(webapp: [M.98](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/m-cross-cutting.md#tc-m98) · android: not yet automated)*
99. <a id="uc-99"></a>Refreshing the page picks up any changes made outside the current session (cache reset). *(webapp: [M.99](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/m-cross-cutting.md#tc-m99) · android: not yet automated)*

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
- **Three inconsistencies between this list's wording and the actual webapp/API implementation**
  were found while writing the detailed test-case catalog (2026-08-22), with full detail in
  [mootmaker-webapp/acceptance/test-cases/README.md](https://github.com/geoffweatherall/mootmaker-webapp/blob/main/acceptance/test-cases/README.md)'s
  "Known doc/code drift" / "Known implementation gaps" sections: case 40's "5-minute boundary"
  start-time default was stale wording (**fixed 2026-08-22** — the rule itself was tightened to 15
  minutes system-wide, not just the wording corrected; case 41's picker-step wording was updated to
  match); case 42's expectation that an end-before-start time range is rejected doesn't appear to
  be enforced anywhere, client or server (still open — flagged ⚠ above); and case 62's week/month
  navigation doesn't exist in the current `PersonCalendarPage` at all, no controls beyond the person
  selector (still open — flagged ⚠ above). Cases 42 and 62 are still a decision for whoever owns
  this list and the corresponding code (update the wording, or build/fix the behaviour) — not
  something a documentation pass should resolve unilaterally.
