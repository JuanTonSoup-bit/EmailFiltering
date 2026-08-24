import { useId, useState } from 'react'
import { IconChart, IconTable } from './Icon.jsx'

/**
 * The frame every chart sits in: title, legend, a chart/table switch, and
 * the plot itself.
 *
 * Why every chart has a table twin
 * --------------------------------
 * A tooltip must enhance a chart, never gate it. If the only way to read a
 * number is to hover the right pixel, then that number does not exist for
 * anyone using a keyboard, a screen reader, a touch screen, or a printout.
 * The table view is the WCAG-clean equivalent of the same data - identical
 * numbers, no color required - and it is one click away on every card.
 *
 * The legend is always present when a chart has two or more series, because
 * color-matching alone is not a dependable identity channel. A one-series
 * chart gets no legend box: there is only one color, and the title already
 * says what is plotted, so a single-swatch legend would just restate it.
 */
export function ChartCard({
  title,
  subtitle,
  legend = [],
  table,
  children,
  stale = false,
  empty = null,
}) {
  const [view, setView] = useState('chart')
  const panelId = useId()
  const showEmpty = Boolean(empty)

  return (
    <section className="card">
      <div className="card__head">
        <div className="card__titles">
          <h2 className="card__title">{title}</h2>
          {subtitle ? <p className="card__sub">{subtitle}</p> : null}
        </div>

        {table && !showEmpty ? (
          <div className="segmented" role="group" aria-label={`${title} view`}>
            <button
              type="button"
              className="segmented__btn"
              aria-pressed={view === 'chart'}
              aria-controls={panelId}
              onClick={() => setView('chart')}
            >
              <IconChart size={13} />
              <span className="sr-only">Chart view</span>
            </button>
            <button
              type="button"
              className="segmented__btn"
              aria-pressed={view === 'table'}
              aria-controls={panelId}
              onClick={() => setView('table')}
            >
              <IconTable size={13} />
              <span className="sr-only">Table view</span>
            </button>
          </div>
        ) : null}
      </div>

      <div
        className={`card__body${stale ? ' is-stale' : ''}`}
        id={panelId}
      >
        {showEmpty ? (
          empty
        ) : view === 'chart' ? (
          <>
            {legend.length >= 2 ? <Legend items={legend} /> : null}
            {children}
          </>
        ) : (
          <div className="tableview__wrap">{table}</div>
        )}
      </div>
    </section>
  )
}

/**
 * Legend rows. The swatch mirrors the mark - a rect for bars and areas, a
 * short stroke for lines - and the text beside it always wears a text
 * token. Coloring the label itself would make identity depend on reading a
 * light hue as text, which fails contrast and looks amateurish besides.
 *
 * Each item may carry an icon, and for status colors it always does: that
 * is the secondary encoding that keeps green-vs-red meaningful for a
 * red-green colorblind reader.
 */
function Legend({ items }) {
  return (
    <div className="legend">
      {items.map((item) => {
        const Glyph = item.icon
        return (
          <span className="legend__item" key={item.label}>
            <span
              className={`legend__swatch${
                item.shape === 'line' ? ' legend__swatch--line' : ''
              }`}
              style={{ background: item.color }}
            />
            {Glyph ? <Glyph size={12} /> : null}
            {item.label}
          </span>
        )
      })}
    </div>
  )
}

/** Shown in place of a plot when there is genuinely nothing to draw yet. */
export function EmptyState({ title, children }) {
  return (
    <div className="empty">
      <div className="empty__title">{title}</div>
      {children}
    </div>
  )
}
