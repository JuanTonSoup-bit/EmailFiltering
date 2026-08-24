# Frontend

What React, Vite, and Recharts do, why they are here, and the design rules the
dashboard follows.

---

## Part 1 — The stack, explained

### React

**What it is.** A JavaScript library for building user interfaces out of
components. A component is a function that takes data (props) and returns a
description of what should be on screen. When the data changes, React works
out the minimum set of DOM changes needed and applies them.

The key idea is that you never write "find the score cell and set its text to
32". You write "the row for this email looks like *this*", and React handles
the difference between the old picture and the new one.

```jsx
export function VerdictBadge({ verdict }) {
  const meta = verdictMeta(verdict)
  const Glyph = meta.icon
  return (
    <span className="badge">
      <span style={{ color: meta.cssVar }}><Glyph /></span>
      {meta.label}
    </span>
  )
}
```

**Why React here.** This dashboard has a specific characteristic: **the same
data appears in several places at once, and it all has to stay in sync.** The
date range drives five cards. The verdict filter drives a table. A background
refetch updates everything without losing the reader's place. Selecting a row
opens a panel showing that row's data.

With direct DOM manipulation, every one of those relationships is a piece of
update code you write and maintain, and every one is a place where two parts
of the screen can disagree. With React, `days` is a state variable and
everything that depends on it re-renders. The bugs where the tiles say one
thing and the chart says another are structurally impossible.

The hooks used and what they are for:

| Hook | Job in this app |
|---|---|
| `useState` | The date range, the verdict filter, the selected message, the theme |
| `useEffect` | Timers (refresh, health probe), the Escape key listener, body scroll lock |
| `useCallback` | Keeping fetcher functions stable so `useFetch` re-runs only when filters actually change |
| `useRef` | Focus management in the drawer; holding the latest refresh function for the interval |
| `useId` | Unique DOM ids for `aria-controls` on the chart/table switch |

**Why not plain JavaScript, or Vue, or Svelte?** Plain JS was a real option
and would have shipped a smaller bundle, but see the sync argument above.
Vue and Svelte would both work fine — React was chosen because it is the most
widely known, which matters for a portfolio piece, and because Recharts is a
React library.

### StrictMode, and why the fetch hook is written the way it is

`main.jsx` wraps the app in `<StrictMode>`. In development React deliberately
double-invokes effects and renders to surface bugs that would otherwise appear
only intermittently — a fetch that does not guard against unmount, an effect
that is not idempotent.

`useFetch` is written to survive that. It tracks a `mounted` ref and a
monotonic `requestId`, and refuses to commit a result if the component has
unmounted or if a newer request has been issued. That second guard also fixes
a real user-facing race: click "7 days" then quickly "30 days", and without it
the slower 7-day response can land last and overwrite the 30-day data.

StrictMode is stripped from production builds, so it costs nothing at runtime.

### Vite

**What it is.** The build tool and development server. Two distinct jobs:

- **In development** it serves your source files directly over native ES
  modules. There is no bundling step, so the dev server starts in
  milliseconds, and editing a component hot-swaps it into the running page
  without a reload or a loss of state.
- **For production** it bundles with Rollup: JSX compiled to JavaScript,
  modules combined, code minified, filenames content-hashed
  (`index-BUZfaG5S.js`) so browsers cache aggressively and still pick up
  changes immediately.

**Why Vite.** It is the default for new React projects for good reason
(Create React App is deprecated), and its dev-server proxy solves a specific
problem here elegantly:

```js
server: { proxy: { '/api': { target: 'http://127.0.0.1:8000' } } }
```

Without this, the dev page at `:5173` calling the API at `:8000` is a
cross-origin request, and the code needs a different base URL in development
than in production. With it, both environments use the relative string
`/api` and the fetch code is identical. One less difference between "works on
my machine" and "works when deployed".

**The build output is shaped to match the backend.** FastAPI mounts
`frontend/dist/assets` at `/assets` and serves `dist/index.html` at `/`. Those
are Vite's defaults, kept explicit in the config so a future change is a
deliberate break rather than a mystery.

Recharts is split into its own chunk via `manualChunks`. It pulls in
`d3-scale`, `d3-shape`, and `d3-array` and is larger than the entire
application; splitting it means editing a component invalidates a ~215kB chunk
instead of a ~600kB one.

### Recharts

**What it is.** A charting library where charts are React components:

```jsx
<BarChart data={data}>
  <XAxis dataKey="date" />
  <YAxis />
  <Bar dataKey="junk" stackId="verdict" fill={colors.statusWarning} />
</BarChart>
```

It renders SVG, and it is built on d3's scale and shape maths — so the axis
ticks, stacking, and layout are d3's, wrapped in a React API.

**Why Recharts.** Three charts, all standard forms, all needing to react to
React state (the date range, the theme). Recharts renders declaratively from
props, which means a theme change is just new props.

**Why not d3 directly?** d3 wants to own the DOM, and React wants to own the
DOM. Making them cooperate means either driving d3 from inside `useEffect` and
manually reconciling, or using d3 only for maths and rendering the SVG
yourself. Both are more work than these three charts justify.

