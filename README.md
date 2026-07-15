# PhishGuard

A self-hosted anti-phishing and junk-mail filter for your personal Gmail, with a
Pi-hole-style threat dashboard.

PhishGuard connects to your inbox over the Gmail API, scores each new message for
phishing and spam signals (email authentication, sender spoofing, malicious URLs,
social-engineering language), and applies a Gmail label so you can review what it
caught. Nothing is ever deleted.

## Version 1 scope

- **Gmail API integration** (OAuth, read-only inbox access + label management)
- **Detection engine**
  - SPF / DKIM / DMARC authentication results
  - Display-name and reply-to spoofing
  - Lookalike / typosquatted sender domains
  - URL analysis (anchor-vs-href mismatch, raw-IP links, shorteners)
  - Social-engineering language (urgency, credential requests)
- **Label-only action** — flagged mail is tagged `PhishGuard/Suspicious` or
  `PhishGuard/Junk` and left in the inbox
- **Threat dashboard** (React) — threats over time, auth pass rates, recent
  flagged mail, top spoofed senders, per-email explainability

## Architecture

```
Gmail API  ->  Poller  ->  Analysis engine  ->  SQLite  ->  FastAPI  ->  React dashboard
                              (explainable scoring)
```

- `backend/` — FastAPI service, Gmail client, analysis engine, background poller
- `frontend/` — Vite + React dashboard

## Getting started

See [`backend/README.md`](backend/README.md) for Gmail API setup and running the
service, and [`frontend/README.md`](frontend/README.md) for the dashboard.

## Design principles

1. **Never destroy mail.** Label only. Every decision is reversible.
2. **Explainable.** Every flag records *why* it was raised.
3. **Local first.** Your mail and its metadata stay on your machine (SQLite).
