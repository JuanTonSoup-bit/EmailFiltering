/**
 * Popup logic.
 *
 * Paints immediately from the last cached poll, then refreshes in the
 * background. A popup that shows a spinner every time it opens feels broken
 * even when it is working.
 *
 * Everything rendered here originates in email - subjects, sender addresses.
 * It is inserted with textContent only. Building this DOM with innerHTML
 * would make a crafted subject line executable inside the extension, which
 * is a genuinely bad trade for an anti-phishing tool.
 */

const DEFAULTS = { port: 8000, days: 7 };

const $ = (id) => document.getElementById(id);

async function settings() {
  const stored = await chrome.storage.local.get(DEFAULTS);
  return { ...DEFAULTS, ...stored };
}

const api = (port, path) => `http://127.0.0.1:${port}/api${path}`;

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

function setPill(state, text) {
  const pill = $('pill');
  pill.className = `pill${state ? ` pill--${state}` : ''}`;
  $('pillText').textContent = text;
}

function showDown(port, detail) {
  $('live').hidden = true;
  $('down').hidden = false;
  $('downPort').textContent = String(port);
  setPill('down', 'Offline');
  if (detail) $('foot').textContent = detail;
}

function relative(iso) {
  if (!iso) return '';
  // The API sends UTC. A value with no offset would be read as local time,
  // which makes a message scanned a minute ago look hours old.
  const hasZone = /(?:Z|[+-]\d{2}:?\d{2})$/.test(iso);
  const then = new Date(hasZone ? iso : `${iso}Z`);
  if (Number.isNaN(then.getTime())) return '';
  const secs = Math.round((Date.now() - then.getTime()) / 1000);
  if (secs < 60) return 'just now';
  if (secs < 3600) return `${Math.round(secs / 60)}m ago`;
  if (secs < 86400) return `${Math.round(secs / 3600)}h ago`;
  return `${Math.round(secs / 86400)}d ago`;
}

function renderStats(stats) {
  $('flagged').textContent = stats.total_flagged ?? 0;
  $('suspicious').textContent = stats.suspicious ?? 0;
  $('junk').textContent = stats.junk ?? 0;
  $('scanned').textContent = stats.total_scanned ?? 0;
}

function renderRecent(emails) {
  const list = $('recent');
  list.textContent = '';

  const flagged = (emails || []).filter((e) => e.verdict !== 'clean').slice(0, 4);
  $('recentLabel').hidden = flagged.length === 0;

  for (const email of flagged) {
    const item = document.createElement('li');
    item.className = 'recent__item';

    const bar = document.createElement('span');
    bar.className = `recent__bar recent__bar--${email.verdict}`;

    const body = document.createElement('div');
    body.className = 'recent__body';

    const subject = document.createElement('div');
    subject.className = 'recent__subject';
    subject.textContent = email.subject || '(no subject)';
    subject.title = email.subject || '';

    const meta = document.createElement('div');
    meta.className = 'recent__meta';
    const verdict = email.verdict === 'suspicious' ? 'Suspicious' : 'Junk';
    meta.textContent =
      `${verdict} · ${email.score} · ${email.from_domain || 'unknown'} · ${relative(email.scanned_at)}`;

    body.append(subject, meta);
    item.append(bar, body);
    list.append(item);
  }
}

async function load({ quiet = false } = {}) {
  const { port, days } = await settings();
  if (!quiet) setPill('', 'Checking…');

  try {
    const [stats, emails] = await Promise.all([
      getJson(api(port, `/stats?days=${days}`)),
      getJson(api(port, `/emails?days=${days}&limit=25`)),
    ]);

    $('down').hidden = true;
    $('live').hidden = false;
    setPill('ok', 'Connected');
    renderStats(stats);
    renderRecent(emails);
    $('foot').textContent = `Last ${days} days · port ${port}`;
  } catch (error) {
    showDown(port, '');
    console.warn('PhishGuard popup:', error);
  }
}

/** Paint from cache first so the popup never opens empty. */
async function paintCached() {
  const { lastStatus, lastStats } = await chrome.storage.local.get([
    'lastStatus',
    'lastStats',
  ]);
  if (lastStatus === 'ok' && lastStats) {
    $('down').hidden = true;
    $('live').hidden = false;
    setPill('ok', 'Connected');
    renderStats(lastStats);
  }
}

// ---------------------------------------------------------------- actions

$('open').addEventListener('click', async () => {
  const { port } = await settings();
  chrome.tabs.create({ url: `http://localhost:${port}/` });
  window.close();
});

$('scan').addEventListener('click', async () => {
  const { port } = await settings();
  const button = $('scan');
  button.disabled = true;
  button.textContent = 'Scanning…';
  $('foot').textContent = 'Contacting Gmail…';

  try {
    const response = await fetch(api(port, '/scan'), { method: 'POST' });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const summary = await response.json();
    $('foot').textContent =
      summary.scanned === 0
        ? 'No new messages since the last scan.'
        : `${summary.scanned} new, ${summary.flagged} flagged.`;
    await load({ quiet: true });
    chrome.runtime.sendMessage({ type: 'refresh' });
  } catch (error) {
    // Almost always missing or expired OAuth credentials.
    $('foot').textContent = 'Scan failed — check credentials.json / token.json.';
    console.warn('PhishGuard scan:', error);
  } finally {
    button.disabled = false;
    button.textContent = 'Scan now';
  }
});

$('copy').addEventListener('click', async () => {
  await navigator.clipboard.writeText($('cmd').textContent.trim());
  $('copy').textContent = 'Copied';
  setTimeout(() => ($('copy').textContent = 'Copy command'), 1500);
});

$('retry').addEventListener('click', () => load());

$('save').addEventListener('click', async () => {
  const port = Math.min(65535, Math.max(1, Number($('port').value) || 8000));
  const days = Math.min(90, Math.max(1, Number($('days').value) || 7));
  await chrome.storage.local.set({ port, days });
  $('port').value = port;
  $('days').value = days;
  $('saved').hidden = false;
  setTimeout(() => ($('saved').hidden = true), 1500);
  chrome.runtime.sendMessage({ type: 'refresh' });
  load();
});

// ------------------------------------------------------------------- boot

(async () => {
  const { port, days } = await settings();
  $('port').value = port;
  $('days').value = days;
  await paintCached();
  await load({ quiet: true });
})();
