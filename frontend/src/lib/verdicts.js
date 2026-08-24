import {
  IconClean,
  IconFail,
  IconJunk,
  IconNeutral,
  IconPass,
  IconSuspicious,
} from '../components/Icon.jsx'

/**
 * Verdict and authentication metadata - the single place that decides how a
 * backend string is presented.
 *
 * The backend emits three verdicts ("clean" | "junk" | "suspicious") and
 * authentication results that are free-form strings from the message's
 * Authentication-Results header ("pass", "fail", "none", "neutral",
 * "softfail", "temperror", ... or "unknown" when the header was absent).
 *
 * Two decisions worth spelling out:
 *
 * 1. Verdicts use the STATUS palette, not the categorical one. Categorical
 *    color means "these are different things"; status color means "this is
 *    good / this is bad". A verdict is a judgement, so status is correct:
 *    clean = good, junk = warning, suspicious = critical.
 *
 * 2. Order is fixed and severity-ascending everywhere - stacks, legends,
 *    tables, tooltips. A reader who learns "amber is junk" on the timeline
 *    must find amber meaning junk in the table too. Color follows the
 *    entity, never its rank in the current data, so filtering never
 *    repaints the survivors.
 */

export const VERDICTS = ['clean', 'junk', 'suspicious']

export const VERDICT_META = {
  clean: {
    key: 'clean',
    label: 'Clean',
    icon: IconClean,
    token: 'statusGood',
    cssVar: 'var(--status-good)',
    description: 'No meaningful signals fired. Left alone in the inbox.',
  },
  junk: {
    key: 'junk',
    label: 'Junk',
    icon: IconJunk,
    token: 'statusWarning',
    cssVar: 'var(--status-warning)',
    description: 'Bulk or promotional mail. Labelled, never deleted.',
  },
  suspicious: {
    key: 'suspicious',
    label: 'Suspicious',
    icon: IconSuspicious,
    token: 'statusCritical',
    cssVar: 'var(--status-critical)',
    description: 'Likely phishing. Labelled for review - check before acting.',
  },
}

export function verdictMeta(verdict) {
  return (
    VERDICT_META[verdict] || {
      key: verdict || 'unknown',
      label: verdict || 'Unknown',
      icon: IconNeutral,
      token: 'statusNeutral',
      cssVar: 'var(--status-neutral)',
      description: 'Unrecognised verdict.',
    }
  )
}

/**
 * Bucket a raw authentication result into pass / fail / other.
 *
 * This mirrors backend/app/analysis/auth.py, which only ever penalises a
 * hard "fail". Everything that is neither pass nor fail - "none",
 * "neutral", a missing header - is genuinely a third state, not a quiet
 * failure, and the dashboard says so rather than rounding it toward either
 * pole. A lot of legitimate mail has no DMARC record at all.
 */
export function authBucket(result) {
  const value = (result || '').toLowerCase()
  if (value === 'pass') return 'pass'
  if (value === 'fail') return 'fail'
  return 'other'
}

export const AUTH_META = {
  pass: {
    label: 'Pass',
    icon: IconPass,
    token: 'statusGood',
    cssVar: 'var(--status-good)',
  },
  fail: {
    label: 'Fail',
    icon: IconFail,
    token: 'statusCritical',
    cssVar: 'var(--status-critical)',
  },
  other: {
    label: 'None / neutral',
    icon: IconNeutral,
    token: 'statusNeutral',
    cssVar: 'var(--status-neutral)',
  },
}

/** Human-readable names for the three authentication mechanisms. */
export const MECHANISM_LABEL = {
  spf: 'SPF',
  dkim: 'DKIM',
  dmarc: 'DMARC',
}

export const MECHANISM_HELP = {
  spf: 'Sender Policy Framework - did the sending server IP appear in the domain’s published list of allowed senders?',
  dkim: 'DomainKeys Identified Mail - was the message cryptographically signed by the domain, and does the signature still verify?',
  dmarc: 'Domain-based Message Authentication - does SPF or DKIM pass AND align with the visible From: domain? This is the one that actually stops spoofing.',
}

/**
 * Severity color for a 0-100 score, used by the meter fills.
 * The thresholds match the backend defaults (SUSPICIOUS_THRESHOLD=50,
 * JUNK_THRESHOLD=25). They are duplicated here rather than fetched because
 * the meter is a visual hint next to a verdict the backend already decided -
 * if the two ever disagree, the verdict badge is the authority.
 */
export function scoreColor(score) {
  if (score >= 50) return 'var(--status-critical)'
  if (score >= 25) return 'var(--status-warning)'
  return 'var(--status-good)'
}
