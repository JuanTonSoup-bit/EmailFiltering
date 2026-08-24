/**
 * Small formatting helpers. Kept in one file so the dashboard is
 * consistent about how it renders a date, a count, or a domain.
 */

/**
 * Compact counts for stat tiles: 940 / 1.2K / 3.4M.
 * Big numbers should never wrap or blow out a tile's width.
 */
export function compact(n) {
  if (n === null || n === undefined || Number.isNaN(n)) return '-'
  if (Math.abs(n) < 1000) return String(n)
  return new Intl.NumberFormat(undefined, {
    notation: 'compact',
    maximumFractionDigits: 1,
  }).format(n)
}

/** Full, thousands-separated. For tables and tooltips, where exact wins. */
export function full(n) {
  if (n === null || n === undefined || Number.isNaN(n)) return '-'
  return new Intl.NumberFormat().format(n)
}

/** "Aug 23" - short axis tick from the API's YYYY-MM-DD timeline dates. */
export function shortDate(isoDate) {
  const parsed = new Date(`${isoDate}T00:00:00`)
  if (Number.isNaN(parsed.getTime())) return isoDate
  return parsed.toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
  })
}

/** "Mon, Aug 23" - the tooltip heading, where there is room for the weekday. */
export function longDate(isoDate) {
  const parsed = new Date(`${isoDate}T00:00:00`)
  if (Number.isNaN(parsed.getTime())) return isoDate
  return parsed.toLocaleDateString(undefined, {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
  })
}

/**
 * Relative age for the "scanned" column ("4m ago", "2d ago").
 *
 * The API sends UTC timestamps. Python's isoformat produces
 * "2026-08-23T14:03:11+00:00" when the column is timezone-aware, but a naive
 * value ("...T14:03:11") is parsed by JS as LOCAL time, which would show a
 * message scanned seconds ago as hours old. Appending "Z" when there is no
 * offset makes the interpretation explicit and correct either way.
 */
export function relativeTime(iso) {
  if (!iso) return '-'
  const hasZone = /(?:Z|[+-]\d{2}:?\d{2})$/.test(iso)
  const parsed = new Date(hasZone ? iso : `${iso}Z`)
  if (Number.isNaN(parsed.getTime())) return '-'

  const seconds = Math.round((Date.now() - parsed.getTime()) / 1000)
  if (seconds < 45) return 'just now'

  const units = [
    ['minute', 60],
    ['hour', 3600],
    ['day', 86400],
    ['week', 604800],
    ['month', 2629800],
    ['year', 31557600],
  ]
  let chosen = units[0]
  for (const unit of units) {
    if (seconds >= unit[1]) chosen = unit
  }
  const value = Math.round(seconds / chosen[1])
  const rtf = new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' })
  return rtf.format(-value, chosen[0])
}

/** Absolute timestamp for the detail panel, where precision matters. */
export function absoluteTime(iso) {
  if (!iso) return '-'
  const hasZone = /(?:Z|[+-]\d{2}:?\d{2})$/.test(iso)
  const parsed = new Date(hasZone ? iso : `${iso}Z`)
  if (Number.isNaN(parsed.getTime())) return iso
  return parsed.toLocaleString()
}

/** Truncate for table cells where CSS ellipsis is not available. */
export function truncate(text, max = 80) {
  if (!text) return ''
  return text.length > max ? `${text.slice(0, max - 1)}…` : text
}
