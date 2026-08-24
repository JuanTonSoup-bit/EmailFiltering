import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { ChartCard, EmptyState } from './ChartCard.jsx'
import { ChartTooltip } from './ChartTooltip.jsx'
import { horizontalSegment } from './chartShapes.jsx'
import { useThemeColors } from '../hooks/useThemeColors.js'
import { full } from '../lib/format.js'
import { AUTH_META, MECHANISM_LABEL } from '../lib/verdicts.js'

/**
 * SPF / DKIM / DMARC outcomes across everything scanned in the window.
 *
 * WHY THIS CHART EXISTS: these three checks are the closest thing email has
 * to identity verification, and the single most useful thing they tell you
 * is not "how much mail is bad" but "how much of my mail is even
 * verifiable". A domain with no DMARC record is not failing - it simply
 * never made a claim - and treating that as a pass or a fail would be
 * wrong in both directions. So the chart has three states, not two.
 *
 * FORM: horizontal stacked bars. Part-to-whole, three rows, and the
 * category names sit comfortably at the left where they read as a list.
 * Horizontal also leaves room for a second line of tick text - the pass
 * rate - which is the number a reader actually came for.
 *
 * WHY THE PASS RATE IS AN AXIS LABEL AND NOT AN IN-BAR LABEL: white text
 * on the green fill lands around 3:1 contrast, under the 4.5:1 that small
 * text needs, and a label inside a short segment would have to be clipped
 * or dropped. Moving it into the tick keeps it in a text token on the card
 * surface, always legible, never measured against a fill.
 *
 * COLOR: status palette (good / critical / neutral). Every legend entry and
 * every tooltip row is paired with an icon and a word, so pass-vs-fail
 * never depends on telling green from red.
 */

const STACK_KEYS = ['passed', 'failed', 'other']

const KEY_META = {
  passed: AUTH_META.pass,
  failed: AUTH_META.fail,
  other: AUTH_META.other,
}

const KEY_LABEL = {
  passed: 'Pass',
  failed: 'Fail',
  other: 'None / neutral',
}

export function AuthChart({ authRates, days, stale }) {
  const colors = useThemeColors()

  const data = (authRates || []).map((rate) => {
    const total = rate.passed + rate.failed + rate.other
    return {
      mechanism: rate.mechanism,
      label: MECHANISM_LABEL[rate.mechanism] || rate.mechanism.toUpperCase(),
      passed: rate.passed,
      failed: rate.failed,
      other: rate.other,
      total,
      passRate: total > 0 ? rate.passed / total : null,
    }
  })

  const hasData = data.some((row) => row.total > 0)

  const legend = STACK_KEYS.map((key) => ({
    label: KEY_LABEL[key],
    color: colors[KEY_META[key].token],
    icon: KEY_META[key].icon,
    shape: 'rect',
  }))

  return (
    <ChartCard
      title="Authentication results"
      subtitle={`Every message scanned in the last ${days} days, by what its sending domain could prove.`}
      legend={legend}
      stale={stale}
      empty={
        hasData ? null : (
          <EmptyState title="No authentication data yet">
            These fill in once the first messages have been scanned.
          </EmptyState>
        )
      }
      table={<AuthTable data={data} />}
    >
      <ResponsiveContainer width="100%" height={232}>
        <BarChart
          data={data}
          layout="vertical"
          margin={{ top: 4, right: 12, left: 4, bottom: 0 }}
          barCategoryGap="30%"
        >
          <CartesianGrid
            horizontal={false}
            stroke={colors.grid}
            strokeWidth={1}
          />
          <XAxis
            type="number"
            allowDecimals={false}
            tick={{ fill: colors.textMuted, fontSize: 11 }}
            tickLine={false}
            axisLine={{ stroke: colors.grid }}
          />
          <YAxis
            type="category"
            dataKey="label"
            width={92}
            tickLine={false}
            axisLine={false}
            tick={<MechanismTick data={data} colors={colors} />}
          />
          <Tooltip
            cursor={{ fill: colors.surface2 }}
            content={<ChartTooltip showTotal />}
          />
          {STACK_KEYS.map((key) => (
            <Bar
              key={key}
              dataKey={key}
              name={KEY_LABEL[key]}
              stackId="auth"
              fill={colors[KEY_META[key].token]}
              // Slimmer than the 24px cap: these bars run the full width of
              // the card, and a saturated status color is meant for small
              // marks and accents rather than large blocks of ink.
              maxBarSize={16}
              shape={horizontalSegment(key, STACK_KEYS)}
              isAnimationActive={false}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  )
}

/**
 * Two-line y-axis tick: the mechanism, then its pass rate.
 *
 * Recharts hands a tick the category value and its pixel position; the row
 * it belongs to has to be looked back up from the data. Both lines use text
 * tokens - the tick is chrome, and chrome never wears a data color.
 */
function MechanismTick({ x, y, payload, data, colors }) {
  const row = data.find((item) => item.label === payload.value)
  const rate =
    row && row.passRate !== null ? `${Math.round(row.passRate * 100)}% pass` : '—'

  return (
    <g transform={`translate(${x},${y})`}>
      <text
        x={-10}
        y={-2}
        textAnchor="end"
        fill={colors.textPrimary}
        fontSize={12}
        fontWeight={600}
      >
        {payload.value}
      </text>
      <text
        x={-10}
        y={13}
        textAnchor="end"
        fill={colors.textMuted}
        fontSize={11}
      >
        {rate}
      </text>
    </g>
  )
}

function AuthTable({ data }) {
  return (
    <table className="tableview">
      <thead>
        <tr>
          <th scope="col">Mechanism</th>
          <th scope="col">Pass</th>
          <th scope="col">Fail</th>
          <th scope="col">None / neutral</th>
          <th scope="col">Pass rate</th>
        </tr>
      </thead>
      <tbody>
        {data.map((row) => (
          <tr key={row.mechanism}>
            <th scope="row" style={{ fontWeight: 400 }}>
              {row.label}
            </th>
            <td>{full(row.passed)}</td>
            <td>{full(row.failed)}</td>
            <td>{full(row.other)}</td>
            <td>
              {row.passRate === null
                ? '—'
                : `${Math.round(row.passRate * 100)}%`}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
