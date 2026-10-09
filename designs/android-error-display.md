# Android: one way to show errors, pinned where they can be seen

## Summary

A save the API refuses on Edit meeting shows its errors in a banner at the top of the scrolling form,
above where the user is looking, so all they see is a thin red line
([mootmaker-android#35](https://github.com/geoffweatherall/mootmaker-android/issues/35)). A survey of
every screen found five different ways of showing an error, the same hidden-error bug on Meeting
details and Home, and a refresh failure on Room availability that is not shown at all. This sets one
standard, a banner pinned under the title bar that never scrolls away, applies it to every screen, and
writes it down as a rule in the Android README.

## Status

**Building**: 2026-10-09. Geoff chose the pinned banner (option B) and asked for it to be the app-wide
standard and documented as a rule. It need not match the webapp. Not yet moved to Ready by Geoff.

## Scope / non-goals

**In scope:** every screen's display of errors from loading, refreshing, saving and acting; two shared
components; the rule in the README; tests.

**Not in scope:**

- **Success messages.** The Toast after leaving a form and Settings' inline "Saved" stay as they are.
- **What errors say.** The messages are unchanged.
- **The webapp.** Geoff asked for Android consistency, not cross-frontend.

## The standard (the rule, as the README will state it)

1. **A screen with nothing to show yet** (its first load failed): the message and **Try again**, filling
   the screen. One shared `LoadFailed` component.
2. **Every other error not about a single field** (a failed refresh, a refused or failed save, response,
   cancel or admin change) appears in **the error banner**, one shared `ErrorBanner` component:
   - **pinned** between the title bar (or, on screens without one, the top of the screen) and the
     scrolling content, so it never scrolls out of view;
   - **every message in full**, one per line, never truncated; with several, all are listed;
   - grows with its messages up to **a third of the screen's height**, then scrolls within itself, so
     every message can still be reached;
   - **dismissible** (×); it also clears when the next attempt succeeds;
   - **Try again** in the banner when the error is a failed refresh;
   - **announced to TalkBack** (a polite live region) when it appears or changes;
   - the error container colours of the Material theme, in light and dark.
3. **Errors inside a dialog stay in the dialog**, since the dialog is what is on screen (cancel
   meeting, delete account, admin deletes).
4. **A field's own problem stays on the field**: Material's error outline and supporting text, for what
   the app checks before calling the API (a missing email, an environment name).

## Trade-offs and decisions

1. **Pinned, not scroll-to-top.** Scrolling up moves the user away from the field they are about to fix
   and the messages scroll away again as they go back down. Pinned, the form stays where it was and the
   messages stay in view while they fix it. Geoff's choice.
2. **One banner per screen, not one per section.** Settings has a Save per section; its messages go to
   the one banner, each prefixed with its section ("Name: …", "Formats: …", "Avatar: …"), so the page
   has one place for errors like every other screen.
3. **Sign in, sign up and reset password use the banner too**, pinned at the top of their form. Their
   current text is already near the top; this makes it the same component and keeps it from scrolling
   away at large font sizes.
4. **A third of the screen at most.** The API returns a handful of short messages, so this is rarely
   reached; when it is (several errors at 200% font), the banner scrolls rather than pushing the form off
   the screen.

## Choices you had me make

- The section prefix on Settings' messages (Decision 2).
- The one-third height limit (Decision 4).

## Open questions

**Blocking:** none.

## Impacts on components

All in `mootmaker-android`, `app/src/main/kotlin/com/mootmaker/app/ui/`:

| Screen | Today | After |
|---|---|---|
| Add / Edit meeting | Banner at the top of the scrolling form (#35) | Pinned banner |
| Meeting details | Action and refresh errors at the top of the scrolling page | Pinned banner, Try again for a refresh |
| Home | Response and refresh errors at the top of the list | Pinned banner, Try again for a refresh |
| Calendar | Refresh error at the top of the content | Pinned banner, Try again |
| Room availability | Refresh error not shown at all | Pinned banner, Try again |
| Admin room and person editors | Errors at the top of the form | Pinned banner |
| Settings | Errors under each section's Save | Pinned banner, messages prefixed by section |
| Sign in, sign up, reset password | Error text above the fields | Pinned banner |
| Every screen's first-load failure | Five copies of `LoadFailed` | One shared `LoadFailed` |
| Dialogs, field errors | Unchanged | Unchanged |

New shared file: `ui/Errors.kt` with `ErrorBanner` and `LoadFailed`.

## Changes to the domain data model and data storage models

N/A: display only.

## Technical considerations

- The banner lives in each screen's `Scaffold` content as a `Column { ErrorBanner(…); scrollingContent }`
  so the scrolling content sits below it; it does not overlay the content.
- Its height limit uses `heightIn(max = screenHeight / 3)` with `verticalScroll` inside.
- **What this leaves behind:** nothing.

## Testing impacts

- **Flow (Robolectric):** for each changed screen, with the content scrolled to the bottom, cause an
  error and assert the banner and every message are **displayed** (`assertIsDisplayed`, in the
  viewport, not merely in the tree). One case per screen; for Add/Edit meeting also several errors at
  once, all displayed; the banner's internal scroll reaches the last message at 200% font; dismiss
  clears it; Try again on a refresh error refetches.
- **Screenshots:** the banner on Add meeting with two errors, light, dark and 200% font; Home with a
  refresh error.
- **Acceptance:** an existing refused-save case asserts its message is displayed after pressing Save at
  the bottom of the form.
- **Unit:** Settings' section prefixes.
- **Not affected:** the instrumented tests outside acceptance; the Maestro smokes.

## Documentation impacts

- **Android README:** a new "Errors" section stating the standard above as a rule for every screen.
- **`testing-strategy.md`:** a line that error displays are tested as displayed, not just present.

## Rollout & migration

Ordinary; nothing persists. Not released until Geoff says: it accumulates with other fixes.

## Risks

- **Many screens touched at once:** each has a flow test that scrolls first and asserts the banner is
  displayed, and the existing tests of each screen keep running.

## Implementation checklist

1. [Claude] `Errors.kt`, the screens above, the tests, the README rule. One PR with acceptance.
2. [Claude] Merge once green; no release until Geoff says.
3. [Geoff] Try it on the phone.

## Definition of done

The new and existing tests and the whole acceptance suite are green, the README rule is in, and Geoff
is happy with it on the phone.
