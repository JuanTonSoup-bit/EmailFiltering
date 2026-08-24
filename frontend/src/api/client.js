/**
 * Thin wrapper around fetch for the PhishGuard API.
 *
 * Deliberately not a data-fetching library. The app has five endpoints, no
 * mutations beyond one POST, and no cache invalidation problem worth
 * solving; React Query or SWR here would be more configuration than code.
 *
 * The base URL is the relative string "/api" in both dev and production:
 *   - dev:  Vite proxies /api to 127.0.0.1:8000 (see vite.config.js)
 *   - prod: FastAPI serves the built page, so /api is the same origin
 * That means no build-time environment variable, and no "works on my
 * machine but not in the container" class of bug.
 */

const BASE = '/api'

/**
 * Sent on every state-changing request.
 *
 * The value is irrelevant; its presence is the point. A custom header forces
 * the browser to preflight a cross-origin request, and the backend's origin
 * allowlist refuses preflights from anywhere but this app -- so a random web
 * page cannot POST to your local API. See backend/app/api/guards.py.
 */
const CLIENT_HEADERS = { 'X-PhishGuard-Client': 'dashboard' }

/** Thrown for any non-2xx response, carrying the status for the UI. */
export class ApiError extends Error {
  /**
   * @param {string} message  shown to the user as-is
   * @param {number} status   HTTP status, or 0 when the request never landed
   * @param {ErrorOptions} [options]  carries `cause` for the console
   */
  constructor(message, status, options) {
    super(message, options)
    this.name = 'ApiError'
    this.status = status
  }
}

async function request(path, options = {}) {
  let response
  try {
    response = await fetch(`${BASE}${path}`, {
      ...options,
      // Merged rather than spread over: a caller passing `headers` would
      // otherwise replace the default Accept instead of adding to it.
      headers: { Accept: 'application/json', ...(options.headers || {}) },
    })
  } catch (cause) {
    // fetch only rejects on a network-level failure, which in practice
    // means the backend is not running. Say that, rather than surfacing
    // "Failed to fetch" to the user.
    throw new ApiError('Cannot reach the PhishGuard API.', 0, { cause })
  }

  if (!response.ok) {
    // FastAPI's error shape is {"detail": "..."}; fall back to the status
    // line if the body is not JSON (a proxy error page, say).
    let detail = `Request failed (${response.status})`
    try {
      const body = await response.json()
      if (body && typeof body.detail === 'string') detail = body.detail
    } catch {
      /* non-JSON error body - keep the generic message */
    }
    throw new ApiError(detail, response.status)
  }

  return response.json()
}

/** Liveness probe. Used by the header pill. */
export function getHealth() {
  return request('/health')
}

/**
 * Dashboard aggregates.
 * @param {number} days 1-90; the backend rejects anything outside that.
 */
export function getStats(days) {
  return request(`/stats?days=${encodeURIComponent(days)}`)
}

/**
 * Scanned messages, newest first.
 * @param {{verdict?: string, limit?: number, offset?: number}} params
 *   verdict must be clean | junk | suspicious - the backend enforces the
 *   pattern and 422s on anything else, so it is omitted rather than sent
 *   empty when the filter is "all".
 */
export function getEmails({ verdict, days, limit = 50, offset = 0 } = {}) {
  const query = new URLSearchParams()
  if (verdict) query.set('verdict', verdict)
  if (days) query.set('days', String(days))
  query.set('limit', String(limit))
  query.set('offset', String(offset))
  return request(`/emails?${query.toString()}`)
}

/** One message, including its full findings list. */
export function getEmail(id) {
  return request(`/emails/${encodeURIComponent(id)}`)
}

/**
 * Run a scan cycle immediately instead of waiting for the poller.
 *
 * This is slow by nature - it makes real Gmail API calls - and it is the
 * only write in the app. It returns {scanned, flagged, verdicts}.
 */
export function triggerScan() {
  return request('/scan', { method: 'POST', headers: CLIENT_HEADERS })
}

/**
 * Stop the server.
 *
 * The reply arrives before the process exits (the backend delays its own
 * shutdown so the response can flush), so a resolved promise means "it
 * accepted and is going down", not "it is already down".
 *
 * Nothing in a browser can start it again -- extensions cannot spawn local
 * processes. Restarting means the desktop shortcut, the logon task, or
 * scripts/Start-PhishGuard.ps1.
 */
export function stopServer() {
  return request('/shutdown', { method: 'POST', headers: CLIENT_HEADERS })
}
