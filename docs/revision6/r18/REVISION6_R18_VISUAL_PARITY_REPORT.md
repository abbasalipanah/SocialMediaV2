# Revision 6 / R18 — V1 visual theme parity

Date: `2026-08-10`

Status: `LOOPBACK_VISUAL_PARITY_VERIFIED / PUBLIC_CUTOVER_NOT_AUTHORIZED`

## Outcome

The V2 frontend now loads the same Inter `300/400/500/600/700` family used by the current
Accumulate/V1 shell. Previously, V2 declared `Inter` but did not load it, so browsers rendered a
system-font fallback. That caused the visible typography and spacing difference.

The canonical V1 Social Media theme is now explicit and test-locked:

| Token | Value |
|---|---|
| Background | `#f8fafc` |
| Card | `#ffffff` |
| Border | `rgba(226, 232, 240, .75)` |
| Primary copy | `#172033` |
| Muted copy | `#78849a` |
| Primary | `#5b4cf0` |
| Primary soft | `#f1efff` |

Pure `#000000`, `#000`, `rgb(0 0 0)`, and the CSS `black` keyword are rejected by the visual
contract test. Near-black copy remains on V1's softened navy-black `#172033`/`#0f172a` range;
TikTok brand surfaces retain `#111827`.

No sidebar, topbar, footer, dashboard, card, table, or responsive layout structure was changed.
Only font loading, shared theme tokens, default copy/background rendering, and visual regression
evidence changed.

## Verification

- frontend component/contract tests: `32 passed`;
- TypeScript: passed;
- production Vite build: passed (`2,535` modules, `24` output files);
- Playwright desktop/mobile suite: `17 passed`, `5` expected project-conditional skips;
- browser-computed body font: `Inter, ui-sans-serif, system-ui, -apple-system,
  BlinkMacSystemFont, "Segoe UI", sans-serif`;
- browser-computed body copy: `rgb(23, 32, 51)` (`#172033`), not pure black;
- browser-computed V1 token values: passed;
- Facebook, Instagram, Instagram Stories, and TikTok desktop/mobile snapshots were manually
  inspected before their stale baselines were refreshed;
- secret leak guard: passed;
- protected source write guard: passed;
- Git diff/whitespace check: passed.

## Isolated loopback release

Code commit `5066eb7` was pushed to `origin/main`. Only the V2 frontend was promoted:

- active frontend: `/opt/social-media-v2/releases/20260810T104500Z-5066eb7/frontend`;
- frontend rollback target: `/opt/social-media-v2/releases/20260810T090500Z-4fb9529/frontend`;
- unchanged backend: `/opt/social-media-v2/releases/20260810T090500Z-4fb9529/backend`;
- web: `127.0.0.1:3026`, healthy;
- API: `127.0.0.1:8026`, healthy;
- built/released SHA-256 artifact set: exact match across all `24` files;
- frontend-only rollback and forward recovery: passed;
- final API/web soak probes: `5/5` passed;
- web journal warning-or-higher entries in the release window: none;
- API/web services: active/enabled;
- collection service/timer: inactive/disabled.

The first incomplete build copy was never activated. It was removed from the active release tree
and retained recoverably at
`/var/lib/social-media-v2/release-quarantine/20260810T104300Z-5066eb7-incomplete`.

## Protected systems and public gate

SocialMedia V1, Accumulate, and performance_marketing were read only. Their source baseline guard
passed after the change. No V2 DB/media, credential, provider gate, collector, timer, backend,
public route, DNS, TLS, or shared Nginx change was made.

R18 does not authorize public cutover. DNS/TLS/shared Nginx remain pending until a separate future
user approval.
