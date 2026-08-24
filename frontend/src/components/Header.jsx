import { IconMoon, IconSun, IconSystem } from './Icon.jsx'
import { nextTheme } from '../lib/theme.js'

/**
 * App header: identity, a live connection indicator, and the theme control.
 *
 * The connection pill is not decoration. This dashboard talks to a backend
 * the user runs themselves, and the single most likely failure - by a wide
 * margin - is that uvicorn is not running, or died. Without an indicator
 * that state looks identical to "no mail has been scanned yet", and the
 * user goes hunting for a bug in the scanner that does not exist.
 *
 * Like every other status in the app, the pill pairs its color with a word.
 */
export function Header({ health, theme, onThemeChange }) {
  const themeIcon = {
    system: IconSystem,
    light: IconSun,
    dark: IconMoon,
  }[theme]
  const ThemeGlyph = themeIcon || IconSystem

  const pillClass =
    health === 'ok' ? 'pill pill--ok' : health === 'down' ? 'pill pill--down' : 'pill'
  const pillText =
    health === 'ok'
      ? 'API connected'
      : health === 'down'
        ? 'API unreachable'
        : 'Connecting…'

  return (
    <header className="header">
      <div className="header__brand">
        <span className="header__mark" aria-hidden="true">
          🛡️
        </span>
        <div>
          <h1 className="header__title">PhishGuard</h1>
          <p className="header__sub">
            Label-only anti-phishing filter for Gmail
          </p>
        </div>
      </div>

      <span className={pillClass} role="status">
        <span className="pill__dot" aria-hidden="true" />
        {pillText}
      </span>

      <button
        type="button"
        className="btn btn--icon"
        onClick={() => onThemeChange(nextTheme(theme))}
        title={`Theme: ${theme}. Click to change.`}
      >
        <ThemeGlyph size={15} />
        <span className="sr-only">
          Theme: {theme}. Switch to {nextTheme(theme)}.
        </span>
      </button>
    </header>
  )
}
