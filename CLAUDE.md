# CLAUDE.md — mcp-landing

Landing page for the WordPress plugin **Enable Abilities for MCP** by Fabio Montenegro.

**Live URL:** https://mcp.fabiomontenegro.com  
**Workers.dev:** https://mcp-landing.stultitia1.workers.dev  
**GitHub:** https://github.com/FabioMontenegro/mcp-landing  
**Plugin page:** https://wordpress.org/plugins/enable-abilities-for-mcp/

---

## Stack

- **Astro 5** — static site generator (`output: 'static'`)
- **pnpm 11.5.1** — package manager (strict isolation, no shameful hoisting)
- **TypeScript** — i18n types
- **Cloudflare Workers + Assets** — hosting (not classic Pages)
- **Wrangler** — deploy via `npx wrangler deploy`, assets served from `./dist`

## Commands

```bash
pnpm install    # install deps (esbuild + sharp allowed via pnpm-workspace.yaml)
pnpm dev        # dev server
pnpm build      # build to dist/
pnpm preview    # preview built output
```

## Deploy

Auto-deploy on push to `main` via Cloudflare Workers + GitHub integration.  
Config: `wrangler.toml` — assets directory is `./dist`.

## Project Structure

```
src/
  i18n/
    es.ts          # Spanish content (neutral, NOT Rioplatense) — exports `es` and `LandingT` type
    en.ts          # English content — implements `LandingT` from es.ts
  layouts/
    Layout.astro   # HTML skeleton, all CSS tokens (dark/light theme), global styles
  components/
    Nav.astro
    Hero.astro         # terminal mockup + dot-grid background
    Stats.astro        # 15K+ downloads, 2K+ active sites, 5/5 stars
    Compare.astro      # sin/con plugin table
    Compat.astro       # compatibility chips (WooCommerce, ACF, etc.)
    Categories.astro   # 15 ability categories with icons and counts
    HowItWorks.astro   # 3 steps — uses set:html for inline <strong>/<code> in text
    Cases.astro        # 6 use cases
    CTA.astro
    Footer.astro
  pages/
    index.astro        # ES route (/)
    en/index.astro     # EN route (/en/)
```

## i18n Pattern

All components receive a `t: LandingT` prop — **no global state, no Astro i18n integration**.

```astro
---
import type { LandingT } from '../i18n/es';
interface Props { t: LandingT }
const { t } = Astro.props;
---
```

Pages pass the locale object down:
```astro
// src/pages/index.astro  → import { es } from '../i18n/es'; const t = es;
// src/pages/en/index.astro → import { en } from '../../i18n/en'; const t = en;
```

To add a new language: create `src/i18n/fr.ts` implementing `LandingT`, add `src/pages/fr/index.astro`.

## Plugin Facts (keep accurate)

- **Version:** 2.0.25
- **Downloads:** 15,000+ (15,081 verified on wp.org)
- **Active installs:** 2,000+
- **Rating:** 5/5 stars
- **Requires:** WordPress 6.9+, PHP 8.0+, MCP Adapter plugin
- **Auth methods:** Bearer Token (SHA-256 API Key) OR Application Password
- **Connection:** via `npx mcp-remote` bridge — NOT direct URL paste
- **License:** GPLv2 or later (free, open source)
- **Categories:** 15 ability categories — 68 abilities own to the plugin + 3 WordPress-native Core abilities (core/get-site-info, core/get-user-info, core/get-environment-info) toggleable from its admin = 71 total. Marketing copy uses 68 (the plugin's own); do not sum them as "71 plugin abilities".

## pnpm Configuration

`pnpm-workspace.yaml` uses `allowBuilds` (pnpm v10.26+ format — NOT `onlyBuiltDependencies` which was the old `package.json` field):

```yaml
allowBuilds:
  esbuild: true
  sharp: true
```

**Do NOT** use the `pnpm` field in `package.json` for build script config — it's ignored in pnpm v10+.

## CSS / Theme

CSS custom properties in `Layout.astro` `<style is:global>`. Supports dark/light via:
- `@media (prefers-color-scheme: dark)` — default OS preference
- `:root[data-theme="dark"]` / `:root[data-theme="light"]` — manual toggle override

## Content Guidelines

- **Spanish (ES):** neutral, professional — no voseo, no Rioplatense slang
- **English (EN):** default for code, comments, identifiers, UI strings
- Verify plugin facts before changing stats (downloads, installs, version)
