import { useEffect, useState } from 'react'
import { IconPower, IconRefresh } from './Icon.jsx'

/**
 * The one filter row.
 *
 * There is exactly one, it sits above everything it scopes, and every card
 * below re-renders against the same slice - so the tiles, the timeline, the
 * authentication breakdown, the sender list, and the message table can
 * always be reconciled with each other. Per-card date ranges are how a
 * dashboard ends up showing "3 flagged this week" next to a top-sender list
 * that adds up to 40.
 *
 * The date range comes first because it is the control every reader reaches
 * for, and it is offered as presets rather than a calendar: nobody wants to
 * fight a date grid to express "last 30 days".
 *
 * Both actions live at the right end. "Scan now" is the only write in the
 * app - it makes live Gmail API calls - so it is the primary button and it
 * reports what it did rather than silently succeeding.
 */

const RANGES = [
  { days: 7, label: '7 days' },
  { days: 14, label: '14 days' },
  { days: 30, label: '30 days' },
  { days: 90, label: '90 days' },
]

export function FilterBar({
  days,
  onDaysChange,
  onRefresh,
  onScan,
  onStop,
  scanning,
  stopping,
  busy,
}) {
  // Stop needs a confirmation, because it takes away the page you are looking
  // at and nothing in the browser can bring it back -- restarting means the
  // desktop shortcut or a terminal. An inline two-click confirm is enough
  // friction to prevent a misclick without the ceremony of a modal.
  const [confirmStop, setConfirmStop] = useState(false)

  useEffect(() => {
    if (!confirmStop) return
    // Don't leave the button armed indefinitely; a Stop that is one stray
    // click away five minutes later is a trap.
    const id = setTimeout(() => setConfirmStop(false), 4000)
    return () => clearTimeout(id)
  }, [confirmStop])

  return (
    <div className="filterbar">
      <span className="filterbar__label" id="range-label">
        Range
      </span>
      <div
        className="segmented"
        role="group"
        aria-labelledby="range-label"
      >
        {RANGES.map((range) => (
          <button
            key={range.days}
            type="button"
            className="segmented__btn"
            aria-pressed={days === range.days}
            onClick={() => onDaysChange(range.days)}
          >
            {range.label}
          </button>
        ))}
      </div>

      <div className="filterbar__spacer" />

      <button
        type="button"
        className="btn"
        onClick={onRefresh}
        disabled={busy}
      >
        <IconRefresh size={14} />
        Refresh
      </button>

      <button
        type="button"
        className="btn btn--primary"
        onClick={onScan}
        disabled={scanning || stopping}
      >
        {scanning ? 'Scanning…' : 'Scan now'}
      </button>

      <button
        type="button"
        className={`btn${confirmStop ? ' btn--danger' : ''}`}
        onClick={() => {
          if (confirmStop) {
            setConfirmStop(false)
            onStop()
          } else {
            setConfirmStop(true)
          }
        }}
        disabled={stopping || scanning}
        title={
          confirmStop
            ? 'Click again to stop the server'
            : 'Stop the PhishGuard server'
        }
      >
        <IconPower size={14} />
        {stopping ? 'Stopping…' : confirmStop ? 'Confirm stop' : 'Stop'}
      </button>
    </div>
  )
}
