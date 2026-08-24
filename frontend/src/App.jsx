import { useCallback, useEffect, useRef, useState } from 'react'
import { getEmails, getHealth, getStats, triggerScan } from './api/client.js'
import { useFetch } from './hooks/useFetch.js'
import { getTheme, setTheme as applyTheme } from './lib/theme.js'
import { full } from './lib/format.js'
import { AuthChart } from './components/AuthChart.jsx'
import { EmailDetail } from './components/EmailDetail.jsx'
import { EmailTable } from './components/EmailTable.jsx'
import { FilterBar } from './components/FilterBar.jsx'
import { Header } from './components/Header.jsx'
import { IconInfo } from './components/Icon.jsx'
import { StatTiles } from './components/StatTiles.jsx'
import { TimelineChart } from './components/TimelineChart.jsx'
import { TopSendersChart } from './components/TopSendersChart.jsx'
import { VERDICTS, verdictMeta } from './lib/verdicts.js'

/** Background refresh cadence. The backend polls Gmail every 120s by
 *  default, so refreshing here every 60s means the page is never more than
 *  about a minute behind the database without hammering it. */
const REFRESH_MS = 60_000
const HEALTH_MS = 30_000

export default function App() {
  const [days, setDays] = useState(14)
  const [verdict, setVerdict] = useState(null)
  const [selected, setSelected] = useState(null)
  const [theme, setThemeState] = useState(getTheme)
  const [health, setHealth] = useState('unknown')
  const [scanning, setScanning] = useState(false)
  const [toast, setToast] = useState(null)

  // Fetchers are wrapped in useCallback so useFetch re-runs exactly when the
  // filters change - and not on every render, which would be an infinite
  // request loop.
  const fetchStats = useCallback(() => getStats(days), [days])
  const fetchEmails = useCallback(
    () => getEmails({ verdict, days, limit: 100 }),
    [verdict, days],
  )

  const stats = useFetch(fetchStats)
  const emails = useFetch(fetchEmails)

  const refreshAll = useCallback(() => {
    stats.refetch()
    emails.refetch()
  }, [stats, emails])

  // Keep the latest refresh function in a ref so the interval below can be
  // set up once instead of being torn down and rebuilt on every render.
  const refreshRef = useRef(refreshAll)
  refreshRef.current = refreshAll

  useEffect(() => {
    const id = setInterval(() => refreshRef.current(), REFRESH_MS)
    return () => clearInterval(id)
  }, [])

  // Liveness probe, independent of the data fetches, so "the backend is
  // down" is distinguishable from "the backend is up and has no data".
  useEffect(() => {
    let cancelled = false
    async function probe() {
      try {
        await getHealth()
        if (!cancelled) setHealth('ok')
      } catch {
        if (!cancelled) setHealth('down')
      }
    }
    probe()
    const id = setInterval(probe, HEALTH_MS)
    return () => {
      cancelled = true
      clearInterval(id)
    }
  }, [])

  function changeTheme(next) {
    applyTheme(next)
    setThemeState(next)
  }

  async function handleScan() {
    setScanning(true)
    setToast(null)
    try {
      const summary = await triggerScan()
      const flagged = summary.flagged ?? 0
      setToast({
        kind: 'ok',
        text:
          summary.scanned === 0
            ? 'Scan complete — no new messages since the last one.'
            : `Scan complete — ${full(summary.scanned)} new message${
                summary.scanned === 1 ? '' : 's'
              }, ${full(flagged)} flagged.`,
      })
      refreshAll()
    } catch (error) {
      // The overwhelmingly common cause is missing OAuth credentials, so
      // the message says what to do rather than just what went wrong.
      setToast({
        kind: 'error',
        text: `Scan failed: ${error.message} Check that backend/credentials.json exists and that you have completed the Google sign-in once.`,
      })
    } finally {
      setScanning(false)
    }
  }

  useEffect(() => {
    if (!toast) return
    const id = setTimeout(() => setToast(null), 9000)
    return () => clearTimeout(id)
  }, [toast])

  const data = stats.data
  const busy = stats.loading || stats.stale || emails.loading || emails.stale
  const apiDown = health === 'down' || stats.error?.status === 0
  const noDataYet = !stats.error && data && data.total_scanned === 0

  return (
    <div className="app">
      <Header health={health} theme={theme} onThemeChange={changeTheme} />

      {apiDown ? (
        <div className="banner">
          <IconInfo size={16} />
          <div className="banner__body">
            <div className="banner__title">Can’t reach the PhishGuard API</div>
            <div className="banner__text">
              Start the backend with{' '}
              <code className="mono">uvicorn app.main:app --reload</code> from
              the <code className="mono">backend/</code> directory, then this
              page will reconnect on its own.
            </div>
          </div>
        </div>
      ) : null}

      {noDataYet ? (
        <div className="banner banner--info">
          <IconInfo size={16} />
          <div className="banner__body">
            <div className="banner__title">No mail scanned yet</div>
            <div className="banner__text">
              The backend is running but the database is empty. If you have
              finished the Google OAuth step, press <strong>Scan now</strong>{' '}
              to pull in recent mail — otherwise the poller will fill this in
              once <code className="mono">backend/credentials.json</code> is in
              place.
            </div>
          </div>
        </div>
      ) : null}

      <FilterBar
        days={days}
        onDaysChange={setDays}
        onRefresh={refreshAll}
        onScan={handleScan}
        scanning={scanning}
        busy={busy}
      />

      <div className={stats.stale ? 'is-stale' : undefined}>
        <StatTiles stats={data} />
      </div>

      {/* Layout order is reading order: the trend first and full width (at a
          90-day range it needs every pixel), then the two supporting
          breakdowns side by side, then the individual messages. The message
          table is full width because it carries five columns including a
          score meter - at half width its right-hand columns get pushed into
          a horizontal scroll, which is the one place a reader should never
          have to hunt. */}
      <div className="grid">
        <div className="span-12">
          <TimelineChart
            timeline={data?.timeline}
            days={days}
            stale={stats.stale}
          />
        </div>
        <div className="span-6">
          <AuthChart
            authRates={data?.auth_rates}
            days={days}
            stale={stats.stale}
          />
        </div>
        <div className="span-6">
          <TopSendersChart
            topSenders={data?.top_senders}
            days={days}
            stale={stats.stale}
          />
        </div>
        <div className="span-12">
          <MessagesCard
            emails={emails}
            verdict={verdict}
            onVerdictChange={setVerdict}
            onSelect={setSelected}
            selectedId={selected?.id}
            days={days}
          />
        </div>
      </div>

      <footer className="footer">
        PhishGuard labels mail. It never deletes, archives, or moves it.
      </footer>

      {selected ? (
        <EmailDetail email={selected} onClose={() => setSelected(null)} />
      ) : null}

      {toast ? (
        <div className="toast" role="status">
          {toast.text}
        </div>
      ) : null}
    </div>
  )
}

