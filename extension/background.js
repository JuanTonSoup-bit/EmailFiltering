/**
 * PhishGuard service worker.
 *
 * Polls the local API and keeps the toolbar badge current, so you can see at
 * a glance whether anything was flagged without opening anything.
 *
 * Badge language, deliberately quiet:
 *   (empty)  server up, nothing flagged in the window - the normal state, and
 *            a badge that is always lit is a badge nobody reads
 *   N (red)  N flagged, at least one suspicious
 *   N (amber) N flagged, junk only
 *   ! (grey) server not reachable
 *
 * NOTE ON SCOPE: a Chrome extension cannot start a local process. Chrome's
 * sandbox has no API for it, and the only workaround - a registered native
 * messaging host - is a lot of moving parts. The project solves this instead
 * with a logon task (scripts/Install-Autostart.ps1) so the server is simply
 * always running. This extension is the window into it, not its launcher.
 */

const DEFAULTS = { port: 8000, days: 7 };
const ALARM = 'phishguard-poll';

const COLOR = {
  critical: '#d03b3b',
  warning: '#fab219',
  offline: '#6f6e66',
};

async function settings() {
  const stored = await chrome.storage.local.get(DEFAULTS);
  return { ...DEFAULTS, ...stored };
}

function apiBase(port) {
  return `http://127.0.0.1:${port}/api`;
}

/** Fetch with a hard timeout - a hung socket must not wedge the alarm. */
async function getJson(url, timeoutMs = 4000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(url, { signal: controller.signal });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return await response.json();
  } finally {
    clearTimeout(timer);
  }
}

async function setBadge(text, color) {
  await chrome.action.setBadgeText({ text });
  if (color) await chrome.action.setBadgeBackgroundColor({ color });
}

/**
 * Poll once and update the badge. The result is cached in storage so the
 * popup can paint instantly from the last known state instead of showing a
 * spinner while it repeats the same request.
 */
async function refresh() {
  const { port, days } = await settings();
  try {
    const stats = await getJson(`${apiBase(port)}/stats?days=${days}`);
    const flagged = stats.total_flagged ?? 0;

    if (flagged > 0) {
      await setBadge(
        flagged > 99 ? '99+' : String(flagged),
        stats.suspicious > 0 ? COLOR.critical : COLOR.warning,
      );
    } else {
      await setBadge('');
    }

    await chrome.action.setTitle({
      title:
        flagged > 0
          ? `PhishGuard - ${stats.suspicious} suspicious, ${stats.junk} junk in the last ${days} days`
          : `PhishGuard - nothing flagged in the last ${days} days`,
    });

    await chrome.storage.local.set({
      lastStatus: 'ok',
      lastStats: stats,
      lastChecked: Date.now(),
    });
    return { status: 'ok', stats };
  } catch (error) {
    await setBadge('!', COLOR.offline);
    await chrome.action.setTitle({
      title: `PhishGuard - server not reachable on port ${port}`,
    });
    await chrome.storage.local.set({
      lastStatus: 'down',
      lastError: String(error && error.message ? error.message : error),
      lastChecked: Date.now(),
    });
    return { status: 'down' };
  }
}

// One minute is the floor Chrome allows for alarms, and it is plenty: the
// backend only polls Gmail every two minutes anyway.
chrome.alarms.create(ALARM, { periodInMinutes: 1 });
chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === ALARM) refresh();
});

chrome.runtime.onStartup.addListener(refresh);
chrome.runtime.onInstalled.addListener(refresh);

// The popup asks for a refresh when it opens, and after a manual scan.
chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type === 'refresh') {
    refresh().then(sendResponse);
    return true; // keep the channel open for the async reply
  }
  return false;
});
