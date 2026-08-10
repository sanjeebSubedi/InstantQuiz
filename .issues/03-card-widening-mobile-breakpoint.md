# 03 - Card widening + mobile breakpoint

**GitHub:** https://github.com/sanjeebSubedi/InstantQuiz/issues/3
**Parent:** [#1 Gruvbox dark theme + layout improvements](01-gruvbox-dark-theme-layout-improvements.md)
**Labels:** enhancement, ready-for-agent
**Status:** done

## What to build

The quiz card widens from 480px to 720px so questions and content use more of the screen. The top margin reduces from 12vh to 8vh. On mobile (below 640px viewport width), the card becomes full-bleed: no border, no border-radius, no shadow, fills the viewport width, min-height 100vh, and padding reduces to 1.5rem.

This is a layout-only change to the `main` element's CSS. No markup changes.

## Acceptance criteria

- [x] Card max-width is 720px on desktop
- [x] Card top margin is 8vh on desktop
- [x] Below 640px viewport width: card has no border, no border-radius, no box-shadow, 100% width, min-height 100vh, 1.5rem padding
- [x] Content remains readable at both breakpoints

## Blocked by

- None - can start immediately
