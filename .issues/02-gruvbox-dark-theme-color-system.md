# 02 - Gruvbox dark theme + color system

**GitHub:** https://github.com/sanjeebSubedi/InstantQuiz/issues/2
**Parent:** [#1 Gruvbox dark theme + layout improvements](01-gruvbox-dark-theme-layout-improvements.md)
**Labels:** enhancement, ready-for-agent
**Status:** done

## What to build

The entire app switches from the current light theme (white card on light gray) to Gruvbox dark. Every surface, text color, border, badge, error state, input field, and button uses the Gruvbox palette. The player sees a dark-themed app across all phases (landing, creating, playing, failed, results).

The CSS custom property set in `:root` is replaced wholesale. Every hardcoded color value elsewhere in the stylesheet is migrated to use the new variables or appropriate Gruvbox values. New variables are introduced for success badges (`--success`, `--success-bg`, `--success-border`), score accent (`--yellow`), and disabled state (`--disabled-bg`, `--disabled-text`).

Primary buttons become accent bg (#83a598) with dark text. Secondary buttons become outlined with accent border and text on transparent bg. Disabled buttons use #504945 bg with #928374 text. Inputs use #3c3836 bg with a new `::placeholder` rule in #928374. Error boxes use Gruvbox red tints. Correct/incorrect badges use Gruvbox green/red with dark-appropriate semi-transparent backgrounds.

The full palette (from the parent spec's Implementation Decisions) is the source of truth for every color value.

## Acceptance criteria

- [x] `:root` custom properties match the palette from the parent spec exactly (17 variables)
- [x] No hardcoded color values remain in the CSS that aren't Gruvbox-native (search for hex values not in the Gruvbox palette)
- [x] Landing page: #282828 page bg, #32302f card surface, #fbf1c7 text, #83a598 accent button with #282828 text
- [x] Input field: #3c3836 bg, #fbf1c7 text, #928374 placeholder, #83a598 focus outline
- [x] Disabled button: #504945 bg, #928374 text
- [x] Correct badge: #b8bb26 text on rgba(184,187,38,0.1) bg
- [x] Incorrect badge: #fb4934 text on rgba(251,73,52,0.1) bg
- [x] Error box (failed screen): #fb4934 text on rgba(251,73,52,0.1) bg with rgba(251,73,52,0.3) border
- [x] Secondary buttons: transparent bg, #83a598 border and text; hover fills with rgba(131,165,152,0.15)

## Blocked by

- None - can start immediately
