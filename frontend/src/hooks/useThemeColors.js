import { useCallback, useEffect, useState } from 'react'
import { resolvedTheme } from '../lib/theme.js'

/**
 * Charts need literal color strings; CSS needs tokens. This bridges them.
 *
 * Recharts renders SVG and takes colors as props (fill="#0ca30c"). The rest
 * of the app styles itself from CSS custom properties. Rather than
 * duplicating hex values in JS - which is exactly how a dashboard ends up
 * with a chart that did not get the dark-mode memo - this hook READS the
 * resolved value of each token off the document at runtime.
 *
 * styles.css stays the single source of truth for color. Change a token
 * there and the charts follow on the next paint.
 *
 * It re-reads on two triggers:
 *   1. the OS flipping prefers-color-scheme (matchMedia listener)
 *   2. data-theme changing on <html> (MutationObserver), i.e. the toggle
 */

const TOKENS = [
  'surface-1',
  'surface-2',
  'border',
  'grid',
  'text-primary',
  'text-secondary',
  'text-muted',
  'series-1',
  'status-good',
  'status-warning',
  'status-serious',
  'status-critical',
  'status-neutral',
]

function readTokens() {
  const styles = getComputedStyle(document.documentElement)
  const out = { mode: resolvedTheme() }
  for (const token of TOKENS) {
    // camelCase the key so call sites read colors.statusGood, not
    // colors['status-good'].
    const key = token.replace(/-([a-z0-9])/g, (_, c) => c.toUpperCase())
    out[key] = styles.getPropertyValue(`--${token}`).trim()
  }
  return out
}

export function useThemeColors() {
  const [colors, setColors] = useState(readTokens)
  const refresh = useCallback(() => setColors(readTokens()), [])

  useEffect(() => {
    const mq = window.matchMedia('(prefers-color-scheme: dark)')
    mq.addEventListener('change', refresh)

    const observer = new MutationObserver(refresh)
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['data-theme'],
    })

    return () => {
      mq.removeEventListener('change', refresh)
      observer.disconnect()
    }
  }, [refresh])

  return colors
}
