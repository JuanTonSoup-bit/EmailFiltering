import { compact, full } from '../lib/format.js'
import { VERDICT_META } from '../lib/verdicts.js'
import { IconClean, IconInfo } from './Icon.jsx'

/**
 * The KPI row.
 *
 * These are stat tiles, not charts, and that is a deliberate call. Five
 * headline numbers rendered as a grouped bar chart would be five bars with
 * a legend, an axis, and a tooltip standing between the reader and five
 * numbers they could simply have read. When the data is a handful of
 * current values, the number IS the visualisation.
 *
 * "Flagged" is the hero figure - one per view, 52px, in the same sans as
 * everything else. It is the number the whole tool exists to produce, so it
 * gets the size, and everything else on the row is context for it.
 *
 * Values are compacted (1.2K) with the exact figure in the title attribute
 * and in the aria-label, so nothing is lost to abbreviation.
 */
export function StatTiles({ stats }) {
  const flagged = stats?.total_flagged ?? 0
  const scanned = stats?.total_scanned ?? 0
  const flaggedShare =
    scanned > 0 ? `${Math.round((flagged / scanned) * 100)}% of all scanned` : '—'

  return (
    <div className="kpi">
      <Tile
        hero
        label="Flagged"
        icon={VERDICT_META.suspicious.icon}
        color="var(--status-critical)"
        value={flagged}
        hint={flaggedShare}
      />
      <Tile
        label="Suspicious"
        icon={VERDICT_META.suspicious.icon}
        color="var(--status-critical)"
        value={stats?.suspicious ?? 0}
        hint="Likely phishing - review these"
      />
      <Tile
        label="Junk"
        icon={VERDICT_META.junk.icon}
        color="var(--status-warning)"
        value={stats?.junk ?? 0}
        hint="Bulk mail, labelled not deleted"
      />
      <Tile
        label="Clean"
        icon={IconClean}
        color="var(--status-good)"
        value={stats?.clean ?? 0}
        hint="Passed every check"
      />
      <Tile
        label="Total scanned"
        icon={IconInfo}
        color="var(--text-muted)"
        value={scanned}
        hint="Messages analysed to date"
      />
    </div>
  )
}

function Tile({ hero = false, label, icon: Glyph, color, value, hint }) {
  const exact = full(value)
  return (
    <div className={`tile${hero ? ' tile--hero' : ''}`}>
      <div className="tile__label">
        {/* The icon carries the color; the label text stays in a text
            token. A colored word is both a contrast problem and a habit
            that quietly makes color load-bearing. */}
        <span style={{ color, display: 'inline-flex' }}>
          <Glyph size={13} />
        </span>
        {label}
      </div>
      <div
        className="tile__value"
        title={exact}
        aria-label={`${label}: ${exact}`}
      >
        {compact(value)}
      </div>
      {hint ? <div className="tile__hint">{hint}</div> : null}
    </div>
  )
}
