# 05 - Results screen density + button spacing

**GitHub:** https://github.com/sanjeebSubedi/InstantQuiz/issues/5
**Parent:** [#1 Gruvbox dark theme + layout improvements](01-gruvbox-dark-theme-layout-improvements.md)
**Labels:** enhancement, ready-for-agent
**Status:** done

## What to build

The results screen no longer reads like a long receipt. Each review row shows the question on top, then "Your answer" and "Correct answer" side-by-side below it (instead of stacked vertically in a definition list). The score number is displayed in Gruvbox yellow (#fabd2f) as the hero element. The "Play again" and "New topic" buttons sit side-by-side with 1rem gap (matching the prev/next controls pattern). The same side-by-side layout applies to the failed screen's "Retry same topic" / "New topic" buttons.

This requires one markup change: the ReviewRow component's `<dl>` definition list is replaced with flex divs (`review-answers` container with two `review-answer-col` children, each containing a `review-label` span and a value span). The old `dt`/`dd` CSS rules are removed and replaced with the new class selectors.

On mobile (below 640px), the answer columns stack vertically with 0.5rem gap.

## Acceptance criteria

- [x] Review rows show "Your answer" and "Correct answer" side-by-side on desktop
- [x] Review answer columns stack vertically below 640px
- [x] Score displays in #fabd2f (Gruvbox yellow)
- [x] "Play again" and "New topic" buttons are side-by-side with ~1rem gap
- [x] "Retry same topic" and "New topic" on the failed screen are also side-by-side with ~1rem gap
- [x] Old `<dl>`/`<dt>`/`<dd>` markup and CSS rules are fully removed - no dead code

## Blocked by

- [#2 Gruvbox dark theme + color system](02-gruvbox-dark-theme-color-system.md) - colors must be in place
- [#3 Card widening + mobile breakpoint](03-card-widening-mobile-breakpoint.md) - side-by-side answers need the wider card