**Why not Chart.js?** It renders to `<canvas>`. Canvas charts cannot be
inspected, cannot be styled with CSS, do not scale crisply, and are invisible
to screen readers. Recharts' SVG output is real DOM.

**Where Recharts was not enough** — two mark rules it cannot express, both
implemented as custom shapes in `components/chartShapes.jsx`:

1. **The 2px surface gap between stacked segments.** Recharts has no concept
   of it, and drawing a border around each segment instead is worse (a border
   is ink that is not data). Each segment gives up 2px on the edge facing the
   segment before it; the bottom segment keeps its full size.
2. **Rounding only the true data-end of a stack.** Recharts' `radius` prop is
   per-series, but which segment is on top changes row to row — a day with no
   suspicious mail has junk on top instead. The custom shape reads the row
   payload and decides for itself.

---

## Part 2 — How the code is organised

```
frontend/src/
├── main.jsx                  entry point
├── App.jsx                   state, data fetching, layout
├── styles.css                all design tokens + layout
├── api/client.js             the five API calls
├── hooks/
│   ├── useFetch.js           fetch + refetch without losing data
│   └── useThemeColors.js     reads CSS tokens for the charts
├── lib/
│   ├── format.js             dates, counts, relative time
│   ├── theme.js              system/light/dark handling
│   └── verdicts.js           verdict + auth metadata, one source of truth
└── components/
    ├── Header.jsx            brand, connection pill, theme toggle
    ├── FilterBar.jsx         the one filter row
    ├── StatTiles.jsx         KPI row with the hero figure
    ├── ChartCard.jsx         card frame, legend, chart/table switch
    ├── ChartTooltip.jsx      shared tooltip body
    ├── chartShapes.jsx       custom bar shapes
    ├── TimelineChart.jsx     flagged mail per day
    ├── AuthChart.jsx         SPF/DKIM/DMARC breakdown
    ├── TopSendersChart.jsx   most-flagged domains
    ├── EmailTable.jsx        the message list
    ├── EmailDetail.jsx       the explainability panel
    ├── Badges.jsx            verdict badge, auth chip, score meter
    └── Icon.jsx              inline SVG icons
```

**All state lives in `App.jsx`.** There is no Redux, no Zustand, no context.
Five pieces of state, one place, passed down as props. A state library would
be more configuration than the state it manages.

**`lib/verdicts.js` is the single source of truth** for how a backend string
becomes something on screen — its label, icon, color token, and description.
Adding a fourth verdict means editing one object, not hunting through six
components.

---

## Part 3 — The design rules, and why

Charts get read by people and executed by machines. These rules are what keep
the reading part honest.

### Color follows meaning, not decoration

Verdicts use the **status palette** (good / warning / critical), not an
arbitrary categorical one. `clean`/`junk`/`suspicious` are *judgements* — good,
unwanted, dangerous — and status color is what that means. Using categorical
colors here would say "three different things" when the truth is "three
severities".

Top senders use **one hue for every bar**, not a light-to-dark ramp. Domains
have no natural order, so a ramp would color each bar darker merely because it
is longer: double-encoding bar length as hue, spending the only free channel
on information the chart already shows.

### Color is never the only channel

Green-vs-red is the single most common color-vision deficiency — roughly 1 in
12 men cannot reliably separate them. Since verdict colors *are* green, amber,
and red, every place a status color appears, it is paired with something else:

- **Icons with different silhouettes.** A shield-with-check, a mail tray, a
  warning triangle. A check, a cross, a dash. These are distinguishable at
  11px in grayscale.
- **Words.** Every badge, legend entry, and tooltip row spells the state out.
- **A table view on every chart.** One click, same numbers, no color involved.

The test applied throughout: *remove the color entirely — does it still read
correctly?* It does.

Text never wears the data color, either. A colored mark sits *beside* the
label; the label itself uses a text token. Light hues like amber are
illegible as small text, and coloring text is how color quietly becomes
load-bearing.

### Marks are thin, chrome is recessive

Bars are capped (24px in the timeline, 16px in the authentication chart where
they span the full card width). Gridlines are solid 1px hairlines one step off
the surface — never dashed, because dashing reads as "threshold" or
"projection" when it is just a grid. Data-ends are rounded 4px; baselines stay
square.

### The tooltip enhances, it never gates

Every number a tooltip shows is reachable without hovering — through direct
labels, axis ticks, or the table view. A value that only exists on hover does
not exist for keyboard users, screen readers, touch screens, or printouts.

### One filter row, scoping everything below it

The date range sits above the cards and every card re-renders against the same
slice. This is why the backend windows *all* its aggregates rather than just
the timeline: a filter that left some cards on all-time totals would put
numbers on screen that cannot be reconciled with each other.

The verdict switch is the exception, and it lives inside the message card
rather than the filter row — it chooses which rows of one list are shown, the
way a sort control would. Putting it in the global row would imply the charts
respond to it, which they do not and should not; the point of the charts is
the *mix* of verdicts.

### Destructive controls arm before they fire

