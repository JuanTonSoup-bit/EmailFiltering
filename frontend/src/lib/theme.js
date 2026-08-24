/**
 * Theme handling.
 *
 * Three states, deliberately - not two:
 *   'system' : no data-theme attribute, so the CSS @media
 *              (prefers-color-scheme) block decides. This is the default.
 *   'light'  : data-theme="light" pinned on <html>
 *   'dark'   : data-theme="dark"  pinned on <html>
 *
 * "System" is a real state rather than a startup guess, so a user who
 * changes their OS theme at 6pm sees the dashboard follow without ever
 * touching the toggle.
 *
 * The choice is persisted in localStorage. Every read and write is wrapped
 * in try/catch: in a private window, or with site data blocked, the
 * accessor itself can throw, and a dashboard that white-screens because it
 * could not remember a color preference would be a ridiculous failure mode.
 */

const STORAGE_KEY = 'phishguard.theme'

/** @returns {'system'|'light'|'dark'} */
export function getTheme() {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored === 'light' || stored === 'dark') return stored
  } catch {
    /* storage unavailable - fall through to 'system' */
  }
  return 'system'
}

/** @param {'system'|'light'|'dark'} theme */
export function setTheme(theme) {
  const root = document.documentElement
  if (theme === 'system') {
    root.removeAttribute('data-theme')
  } else {
    root.setAttribute('data-theme', theme)
  }
  try {
    if (theme === 'system') localStorage.removeItem(STORAGE_KEY)
    else localStorage.setItem(STORAGE_KEY, theme)
  } catch {
    /* preference simply will not survive a reload; the app still works */
  }
}

/** The theme actually being painted right now, after resolving 'system'. */
export function resolvedTheme() {
  const explicit = document.documentElement.getAttribute('data-theme')
  if (explicit === 'light' || explicit === 'dark') return explicit
  return window.matchMedia('(prefers-color-scheme: dark)').matches
    ? 'dark'
    : 'light'
}

/** Cycle order for the header button: system -> light -> dark -> system. */
export function nextTheme(current) {
  if (current === 'system') return 'light'
  if (current === 'light') return 'dark'
  return 'system'
}
