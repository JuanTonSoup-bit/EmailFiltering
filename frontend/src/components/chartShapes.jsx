/**
 * Custom Recharts bar shapes.
 *
 * Two mark rules are not expressible with Recharts' built-in props, so the
 * bars are drawn by hand:
 *
 * 1. THE SURFACE GAP. Touching fills are separated by 2px of the surface
 *    color - never by a stroke drawn around the mark. A border is ink that
 *    is not data; a gap is the surface showing through. Recharts has no
 *    notion of this, so each segment gives up 2px on the edge facing the
 *    segment before it. The bottom (or leftmost) segment keeps its full
 *    size because nothing sits between it and the baseline.
 *
 * 2. THE ROUNDED DATA-END. A bar is rounded 4px only at the end where the
 *    data stops, and stays square at the baseline. In a stack that end
 *    belongs to whichever segment happens to be last with a non-zero value
 *    on that row - which changes row to row. Recharts' `radius` prop is
 *    per-series, not per-row, so it cannot express this; the shape reads
 *    the row payload and decides for itself.
 *
 * Both factories close over the stack's key order so each segment can work
 * out whether it is currently the first or last non-zero one in its row.
 */

const GAP = 2
const RADIUS = 4

/** Which stack keys actually have a value on this row, in stack order. */
function activeKeys(payload, keys) {
  return keys.filter((key) => Number(payload?.[key]) > 0)
}

/** Rect with two rounded corners on one side, square on the other. */
function roundedPath({ x, y, width, height, radius, side }) {
  const r = Math.max(0, Math.min(radius, width / 2, height / 2))
  if (r === 0) return `M${x},${y}h${width}v${height}h${-width}Z`

  if (side === 'top') {
    return [
      `M${x},${y + height}`,
      `V${y + r}`,
      `Q${x},${y} ${x + r},${y}`,
      `H${x + width - r}`,
      `Q${x + width},${y} ${x + width},${y + r}`,
      `V${y + height}`,
      'Z',
    ].join(' ')
  }

  // side === 'right'
  return [
    `M${x},${y}`,
    `H${x + width - r}`,
    `Q${x + width},${y} ${x + width},${y + r}`,
    `V${y + height - r}`,
    `Q${x + width},${y + height} ${x + width - r},${y + height}`,
    `H${x}`,
    'Z',
  ].join(' ')
}

/**
 * Vertical stacked columns (the timeline).
 * @param {string} dataKey  the series this shape draws
 * @param {string[]} stackKeys  every series in the stack, bottom-first
 */
export function verticalSegment(dataKey, stackKeys) {
  return function Segment(props) {
    const { x, y, width, height, fill, payload } = props
    if (!height || height <= 0 || !width) return null

    const active = activeKeys(payload, stackKeys)
    const isBottom = active[0] === dataKey
    const isTop = active[active.length - 1] === dataKey

    // Give up 2px at the bottom edge unless this segment sits on the
    // baseline - that strip of surface is what separates it from the
    // segment below.
    const drawnHeight = isBottom ? height : Math.max(1, height - GAP)

    return (
      <path
        d={roundedPath({
          x,
          y,
          width,
          height: drawnHeight,
          radius: isTop ? RADIUS : 0,
          side: 'top',
        })}
        fill={fill}
      />
    )
  }
}

/**
 * Horizontal stacked bars (the authentication breakdown), growing right
 * from a left baseline.
 */
export function horizontalSegment(dataKey, stackKeys) {
  return function Segment(props) {
    const { x, y, width, height, fill, payload } = props
    if (!width || width <= 0 || !height) return null

    const active = activeKeys(payload, stackKeys)
    const isFirst = active[0] === dataKey
    const isLast = active[active.length - 1] === dataKey

    // The gap is taken off the left edge - the side facing the previous
    // segment - so the baseline stays flush.
    const offset = isFirst ? 0 : GAP
    const drawnWidth = Math.max(1, width - offset)

    return (
      <path
        d={roundedPath({
          x: x + offset,
          y,
          width: drawnWidth,
          height,
          radius: isLast ? RADIUS : 0,
          side: 'right',
        })}
        fill={fill}
      />
    )
  }
}

/** Single (unstacked) horizontal bar - top senders. Always rounded at the tip. */
export function singleHorizontalBar(props) {
  const { x, y, width, height, fill } = props
  if (!width || width <= 0 || !height) return null
  return (
    <path
      d={roundedPath({ x, y, width, height, radius: RADIUS, side: 'right' })}
      fill={fill}
    />
  )
}