**Stop** sits in the filter row beside Scan now, and takes two clicks: the
first arms it (turns critical, label changes to "Confirm stop"), the second
fires. It disarms itself after four seconds.

The friction is deliberate. A misclick would switch the mail filter off, and
**nothing in the browser can turn it back on** — extensions cannot spawn local
processes. The label changes along with the colour, so the warning does not
depend on seeing red.

Stopping is also the one place the app distinguishes two states that look
identical over HTTP: "you turned it off" gets a **PhishGuard stopped** banner
explaining how to restart, while "it went away unexpectedly" keeps the generic
unreachable error. Same symptom, different message, because the reader needs
different things from each.

### Writes carry a header, reads do not

`api/client.js` sends `X-PhishGuard-Client` on `triggerScan` and `stopServer`.
The value is irrelevant; its presence forces a CORS preflight, which the
backend's origin allowlist refuses for third-party pages. Without it, any
website you visited could POST to your local API. See
[BACKEND.md](BACKEND.md) for the full reasoning.

`request()` merges caller headers over its defaults rather than spreading them
— passing `headers` would otherwise silently replace the default `Accept`.

### Refetch keeps the frame

Background refreshes hold the previous render at reduced opacity. No skeleton
flash, no layout jump. This is the entire reason `useFetch` separates
`loading` (nothing to show yet) from `stale` (showing old data while fetching
new).

### The form is chosen before the color

- **Five headline numbers → stat tiles, not a bar chart.** When the data is a
  handful of current values, the number *is* the visualisation. "Flagged" is
  the hero figure at 52px — one per view, the number the tool exists to
  produce.
- **Flagged mail per day → stacked columns.** Discrete daily buckets, and the
  reader's question is part-to-whole. A smooth line would imply continuous
  measurement between days.
- **Clean mail is excluded from that chart** — and this is the most
  consequential chart decision here. Clean outnumbers flagged by one or two
  orders of magnitude; stacking it collapses every interesting segment into a
  sub-pixel sliver. The chart would technically contain the answer while
  making it unreadable, which is worse than not showing it. Clean lives in the
  KPI tiles and in that card's own table view.
- **Authentication → horizontal stacked bars** with three states, and the pass
  rate as a second line in the axis tick. It is an axis label rather than an
  in-bar label because white text on the green fill lands around 3:1 contrast,
  under the 4.5:1 small text needs, and a label in a short segment would have
  to be clipped.
- **Top senders → horizontal bars.** Domain names are long; rotating them 45°
  under a column chart is the classic unreadable axis.

---

## Part 4 — Theming

Three states, not two:

| State | Mechanism |
|---|---|
| `system` (default) | No attribute on `<html>`; the CSS `@media (prefers-color-scheme: dark)` block decides |
| `light` | `data-theme="light"` pinned on `<html>` |
| `dark` | `data-theme="dark"` pinned on `<html>` |

"System" is a real state rather than a startup guess, so changing your OS
theme at 6pm makes the dashboard follow without touching the toggle.

**Every color is a CSS custom property on `:root`.** Components reference roles
(`--text-secondary`, `--status-critical`), never hex values. That is what makes
light/dark a single swap in `styles.css` instead of a change in twelve
component files.

The charts need literal color strings, since Recharts takes colors as props.
Rather than duplicating hex values in JavaScript — which is exactly how a
dashboard ends up with a chart that did not get the dark-mode memo —
`useThemeColors` **reads the resolved token values off the document at
runtime** and re-reads when either the OS preference or the `data-theme`
attribute changes. `styles.css` stays the single source of truth for color.

A small inline script in `index.html` applies the stored theme **before first
paint**, so a dark-mode user never sees a white flash. It has to be inline; a
module script runs after the browser has already painted.

Every `localStorage` access is wrapped in `try/catch`. In a private window, or
with site data blocked, the accessor itself throws — and a dashboard that
white-screens because it could not remember a color preference would be a
ridiculous failure mode.

---

## Part 5 — Accessibility

- **Every chart has a table twin**, reachable from a switch in the card
  header.
- **Table rows are keyboard-operable.** They are `<tr>` elements with
  `tabIndex`, `role="button"`, and an Enter/Space handler — a real `<button>`
  cannot contain table cells, so the behaviour is supplied by hand rather than
  left mouse-only.
- **The detail panel is a real dialog.** It takes focus on open, returns focus
  to the element that opened it on close, closes on Escape, closes on a scrim
  click, and locks background scroll. Those four behaviours are what separate
  a dialog from a div that looks like one.
- **Icons are `aria-hidden`** because the adjacent text is the accessible
  name. Announcing "check-circle Clean" instead of "Clean" is noise.
- **Compact auth chips carry an `.sr-only` word**, so a screen reader hears
  "SPF Fail" where a sighted reader sees an icon.
- **`prefers-reduced-motion`** disables the drawer's slide-in.

---

## Building it

```bash
cd frontend
npm install
npm run dev      # dev server on :5173, proxying /api to :8000
npm run build    # production build into frontend/dist
```

After `npm run build`, FastAPI serves the dashboard itself at
`http://localhost:8000/` — no separate server needed.
