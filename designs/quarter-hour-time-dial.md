# Android: a quarter-hour clock dial for meeting times

## Summary

Meeting start and end times on Android are chosen from drop-down lists of quarter hours today. This
replaces them with a "Select time" dialog showing a clock dial like the Android Clock app's, built by
the app itself so that the minute dial offers only what the API accepts: 00, 15, 30 and 45. It
resolves [mootmaker-android#28](https://github.com/geoffweatherall/mootmaker-android/issues/28),
option 3.

## Status

**Building**: 2026-10-09. Drafted by Claude after Geoff chose option 3, having tried option 2
(mootmaker-android#33) on his phone. Not yet moved to Ready by Geoff. Built (mootmaker-android#36) and released in
[v5.10.10](https://github.com/geoffweatherall/mootmaker-release/releases/tag/v5.10.10) on 2026-10-10 NZDT,
with the other fixes Geoff approved as a group; waiting on Geoff trying it on his phone.

## Scope / non-goals

**In scope:** the Add meeting and Edit meeting forms' Start time and End time fields; a dialog with a
header, an hour dial, a minute dial and a typed-entry mode; its tests at every layer.

**Not in scope:**

- **Dates.** The date field keeps Material's date picker.
- **Changing the time rules.** End after start, no spanning midnight, the latest default slot: all
  stay exactly as the ViewModel enforces them today.
- **The webapp.** Its MUI dial already has a 15-minute step.

## Trade-offs and decisions

1. **Our own dial, not Material3's `TimePicker`.** Material3 1.3.2's dial fixes its minute labels at
   fives, snaps a tap to five minutes and a drag to any minute, and keeps the hand's angle in private
   state. Option 2 (#33) corrected the minute after the fact; the hand then stayed where the finger
   left it, and making it follow needed synthetic taps found through Material's private strings. Geoff
   tried it and preferred not to keep it. A dial of our own draws exactly what is allowed and has no
   hidden state to fight.
2. **The minute dial shows only 00, 15, 30 and 45**, at the twelve, three, six and nine o'clock
   positions, large enough to hit easily. A touch or drag selects the nearest of the four by angle.
   The webapp greys out the other eight labels; four clear targets are simpler to hit on a phone.
3. **The hour dial matches the Clock app.** In 24-hour mode it has two rings, 0 to 11 outside and 12 to
   23 inside, as in Geoff's screenshots of the Clock app; in 12-hour mode one ring of 1 to 12 and an AM/PM
   toggle. Picking an hour moves on to the minutes, as the Clock app does.
4. **Material's look, our behaviour.** Colours, shapes and type come from the app's Material3 theme
   (the selector circle and hand in `primary`, the dial face in `surfaceContainerHighest`, the header
   boxes like Material's), so the dialog looks at home beside the date picker.
5. **Typed entry reuses Material's `TimeInput`**, rounded to the nearest quarter on OK, as #33 does.
   Its minute field cannot be limited to quarters, and typing is also what the acceptance tests use.
6. **All geometry is pure Kotlin, tested exhaustively.** Angle to hour (by ring), angle to quarter,
   hour and minute to label positions, 12/24-hour conversion: plain functions in the `data` module,
   with no Compose types, so every angle and every hour can be checked, not a sample.
7. **TalkBack can use the dial without touching it.** Every number on the dial is a selectable node
   with its own label ("9 hours", "15 minutes", the selected one marked selected), so a screen reader
   can pick a time, and the tests pick times the same way rather than by coordinates.
8. **#33 is closed, not merged.** Its dialog shell, typing mode, rounding functions, `pickTime`
   acceptance helper and tests are carried into the new branch; its dial workaround is not.

## Choices you had me make

- Four minute labels rather than twelve with eight greyed out (Decision 2).
- The hour and minute selection circles' size (48dp, Material's touch-target minimum).

## Open questions

**Blocking:** none.

**Non-blocking:** whether the dial should animate the hand between positions (Material's does).
It is built without animation first; adding it later changes no behaviour.

## Impacts on components

All in `mootmaker-android`:

- **New `app/.../addmeeting/QuarterHourDial.kt`:** the dial composable (face, labels, hand, gestures,
  semantics) and the dialog around it.
- **New `data/.../meeting/TimeDial.kt`:** the geometry and conversions.
- **`AddMeetingScreen.kt`:** Start and End time fields open the dialog instead of a menu.
- **Acceptance helpers:** `pickTime(field, time)` from #33, typing the time.

## Changes to the domain data model and data storage models

N/A: display only.

## Technical considerations

- Times stay `LocalTime` on the form and naive local date-times on the wire, as today.
- Gesture handling uses `pointerInput` with `detectTapGestures` and `detectDragGestures` over the
  dial; while dragging, the hand follows the finger's angle and the selection is the nearest allowed
  value, so what the hand points at and what the header shows always agree.
- Right-to-left layouts keep the clock face as a clock: the dial is not mirrored.
- **What this leaves behind:** nothing; no state outside the dialog.

## Testing impacts

- **Unit (`data`):** angle to quarter for every whole degree; angle and radius to hour for every
  degree on both rings in both modes; label positions round-trip to their own values; 12/24-hour
  conversion for every hour; rounding typed minutes for all 60.
- **Flow (Robolectric):** pick a time by touch (tap on a label's position), by drag (start on one
  label, end between two), and by semantics (TalkBack's path); Cancel leaves the field unchanged;
  OK applies it; 12-hour mode with AM/PM; typed entry rounds; the header and the selected label always
  agree after every gesture. Carried from #33 where they apply.
- **Screenshots:** the dialog's hour and minute dials in light, dark and 200% font, 12- and 24-hour.
- **Acceptance:** #33's `pickTime` typing helper in F.42, F.43, N.103 and O.113, which passed on
  the emulator there.
- **Not affected:** the instrumented tests outside acceptance, the Maestro smokes (they book through
  the API or accept the form's default times), and mootmaker-release's smoke suite.

## Documentation impacts

`use-cases.md`'s F.41 Android link if its test moves; the Android README's form description if it
names the drop-downs.

## Rollout & migration

An ordinary release; nothing persists.

## Risks

- **Gesture maths edge cases** (the boundary between two quarters, the inner and outer hour rings):
  covered exhaustively by the unit tests above.
- **Small or crowded dials at 200% font:** the labels are drawn at a fixed size, as Material's are, and
  the 200% screenshot pins how it looks.

## Implementation checklist

1. [Claude] Geometry and conversions in `data`, with exhaustive unit tests.
2. [Claude] The dial and dialog, the form wired to them, flow tests and screenshots, #33's acceptance
   changes carried over. One PR with acceptance.
3. [Claude] Close #33; a release.
4. [Geoff] Try it on the phone.

## Definition of done

The new tests and the whole acceptance suite are green, released, and Geoff is happy with it on the
phone.
