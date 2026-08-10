# 06 - Option hover/selected fix + transitions

**GitHub:** https://github.com/sanjeebSubedi/InstantQuiz/issues/6
**Parent:** [#1 Gruvbox dark theme + layout improvements](01-gruvbox-dark-theme-layout-improvements.md)
**Labels:** enhancement, ready-for-agent
**Status:** done

## What to build

The player can hover over answer options and clearly read the text. Currently the generic `button:hover` rule applies a dark blue background to `.option` buttons, making text unreadable. The `.option:hover` rule must override the background (to #3c3836, Gruvbox bg1) in addition to border-color.

Selected options show a subtle accent tint (rgba(131,165,152,0.15)) with an #83a598 border and accent-colored text - clearly distinct from hover and unselected states without being visually loud.

All buttons and options gain smooth 150ms transitions on background, border-color, and color properties, so state changes feel polished instead of instant.

## Acceptance criteria

- [x] Hovering an option shows #3c3836 background with #fbf1c7 text - clearly readable
- [x] The generic `button:hover` background no longer bleeds through to options
- [x] Selected option shows accent border + accent text + rgba(131,165,152,0.15) bg
- [x] Hover -> selected -> unselected transitions are smooth (~150ms), not instant
- [x] Transitions apply to all buttons (primary, secondary) and options

## Blocked by

- [#2 Gruvbox dark theme + color system](02-gruvbox-dark-theme-color-system.md) - contrast fix only verifiable on dark background
