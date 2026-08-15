# web

Next.js (App Router, TypeScript, Tailwind) site reading Supabase with the anon key.
Pages: Overview, Rates desk, Markets, Sources and health. Server components with 60s
revalidation; charts are small SVG components (`LineChart`, `BarChart`) with hover.

## Run locally

```
cd web
npm install
cp .env.example .env.local   # fill NEXT_PUBLIC_SUPABASE_URL / NEXT_PUBLIC_SUPABASE_ANON_KEY (public values)
npm run dev
```

## Deploy

Netlify, from `netlify.toml` at the repo root (base `web`). Env vars on the Netlify site:
`NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`. Linking the GitHub repo
in Netlify makes every merge to `main` deploy.

## Design notes

Light, quiet, precise: hairlines not cards, tabular figures, tier badge and as-at time on
every figure, no colour on text except up/down deltas. Charts follow the dataviz rules:
2px lines, ≤24px bars with rounded data-ends, hairline grid, legend when >1 series,
tooltip on hover, no dual axes.
