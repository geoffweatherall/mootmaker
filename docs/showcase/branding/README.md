# Branding

Brand assets for the mootmaker project family (`mootmaker-webapp`, and the future
`mootmaker-android`). This is prep material — nothing outside this directory references
these files yet. See [palette.html](palette.html) for a human-viewable version of everything
below, including the logo rendered at size.

## The mark: Meeting Booked

A calendar with two overlapping circles badged onto the header, standing in for the two people
about to meet - the same "overlapping avatars" motif used across the industry for
participants/attendees, so the badge reads as *a meeting*, not just *a task done*. Flat, rounded,
Material-language shapes throughout, same container silhouette as the original "Calendar Done"
mark (a calendar with binder rings, a coloured header, and a slot grid) so the refresh reads as
an evolution rather than a different app.

## Files

| Path | Purpose |
|---|---|
| [resources/logo.svg](resources/logo.svg) | Master mark, transparent background, 240×240 viewBox. The source of truth vector - scales cleanly to any size or resolution. Colours are hardcoded hex (not CSS variables), since standalone SVG tooling won't resolve custom properties. |
| [resources/icon.svg](resources/icon.svg) | Same mark on a plain square Paper-coloured canvas, no corner rounding baked in. Ready to export as PNGs at any resolution for favicons, app icons, etc. Platform-specific masking (Android adaptive icon foreground/background split, iOS's own corner rounding) should be derived from this or from `logo.svg` when that work happens, not re-baked into this file. |
| [tokens.css](tokens.css) | CSS custom properties for the UI token set below - light default, dark via `prefers-color-scheme` and via a `data-theme` attribute override. |
| [palette.html](palette.html) | Standalone, self-contained HTML page for visually reviewing the logo and full palette in a browser. |

## Logo colours

Fixed hex values used inside the mark itself - constant regardless of the surrounding app's
theme, the same way most app icons don't recolour when the OS switches theme.

| Name | Hex |
|---|---|
| Ink Violet | `#4338CA` |
| Signal Teal | `#0E8F82` |
| Sunbeam Amber | `#F59E0B` |
| Paper | `#FAF9F6` |

## UI tokens

For the app's own surfaces, text, and accents (see `tokens.css`). `--color-primary`,
`--color-secondary`, and `--color-accent` are the same three logo hues above, reused for the
app's own buttons/links/highlights; they shift to lighter variants in dark mode for contrast,
unlike the logo's fixed colours.

| Token | Light | Dark |
|---|---|---|
| `--color-bg` | `#FAF9F6` | `#17152A` |
| `--color-surface` | `#FFFFFF` | `#201D38` |
| `--color-surface-tile` | `#F4F1EA` | `#ECE8F7` |
| `--color-ink` | `#1E1B2E` | `#F1EFFA` |
| `--color-ink-soft` | `#58527A` | `#B6B0D8` |
| `--color-border` | `#E7E3F6` | `#34305A` |
| `--color-primary` | `#4338CA` | `#8B85F0` |
| `--color-secondary` | `#0E8F82` | `#2DD4BF` |
| `--color-accent` | `#F59E0B` | `#FBBF24` |

## Room-identity palette

A separate 8-hue categorical palette, `--color-room-1` through `--color-room-8`, for colour-coding
rooms in `mootmaker-webapp`'s daily availability grid and person calendar - kept apart from
primary/secondary/accent so a room's colour is never mistaken for a primary-action/warning cue
elsewhere in the UI. Validated (CVD-safe adjacent-pair separation, contrast against `--color-bg`
in both modes) with the Claude Code dataviz skill's palette validator rather than eyeballed; see
`tokens.css`'s own comment and `mootmaker-webapp/webapp/src/theme/tokens.ts` for the full
rationale, including why three of the eight hues (light mode) are always paired with the room's
name as visible text rather than used as colour alone.

## Typography

Two typefaces, both self-hosted via `@fontsource` (no external font request at runtime):
**Inter** (`--font-body`) for body/UI text - a workhorse face built for small sizes in dense forms
and tables - and **Outfit** (`--font-heading`) for headings - geometric with rounded terminals,
echoing this mark's own flat rounded shape language, so headings read as distinctly "Mootmaker"
rather than generic browser-default chrome.

## Status

Wired up in `mootmaker-webapp`: the MUI theme's palette, typography, shadows, and component
styling (buttons, inputs, chips) are all built from the tokens above; `icon.svg` is the favicon,
and `logo.svg` appears next to the app name in the header. Light/dark follows the OS preference
only - there's no in-app toggle (see that project's `ThemeModeProvider.tsx`), though the
`data-theme` override in `tokens.css` is kept in place for if one gets added later. The Android
app doesn't exist as code yet - just an empty repo - so applying the branding there remains
future work.

The webapp's own sidebar/account icons (`mootmaker-webapp/webapp/src/icons/`) are also custom
flat-shape glyphs built to sit alongside this mark, rather than stock Material icons - see that
directory's own doc comment. The home page's hero illustration
(`mootmaker-webapp/webapp/src/assets/home-hero.svg`) reuses the same four-colour palette in the
same flat, rounded, no-gradient style.