/**
 * The message list card.
 *
 * The verdict switch lives in this card's header rather than in the global
 * filter row on purpose. The filter row holds controls that re-slice the
 * whole dashboard; this one only chooses which rows of one list are shown,
 * the same way a sort control would. Putting it in the global row would
 * imply the charts respond to it too, which they do not and should not - the
 * point of the charts is the mix of verdicts.
 */
function MessagesCard({
  emails,
  verdict,
  onVerdictChange,
  onSelect,
  selectedId,
  days,
}) {
  const rows = emails.data || []

  return (
    <section className="card">
      <div className="card__head">
        <div className="card__titles">
          <h2 className="card__title">Recent messages</h2>
          <p className="card__sub">
            Newest first, last {days} days. Select a row to see exactly why it
            scored the way it did.
          </p>
        </div>

        <div className="segmented" role="group" aria-label="Filter by verdict">
          <button
            type="button"
            className="segmented__btn"
            aria-pressed={verdict === null}
            onClick={() => onVerdictChange(null)}
          >
            All
          </button>
          {VERDICTS.map((key) => (
            <button
              key={key}
              type="button"
              className="segmented__btn"
              aria-pressed={verdict === key}
              onClick={() => onVerdictChange(key)}
            >
              {verdictMeta(key).label}
            </button>
          ))}
        </div>
      </div>

      <div
        className={`card__body${emails.stale ? ' is-stale' : ''}`}
        style={{ padding: '0 0 8px' }}
      >
        {emails.error ? (
          <div className="empty">
            <div className="empty__title">Could not load messages</div>
            {emails.error.message}
          </div>
        ) : emails.loading ? (
          <div className="empty">Loading…</div>
        ) : (
          <EmailTable
            emails={rows}
            onSelect={onSelect}
            selectedId={selectedId}
          />
        )}
      </div>
    </section>
  )
}
