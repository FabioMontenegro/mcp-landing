# Abilities directory + categories grid fix

## Objective
Publish a browsable directory of every plugin ability (EN `/abilities/`, ES `/es/abilities/`) and fix the misaligned categories grid on the home page.

## Problem / why
- Home categories cards render shrunk and centered: the Ko-fi widget stylesheet (`floating-chat-wrapper.css`) ships a generic `.cat` rule that overrides our card width (verified: disabling the stylesheet restores 199px cards).
- The home category list is hand-written and out of sync with the plugin (e.g. sections that do not exist, wrong counts).
- Competitor sites expose a full tools directory; we have none.

## Scope
- `src/data/abilities.json` generated from the plugin registry (`ewpa_get_abilities_registry()`), 109 `ewpa/*` + 3 core = 112, 21 sections.
- Home categories grid driven by the JSON, namespaced classes, cards link to directory anchors.
- New directory pages (EN/ES) with section nav, search and type filter.
- Nav links work from any page.

## Constraints
- Static Astro, no new dependencies. Class names must not collide with third-party CSS (prefix `abl-`).
- Ability descriptions stay in English on the ES page (source of truth is the plugin).
- Headline stat "101+" is NOT changed without the user's decision.

## Tasks
- [x] T1 Reviews section (commit 01cbb07) — inline
- [x] T2 Categories grid data-driven + Ko-fi collision fix — delegated (writer trigger: 2+ non-trivial files)
- [x] T3 Directory pages EN/ES + nav — delegated (same writer)
- [x] T4 Browser verification (desktop + mobile, EN + ES, filters) — inline. Found and fixed: "1 abilities" plural, search now includes section/plugin names ("woo" 1 → 8 hits), mobile active chip off-by-one (IntersectionObserver replaced with scroll-position check), native scrollbar on chip row hidden. Verified: 21 cards equal width (253px @1440), 112 rows, filters 13 destructive, empty state, `/` shortcut, deep link #woocommerce, light + dark, no horizontal scroll at 375px.
- [x] T5 Deploy — count updated to 109 (24594db), live version 65d1ee44, verified 112 rows on /abilities/, /es/abilities/ 200, home shows 109+

## Checks
- `npm run build` passes; browser check of grid widths, anchors, search/filter, dark mode, 375px width.
- TDD: off (no test runner in project).

## Progress / next step
T2–T4 done and committed. Next: T5 deploy once the user decides whether the home "101+" stat becomes "109+". Earlier note — `npm run build` passes (4 pages + /en redirect), dist has 112 `abl-row` per directory page, 21 `abl-card` on each home, no `class="cat"`. Not yet browser-verified (T4): sticky offsets are computed in JS, mobile index chip row, dark mode pills. Next: T4, then commit.
