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
import { verticalSegment } from './chartShapes.jsx'
import { useThemeColors } from '../hooks/useThemeColors.js'
import { full, longDate, shortDate } from '../lib/format.js'
import { VERDICT_META } from '../lib/verdicts.js'

/**
 * Flagged mail per day.
 *
 * FORM: stacked columns, not a line or an area. The x-axis is a set of
 * discrete daily buckets rather than a continuous quantity, and the reader's
 * job is part-to-whole ("how much of yesterday's flagged mail was actual
 * phishing?"). Columns say "these are counted buckets"; a smooth line would
 * imply a continuous measurement between days that does not exist.
 *
 * WHY CLEAN IS NOT PLOTTED HERE: clean mail outnumbers flagged mail by one
 * or two orders of magnitude. Stack it and every interesting segment
 * collapses to a sub-pixel sliver at the bottom of the chart - the chart
 * would technically contain the answer while making it unreadable, which is
 * the worst outcome. Clean is carried by the KPI tiles and by this card's
 * own table view, so the number is never hidden, just moved somewhere it
 * can be read.
 *
 * COLOR: the status palette, because junk and suspicious are severities
 * rather than arbitrary categories. Severity stacks upward so the most
 * serious band sits on top, against the axis-free air where it reads best.
 * Green/amber/red is confusable for red-green colorblind readers, so the
 * legend carries a distinct icon per series and the table view carries the
 * numbers with no color at all.
 */

const STACK_KEYS = ['junk', 'suspicious']

/**
 * The API only returns days that actually have rows. Plotting that array
 * directly would silently compress a quiet week into one column and put
 * two dates that are five days apart side by side - a lie about the shape
 * of the data. This pads the range out to one entry per day.
 *
 * Days are built in UTC because the backend buckets on
 * strftime('%Y-%m-%d', scanned_at) over UTC timestamps; building them in
 * local time would shift every bucket by the viewer's offset and drop or
 * duplicate a day at the edges.
 */
export function fillDays(timeline, days) {
  const byDate = new Map((timeline || []).map((point) => [point.date, point]))
  const out = []
  const cursor = new Date()
  cursor.setUTCHours(0, 0, 0, 0)
  cursor.setUTCDate(cursor.getUTCDate() - (days - 1))

  for (let i = 0; i < days; i += 1) {
    const key = cursor.toISOString().slice(0, 10)
    const found = byDate.get(key)
    out.push({
      date: key,
      clean: found?.clean ?? 0,
      junk: found?.junk ?? 0,
      suspicious: found?.suspicious ?? 0,
    })
    cursor.setUTCDate(cursor.getUTCDate() + 1)
  }
  return out
}

export function TimelineChart({ timeline, days, stale }) {
  const colors = useThemeColors()
  const data = fillDays(timeline, days)
  const hasFlagged = data.some((day) => day.junk > 0 || day.suspicious > 0)

  const legend = STACK_KEYS.map((key) => ({
    label: VERDICT_META[key].label,
    color: colors[VERDICT_META[key].token],
    icon: VERDICT_META[key].icon,
    shape: 'rect',
  }))

  const axisTick = { fill: colors.textMuted, fontSize: 11 }

  return (
    <ChartCard
      title="Flagged mail per day"
      subtitle={`Last ${days} days. Clean mail is excluded here so the flagged bars stay readable - see the table view for all three.`}
      legend={legend}
      stale={stale}
      empty={
        hasFlagged ? null : (
          <EmptyState title="Nothing flagged in this window">
            Either the inbox has been quiet, or no mail has been scanned yet.
          </EmptyState>
        )
      }
      table={<TimelineTable data={data} />}
    >
      {/* The container is sized to include the x-axis band. Pinning a card
          to a height that only fits the plot is what produces a cropped
          axis and a tiny nested scrollbar. */}
      <ResponsiveContainer width="100%" height={248}>
        <BarChart
          data={data}
          margin={{ top: 8, right: 4, left: -12, bottom: 0 }}
          barCategoryGap="22%"
        >
          {/* Horizontal rules only, hairline, solid, one step off the
              surface. Vertical gridlines on a categorical axis are noise,
              and dashed rules read as "threshold" when they are just a
              grid. */}
          <CartesianGrid
            vertical={false}
            stroke={colors.grid}
            strokeWidth={1}
          />
          <XAxis
            dataKey="date"
            tickFormatter={shortDate}
            tick={axisTick}
            tickLine={false}
            axisLine={{ stroke: colors.grid }}
            interval="preserveStartEnd"
            minTickGap={18}
          />
          <YAxis
            allowDecimals={false}
            width={44}
            tick={axisTick}
            tickLine={false}
            axisLine={false}
          />
          <Tooltip
            // The hover band spans the whole day column, so the reader aims
            // at a date rather than at a 6px bar.
            cursor={{ fill: colors.surface2 }}
            content={
              <ChartTooltip labelFormatter={longDate} showTotal />
            }
          />
          {STACK_KEYS.map((key) => (
            <Bar
              key={key}
              dataKey={key}
              name={VERDICT_META[key].label}
              stackId="verdict"
              fill={colors[VERDICT_META[key].token]}
              maxBarSize={24}
              shape={verticalSegment(key, STACK_KEYS)}
              isAnimationActive={false}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  )
}

/** The WCAG-clean twin: every number, no color needed. */
function TimelineTable({ data }) {
  return (
    <table className="tableview">
      <thead>
        <tr>
          <th scope="col">Day</th>
          <th scope="col">Clean</th>
          <th scope="col">Junk</th>
          <th scope="col">Suspicious</th>
        </tr>
      </thead>
      <tbody>
        {data.map((day) => (
          <tr key={day.date}>
            <th scope="row" style={{ fontWeight: 400 }}>
              {shortDate(day.date)}
            </th>
            <td>{full(day.clean)}</td>
            <td>{full(day.junk)}</td>
            <td>{full(day.suspicious)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
