import {
  AUTH_META,
  MECHANISM_LABEL,
  authBucket,
  scoreColor,
  verdictMeta,
} from '../lib/verdicts.js'

/**
 * The three small status components. All of them follow the same rule:
 * icon + word first, color as reinforcement. Take the color away and every
 * one of them still says what it means.
 */

/** Verdict pill for table rows and the detail panel header. */
export function VerdictBadge({ verdict, size = 12 }) {
  const meta = verdictMeta(verdict)
  const Glyph = meta.icon
  return (
    <span className="badge" title={meta.description}>
      <span className="badge__icon" style={{ color: meta.cssVar }}>
        <Glyph size={size} />
      </span>
      {meta.label}
    </span>
  )
}

/**
 * One SPF / DKIM / DMARC chip.
 *
 * Two densities. The expanded form spells the outcome out in words and is
 * what the detail panel uses. The compact form - three chips per table row,
 * where a word each would triple the row height - drops the word and lets
 * the ICON carry the outcome.
 *
 * That is still not color-alone: a check, a cross, and a dash have
 * different silhouettes and are told apart in grayscale at 11px. The
 * mechanism name stays visible in both forms, the exact result is in the
 * title attribute, and the detail panel always shows the long version.
 *
 * The raw result string is surfaced whenever it is something other than a
 * plain pass or fail ("softfail", "temperror", "none"): those distinctions
 * are what you tune against, and flattening them to "other" would throw
 * away the only clue about why.
 */
export function AuthChip({ mechanism, result, compact = false }) {
  const bucket = authBucket(result)
  const meta = AUTH_META[bucket]
  const Glyph = meta.icon
  const raw = (result || 'unknown').toLowerCase()
  const name = MECHANISM_LABEL[mechanism] || mechanism

  return (
    <span className="chip" title={`${name}: ${raw}`}>
      <span className="chip__label">{name}</span>
      <span style={{ color: meta.cssVar, display: 'inline-flex' }}>
        <Glyph size={11} />
      </span>
      {compact ? (
        <span className="sr-only">{bucket === 'other' ? raw : meta.label}</span>
      ) : bucket === 'other' ? (
        raw
      ) : (
        meta.label
      )}
    </span>
  )
}

/**
 * The 0-100 score as a meter.
 *
 * A meter, not a bar chart: it is one ratio against a fixed limit, which is
 * exactly the case where a chart would be overkill. The fill carries
 * severity and the unfilled track is a muted surface step, so the state
 * reads across the whole width rather than only where the fill ends.
 *
 * The number is always printed beside it - the meter is the glance, the
 * number is the fact.
 */
export function ScoreMeter({ score, showValue = true }) {
  const clamped = Math.max(0, Math.min(100, Number(score) || 0))
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
      {showValue ? <span>{clamped}</span> : null}
      <span
        className="meter"
        role="meter"
        aria-valuenow={clamped}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label="Risk score"
      >
        <span
          className="meter__fill"
          style={{ width: `${clamped}%`, background: scoreColor(clamped) }}
        />
      </span>
    </span>
  )
}
