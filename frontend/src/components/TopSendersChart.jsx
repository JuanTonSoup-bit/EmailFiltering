import {
  Bar,
  BarChart,
  CartesianGrid,
  LabelList,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { ChartCard, EmptyState } from './ChartCard.jsx'
import { ChartTooltip } from './ChartTooltip.jsx'
import { singleHorizontalBar } from './chartShapes.jsx'
import { useThemeColors } from '../hooks/useThemeColors.js'
import { full, truncate } from '../lib/format.js'

/**
 * The sender domains that got flagged most often.
 *
 * FORM: horizontal bars. Domain names are long and unpredictable
 * ("secure-paypal-billing.example"), and rotating them 45 degrees under a
 * column chart is the classic unreadable-axis mistake. Horizontal gives
 * every label a full line to itself.
 *
 * COLOR: ONE hue for every bar - categorical slot 1 - not a light-to-dark
 * ramp. Domains have no natural order, so a ramp would be coloring each bar
 * darker simply because it is longer: double-encoding bar length as hue,
 * spending the only free channel on information the chart already shows.
 * A single series also means no legend box; the card title already names
 * what is plotted.
 *
 * Counts are direct-labelled at each tip, which is what makes this chart
 * readable without hovering - and the y-axis ticks carry identity, so the
 * tooltip is a convenience rather than the only way in.
 */
export function TopSendersChart({ topSenders, days, stale }) {
  const colors = useThemeColors()

  const data = (topSenders || []).map((sender) => ({
    ...sender,
    label: truncate(sender.from_domain, 30),
  }))

  // Height grows with the row count instead of squashing rows into a fixed
  // box - 10 domains in the space of 3 is a wall of hairlines.
  const height = Math.max(160, data.length * 30 + 36)

  return (
    <ChartCard
      title="Most-flagged sender domains"
      subtitle={`Domains behind junk or suspicious mail, last ${days} days.`}
      stale={stale}
      empty={
        data.length === 0 ? (
          <EmptyState title="No flagged senders yet">
            Nothing has scored above the junk threshold so far.
          </EmptyState>
        ) : null
      }
      table={<SendersTable data={data} />}
    >
      <ResponsiveContainer width="100%" height={height}>
        <BarChart
          data={data}
          layout="vertical"
          margin={{ top: 4, right: 40, left: 4, bottom: 0 }}
          barCategoryGap="26%"
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
            width={168}
            tickLine={false}
            axisLine={false}
            tick={{ fill: colors.textSecondary, fontSize: 12 }}
          />
          <Tooltip
            cursor={{ fill: colors.surface2 }}
            content={<ChartTooltip />}
          />
          <Bar
            dataKey="count"
            name="Times flagged"
            fill={colors.series1}
            maxBarSize={18}
            shape={singleHorizontalBar}
            isAnimationActive={false}
          >
            {/* Value at the tip, outside the bar, in a text token. Placing
                it inside would mean measuring text against a fill on every
                render and clipping the short bars. */}
            <LabelList
              dataKey="count"
              position="right"
              offset={8}
              fill={colors.textSecondary}
              fontSize={11}
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  )
}

function SendersTable({ data }) {
  return (
    <table className="tableview">
      <thead>
        <tr>
          <th scope="col">Domain</th>
          <th scope="col">Times flagged</th>
          <th scope="col">Highest score</th>
        </tr>
      </thead>
      <tbody>
        {data.map((sender) => (
          <tr key={sender.from_domain}>
            <th scope="row" className="mono" style={{ fontWeight: 400 }}>
              {sender.from_domain}
            </th>
            <td>{full(sender.count)}</td>
            <td>{full(sender.max_score)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
