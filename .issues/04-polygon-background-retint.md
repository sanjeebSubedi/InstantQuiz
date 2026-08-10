# 04 - Polygon background retint to Gruvbox

**GitHub:** https://github.com/sanjeebSubedi/InstantQuiz/issues/4
**Parent:** [#1 Gruvbox dark theme + layout improvements](01-gruvbox-dark-theme-layout-improvements.md)
**Labels:** enhancement, ready-for-agent
**Status:** done

## What to build

The animated polygon background uses Gruvbox accent colors instead of blue hues. The player sees subtle floating polygons in aqua, green, yellow, orange, and purple tones that complement the dark theme, rather than clashing blue tones that vanish against #282828.

The change is to the CONFIG.colors RGB array in PolygonBackground. The new values are: aqua [131,165,152], green [184,187,38], yellow [250,189,47], orange [254,128,25], purple [211,134,155]. Opacity range stays at 0.025-0.1. If the warmer/brighter Gruvbox colors are too visible at this opacity range, reduce maxOpacity to 0.07.

## Acceptance criteria

- [x] Floating polygons are tinted in Gruvbox accent colors (aqua, green, yellow, orange, purple)
- [x] Polygons are subtle - visible but not distracting against the dark background
- [x] No blue-tinted polygons remain

## Blocked by

- None - can start immediately
