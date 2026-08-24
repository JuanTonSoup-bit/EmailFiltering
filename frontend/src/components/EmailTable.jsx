import { AuthChip, ScoreMeter, VerdictBadge } from './Badges.jsx'
import { EmptyState } from './ChartCard.jsx'
import { relativeTime } from '../lib/format.js'

/**
 * The recent-messages table.
 *
 * This is the layer of the dashboard that turns aggregate numbers back into
 * individual pieces of mail. Charts answer "how much"; only this answers
 * "which one, and what should I do about it".
 *
 * Every row is a button in behaviour: clickable, focusable, and openable
 * with Enter or Space. It is a <tr> rather than a real <button> because a
 * button cannot contain table cells, so the keyboard behaviour is supplied
 * by hand - tabIndex, role, and a keydown handler - rather than left to a
 * mouse-only interaction.
 *
 * Nothing here is truncated silently: a clipped subject keeps its full text
 * in the title attribute, and the detail panel shows everything.
 */
export function EmailTable({ emails, onSelect, selectedId }) {
  if (!emails || emails.length === 0) {
    return (
      <EmptyState title="No messages match this filter">
        Try “All”, or run a scan to pull in recent mail.
      </EmptyState>
    )
  }

  return (
    <div className="mailtable__wrap">
      <table className="mailtable">
        <caption className="sr-only">
          Scanned messages, newest first. Select a row to see why it was
          scored the way it was.
        </caption>
        <thead>
          <tr>
            <th scope="col">Verdict</th>
            <th scope="col">Subject / sender</th>
            <th scope="col">Authentication</th>
            <th scope="col" style={{ textAlign: 'right' }}>
              Score
            </th>
            <th scope="col" style={{ textAlign: 'right' }}>
              Scanned
            </th>
          </tr>
        </thead>
        <tbody>
          {emails.map((email) => (
            <tr
              key={email.id}
              tabIndex={0}
              role="button"
              aria-label={`Open details for ${email.subject || '(no subject)'}`}
              aria-current={email.id === selectedId ? 'true' : undefined}
              onClick={() => onSelect(email)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' || event.key === ' ') {
                  event.preventDefault()
                  onSelect(email)
                }
              }}
            >
              <td>
                <VerdictBadge verdict={email.verdict} />
              </td>

              <td className="cell-subject">
                <span
                  className="cell-subject__line"
                  title={email.subject || ''}
                >
                  {email.subject || <em>(no subject)</em>}
                </span>
                <span
                  className="cell-subject__line cell-subject__from"
                  title={email.from_address || ''}
                >
                  {email.from_display
                    ? `${email.from_display} · ${email.from_address || ''}`
                    : email.from_address || 'unknown sender'}
                </span>
              </td>

              <td>
                <div className="chips chips--nowrap">
                  <AuthChip mechanism="spf" result={email.spf} compact />
                  <AuthChip mechanism="dkim" result={email.dkim} compact />
                  <AuthChip mechanism="dmarc" result={email.dmarc} compact />
                </div>
              </td>

              <td className="cell-num">
                <ScoreMeter score={email.score} />
              </td>

              <td className="cell-num" title={email.scanned_at}>
                {relativeTime(email.scanned_at)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
