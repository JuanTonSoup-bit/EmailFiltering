import { useEffect, useRef } from 'react'
import { AuthChip, VerdictBadge } from './Badges.jsx'
import { IconClose } from './Icon.jsx'
import { absoluteTime } from '../lib/format.js'
import {
  MECHANISM_HELP,
  scoreColor,
  verdictMeta,
} from '../lib/verdicts.js'

/**
 * The explainability panel - arguably the most important screen in the app.
 *
 * A filter that says "this is phishing" and nothing else is a filter you
 * cannot trust and cannot tune. Every message here shows the complete
 * arithmetic: which signals fired, what each one was worth, what evidence
 * triggered it, and how the total landed on a verdict. If PhishGuard is
 * wrong about a message, this panel is where you find out why in about ten
 * seconds - and which weight or threshold in .env to change.
 *
 * Findings are sorted by weight so the reason that actually drove the
 * verdict is at the top, rather than whatever order the engine happened to
 * evaluate its analysers in.
 *
 * Accessibility: it is a modal dialog, so it takes focus on open, sends
 * focus back where it came from on close, closes on Escape, and closes on a
 * scrim click. Those four behaviours are what separate a dialog from a div
 * that merely looks like one.
 */
export function EmailDetail({ email, onClose }) {
  const closeRef = useRef(null)
  const returnFocusRef = useRef(null)

  useEffect(() => {
    // Remember what had focus so it can be handed back on close - otherwise
    // a keyboard user lands back at the top of the document.
    returnFocusRef.current = document.activeElement
    closeRef.current?.focus()

    function onKeyDown(event) {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKeyDown)

    // Stop the page behind the drawer from scrolling under it.
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'

    return () => {
      document.removeEventListener('keydown', onKeyDown)
      document.body.style.overflow = previousOverflow
      if (returnFocusRef.current instanceof HTMLElement) {
        returnFocusRef.current.focus()
      }
    }
  }, [onClose])

  if (!email) return null

  const meta = verdictMeta(email.verdict)
  const findings = [...(email.findings || [])].sort(
    (a, b) => b.weight - a.weight,
  )

  return (
    <>
      <div className="drawer__scrim" onClick={onClose} aria-hidden="true" />
      <aside
        className="drawer"
        role="dialog"
        aria-modal="true"
        aria-label="Message details"
      >
        <header className="drawer__head">
          <div style={{ marginRight: 'auto', minWidth: 0 }}>
            <div style={{ marginBottom: 8 }}>
              <VerdictBadge verdict={email.verdict} size={13} />
            </div>
            <h2 className="drawer__title">
              {email.subject || <em>(no subject)</em>}
            </h2>
          </div>
          <button
            type="button"
            className="btn btn--icon"
            onClick={onClose}
            ref={closeRef}
          >
            <IconClose size={15} />
            <span className="sr-only">Close details</span>
          </button>
        </header>

        <div className="drawer__body">
          {/* --- Score ------------------------------------------------- */}
          <section className="section">
            <h3 className="section__title">Risk score</h3>
            <div
              style={{
                display: 'flex',
                alignItems: 'baseline',
                gap: 10,
                marginBottom: 2,
              }}
            >
              <span style={{ fontSize: 30, fontWeight: 650, lineHeight: 1 }}>
                {email.score}
              </span>
              <span style={{ color: 'var(--text-muted)', fontSize: 13 }}>
                out of 100
              </span>
            </div>
            <div className="scorebar">
              <div
                className="scorebar__fill"
                style={{
                  width: `${Math.min(100, email.score)}%`,
                  background: scoreColor(email.score),
                }}
              />
            </div>
            <p
              style={{
                margin: 0,
                fontSize: 12,
                color: 'var(--text-secondary)',
              }}
            >
              {meta.description}
            </p>
          </section>

          {/* --- Findings ---------------------------------------------- */}
          <section className="section">
            <h3 className="section__title">
              Why it scored this way ({findings.length}{' '}
              {findings.length === 1 ? 'signal' : 'signals'})
            </h3>
            {findings.length === 0 ? (
              <p
                style={{
                  margin: 0,
                  fontSize: 13,
                  color: 'var(--text-secondary)',
                }}
              >
                No signals fired. Authentication passed, the sender looked
                consistent, and nothing in the body or links matched a
                detection rule.
              </p>
            ) : (
              <div>
                {findings.map((finding, index) => (
                  <div className="finding" key={`${finding.code}-${index}`}>
                    <span
                      className="finding__weight"
                      title={`Added ${finding.weight} points`}
                    >
                      +{finding.weight}
                    </span>
                    <div style={{ minWidth: 0 }}>
                      <div className="finding__label">{finding.label}</div>
                      <div className="finding__detail">{finding.detail}</div>
                      <div className="finding__code">{finding.code}</div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* --- Authentication ---------------------------------------- */}
          <section className="section">
            <h3 className="section__title">Authentication</h3>
            <div className="chips" style={{ marginBottom: 10 }}>
              <AuthChip mechanism="spf" result={email.spf} />
              <AuthChip mechanism="dkim" result={email.dkim} />
              <AuthChip mechanism="dmarc" result={email.dmarc} />
            </div>
            <dl className="kv">
              {['spf', 'dkim', 'dmarc'].map((mechanism) => (
                <div key={mechanism} style={{ display: 'contents' }}>
                  <dt className="kv__k">{mechanism.toUpperCase()}</dt>
                  <dd
                    className="kv__v"
                    style={{
                      margin: 0,
                      fontSize: 12,
                      color: 'var(--text-secondary)',
                    }}
                  >
                    {MECHANISM_HELP[mechanism]}
                  </dd>
                </div>
              ))}
            </dl>
          </section>

          {/* --- Sender ------------------------------------------------- */}
          <section className="section">
            <h3 className="section__title">Sender</h3>
            <dl className="kv">
              <Row k="Display name" v={email.from_display} />
              <Row k="Address" v={email.from_address} mono />
              <Row k="Domain" v={email.from_domain} mono />
              <Row
                k="Reply-To"
                v={email.reply_to || 'same as sender'}
                mono={Boolean(email.reply_to)}
              />
              <Row k="Date sent" v={email.date_sent} />
            </dl>
          </section>

          {/* --- What PhishGuard did ------------------------------------ */}
          <section className="section">
            <h3 className="section__title">Action taken</h3>
            <dl className="kv">
              <Row
                k="Gmail label"
                v={email.label_applied || 'none - left untouched'}
                mono={Boolean(email.label_applied)}
              />
              <Row k="Scanned" v={absoluteTime(email.scanned_at)} />
              <Row k="Gmail ID" v={email.gmail_id} mono />
            </dl>
            <p
              style={{
                marginTop: 10,
                fontSize: 12,
                color: 'var(--text-muted)',
              }}
            >
              PhishGuard only ever adds a label. It never deletes, archives,
              or moves mail, so a false positive costs you nothing but a
              label you can remove.
            </p>
          </section>
        </div>
      </aside>
    </>
  )
}

function Row({ k, v, mono = false }) {
  return (
    <div style={{ display: 'contents' }}>
      <dt className="kv__k">{k}</dt>
      <dd className={`kv__v${mono ? ' mono' : ''}`} style={{ margin: 0 }}>
        {v || '—'}
      </dd>
    </div>
  )
}
