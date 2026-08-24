import { full } from '../lib/format.js'

/**
 * Shared tooltip body for every chart on the dashboard.
 *
 * Three rules it exists to enforce:
 *
 * - ONE TOOLTIP, EVERY SERIES. The readout lists every series at that
 *   position, so the pointer never has to land on a specific segment to
 *   get its number.
 * - VALUES LEAD, LABELS FOLLOW. Inside a tooltip the reader already knows
 *   which series they are looking at and wants the number, so the value is
 *   the high-contrast element and the name is secondary. That is the
 *   legend's hierarchy inverted, on purpose.
 * - LINE KEYS, NOT BOXES. At tooltip density a filled swatch is
 *   data-weight ink doing a label's job, so each row is keyed with a short
 *   2px stroke instead.
 *
 * Series names are rendered as React children (i.e. as text nodes), never
 * assembled into HTML - they can originate in API data and are treated as
 * untrusted.
 *
 * @param {object} props Recharts injects `active` and `payload`.
 * @param {(label: any) => string} [props.labelFormatter]
 * @param {number} [props.total] when given, adds a total row
 */
export function ChartTooltip({
  active,
  payload,
  label,
  labelFormatter,
  showTotal = false,
}) {
  if (!active || !payload || payload.length === 0) return null

  const heading = labelFormatter ? labelFormatter(label) : label
  // Recharts hands stacked segments bottom-first; the tooltip reads
  // top-down to match what the eye sees on the stack.
  const rows = [...payload].reverse()
  const total = rows.reduce((sum, row) => sum + (Number(row.value) || 0), 0)

  return (
    <div className="tooltip" role="tooltip">
      {heading ? <div className="tooltip__head">{heading}</div> : null}
      {rows.map((row) => (
        <div className="tooltip__row" key={row.dataKey ?? row.name}>
          <span
            className="tooltip__key"
            style={{ background: row.color || row.fill }}
          />
          <span className="tooltip__name">{row.name}</span>
          <span className="tooltip__value">{full(row.value)}</span>
        </div>
      ))}
      {showTotal && rows.length > 1 ? (
        <div className="tooltip__row" style={{ paddingTop: 4 }}>
          <span className="tooltip__key" style={{ background: 'transparent' }} />
          <span className="tooltip__name">Total</span>
          <span className="tooltip__value">{full(total)}</span>
        </div>
      ) : null}
    </div>
  )
}
