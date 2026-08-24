# PhishGuard dashboard

React + Vite front end for the PhishGuard API.

## Commands

```bash
npm install
npm run dev      # dev server on :5173, proxies /api to :8000
npm run build    # production build into dist/
npm run preview  # serve the production build locally
```

For development you need the backend running too:

```bash
cd ../backend && uvicorn app.main:app --reload --port 8000
```

Then use **http://localhost:5173/**. Vite proxies `/api` to the backend, so
the app uses the same relative base URL in development and production.

After `npm run build`, FastAPI serves the dashboard itself at
**http://localhost:8000/** — `dist/index.html` at `/` and `dist/assets` at
`/assets`.

## What it shows

- **KPI row** — flagged (the hero figure), suspicious, junk, clean, total
  scanned
- **Flagged mail per day** — stacked columns, junk and suspicious
- **Authentication results** — SPF/DKIM/DMARC pass / fail / no-claim, with
  pass rates
- **Most-flagged sender domains**
- **Recent messages** — filterable by verdict; selecting a row opens the
  explainability panel showing every signal that fired, its weight, and the
  evidence behind it

Every chart has a table view. Every status color is paired with an icon and a
word, so nothing depends on telling green from red.

## Structure

```
src/
├── App.jsx           state, data fetching, layout
├── styles.css        design tokens (the single source of truth for color)
├── api/client.js     the five API calls
├── hooks/            useFetch, useThemeColors
├── lib/              format, theme, verdict + auth metadata
└── components/       header, filter bar, tiles, charts, table, detail panel
```

**Full write-up — what React, Vite, and Recharts each do, why they were
chosen, and the design rules behind the charts — is in
[../docs/FRONTEND.md](../docs/FRONTEND.md).**
