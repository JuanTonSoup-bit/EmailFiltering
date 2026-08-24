/**
 * Inline SVG icons.
 *
 * These are not decoration. The status palette (green / amber / red) is
 * deutan-confusable by construction - roughly 1 in 12 men cannot reliably
 * separate the green from the red - so every status color in this app ships
 * with an icon AND a word. Strip the color out entirely and the interface
 * still reads correctly. That is the test.
 *
 * Shapes are chosen to differ in silhouette, not just in fill: a check, a
 * triangle, a slashed circle, and a dash are distinguishable at 12px in
 * grayscale.
 *
 * Icons are aria-hidden because the adjacent text is the accessible name -
 * announcing "check-circle Clean" instead of "Clean" is noise for a screen
 * reader.
 */

const base = {
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 2,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
  'aria-hidden': true,
  focusable: false,
}

function Svg({ size = 14, children, ...rest }) {
  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      {...base}
      {...rest}
    >
      {children}
    </svg>
  )
}

/** Clean - a shield with a check. Nothing to do. */
export function IconClean(props) {
  return (
    <Svg {...props}>
      <path d="M12 3l7 3v5c0 4.4-2.9 8.4-7 10-4.1-1.6-7-5.6-7-10V6z" />
      <path d="M9 12l2 2 4-4" />
    </Svg>
  )
}

/** Junk - a mail tray. Bulk, unwanted, but not an attack. */
export function IconJunk(props) {
  return (
    <Svg {...props}>
      <path d="M3 13h5l1 3h6l1-3h5" />
      <path d="M5 5h14l2 8v5a1 1 0 01-1 1H4a1 1 0 01-1-1v-5z" />
    </Svg>
  )
}

/** Suspicious - a warning triangle. The one that needs a human. */
export function IconSuspicious(props) {
  return (
    <Svg {...props}>
      <path d="M12 3.5l9.2 16a1 1 0 01-.9 1.5H3.7a1 1 0 01-.9-1.5z" />
      <path d="M12 9.5v4.2" />
      <path d="M12 17.2h.01" />
    </Svg>
  )
}

/** Auth pass. */
export function IconPass(props) {
  return (
    <Svg {...props}>
      <circle cx="12" cy="12" r="9" />
      <path d="M8.5 12.2l2.4 2.4 4.6-4.8" />
    </Svg>
  )
}

/** Auth fail - a slashed circle, clearly different in outline from a check. */
export function IconFail(props) {
  return (
    <Svg {...props}>
      <circle cx="12" cy="12" r="9" />
      <path d="M8.6 8.6l6.8 6.8M15.4 8.6l-6.8 6.8" />
    </Svg>
  )
}

/** No result / neutral / not published - a dash. */
export function IconNeutral(props) {
  return (
    <Svg {...props}>
      <circle cx="12" cy="12" r="9" />
      <path d="M8.5 12h7" />
    </Svg>
  )
}

export function IconRefresh(props) {
  return (
    <Svg {...props}>
      <path d="M20 11a8 8 0 10-2.3 6.3" />
      <path d="M20 5v6h-6" />
    </Svg>
  )
}

export function IconSun(props) {
  return (
    <Svg {...props}>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
    </Svg>
  )
}

export function IconMoon(props) {
  return (
    <Svg {...props}>
      <path d="M20 14.5A8.5 8.5 0 019.5 4a8.5 8.5 0 1010.5 10.5z" />
    </Svg>
  )
}

/** "Follow the OS" - a monitor. */
export function IconSystem(props) {
  return (
    <Svg {...props}>
      <rect x="3" y="4" width="18" height="12" rx="1.5" />
      <path d="M8 20h8M12 16v4" />
    </Svg>
  )
}

export function IconClose(props) {
  return (
    <Svg {...props}>
      <path d="M6 6l12 12M18 6L6 18" />
    </Svg>
  )
}

export function IconTable(props) {
  return (
    <Svg {...props}>
      <rect x="3" y="4" width="18" height="16" rx="1.5" />
      <path d="M3 9.5h18M9.5 9.5V20" />
    </Svg>
  )
}

export function IconChart(props) {
  return (
    <Svg {...props}>
      <path d="M4 20V10M10 20V5M16 20v-7M22 20H2" />
    </Svg>
  )
}

export function IconInfo(props) {
  return (
    <Svg {...props}>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 11v5M12 8h.01" />
    </Svg>
  )
}

/** Power — the stop control. A distinct silhouette from refresh at 14px. */
export function IconPower(props) {
  return (
    <Svg {...props}>
      <path d="M12 4v8" />
      <path d="M7.1 7.1a7 7 0 1 0 9.8 0" />
    </Svg>
  )
}
