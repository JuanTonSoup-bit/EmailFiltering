"""Populate the database with realistic demo data - no Gmail account needed.

    python -m app.tools.seed_demo            # ~120 messages over 21 days
    python -m app.tools.seed_demo --days 45 --count 300
    python -m app.tools.seed_demo --reset    # wipe existing rows first

Why this exists
---------------
Two reasons, and neither is decoration.

1. The dashboard cannot be developed, reviewed, or screenshotted until the
   database has something in it, and the only other way to fill it is to
   complete a Google Cloud OAuth flow against a real inbox. That is a large
   obstacle in front of a small task.

2. It doubles as an end-to-end check of the detection engine. Nothing here
   hard-codes a verdict: every row is a synthetic message run through the
   real `analyze()` function, which means the scores and findings shown in
   the demo are the scores and findings the engine actually produces. If a
   weight changes in engine.py, the demo data changes with it.

The synthetic phishing messages are modelled on well-worn commodity lures -
the kind that arrive in any inbox. Nothing here targets a real person or
organisation, and the lookalike domains all use RFC 2606 reserved names
(.example / example.com), which can never resolve.
"""

from __future__ import annotations

import argparse
import datetime as dt
import random

from ..analysis import analyze
from ..analysis.message import ParsedMessage
from ..config import settings
from ..db import SessionLocal, init_db
from ..models import ScannedEmail

# --------------------------------------------------------------------------
# Message templates
#
# Each template is (weight, builder). Weight controls how often the template
# is picked, so the generated mix looks like a real inbox: mostly legitimate
# mail, a decent amount of marketing, and phishing as the rare case. A demo
# that is 50% phishing would make the dashboard look absurd and would hide
# the exact problem the design has to solve - finding a few bad messages
# among many good ones.
# --------------------------------------------------------------------------


def _auth_header(spf: str, dkim: str, dmarc: str) -> str:
    return f"mx.google.com; spf={spf} smtp.mailfrom=example.com; dkim={dkim}; dmarc={dmarc}"


def _message(
    *,
    gmail_id: str,
    subject: str,
    display: str,
    address: str,
    domain: str,
    body_text: str = "",
    body_html: str = "",
    spf: str = "pass",
    dkim: str = "pass",
    dmarc: str = "pass",
    reply_to: str = "",
    reply_to_domain: str = "",
    bulk: bool = False,
) -> ParsedMessage:
    headers = {"authentication-results": _auth_header(spf, dkim, dmarc)}
    if bulk:
        headers["list-unsubscribe"] = "<https://lists.example.com/u/123>"
        headers["list-id"] = "news.lists.example.com"
    if reply_to:
        headers["reply-to"] = reply_to

    return ParsedMessage(
        gmail_id=gmail_id,
        thread_id=f"thread-{gmail_id}",
        headers=headers,
        subject=subject,
        from_address=address,
        from_display=display,
        from_domain=domain,
        reply_to=reply_to,
        reply_to_domain=reply_to_domain,
        to_address="you@gmail.com",
        date_sent="",
        body_text=body_text,
        body_html=body_html,
        label_ids=["INBOX"],
    )


def legit_personal(i: int) -> ParsedMessage:
    who = random.choice(
        ["Dana Whitfield", "Marcus Reyes", "Priya Raman", "Tom Okafor"]
    )
    subject = random.choice(
        [
            "Re: study group Thursday",
            "notes from the meeting",
            "Are you free Friday?",
            "Re: that link you sent",
        ]
    )
    return _message(
        gmail_id=f"demo-legit-{i}",
        subject=subject,
        display=who,
        address=f"{who.split()[0].lower()}@mail.example.com",
        domain="mail.example.com",
        body_text="Sounds good, see you then.",
    )


def legit_transactional(i: int) -> ParsedMessage:
    return _message(
        gmail_id=f"demo-txn-{i}",
        subject=random.choice(
            [
                "Your receipt from Riverside Coffee",
                "Your order has shipped",
                "Security alert: new sign-in",
                "Your monthly statement is ready",
            ]
        ),
        display="Riverside",
        address="no-reply@riverside.example.com",
        domain="riverside.example.com",
        body_text="Thanks for your order. Track it in your account.",
        body_html='<p>Thanks for your order. <a href="https://riverside.example.com/orders">Track it</a>.</p>',
    )


def marketing_plain(i: int) -> ParsedMessage:
    """Well-behaved bulk mail: authenticates cleanly, carries
    List-Unsubscribe, no pressure language.

    This scores 12 - the bulk signal alone - which is under the junk
    threshold of 25, so it stays `clean`. That is the engine working as
    designed: a newsletter you subscribed to is not junk just because it is
    bulk, and List-Unsubscribe on its own is a weak signal that only tips
    something over when it is already borderline.
    """
    return _message(
        gmail_id=f"demo-bulk-{i}",
        subject=random.choice(
            [
                "Your weekly digest",
                "New arrivals just dropped",
                "This month at Northwind",
                "Your reading list for the week",
            ]
        ),
        display="Northwind",
        address="news@news.northwind.example.com",
        domain="northwind.example.com",
        body_text="Here is what is new this week. Unsubscribe any time.",
        body_html='<p>What is new. <a href="https://northwind.example.com/new">Read more</a></p>',
        bulk=True,
    )


def marketing_pushy(i: int) -> ParsedMessage:
    """Pressure-selling bulk mail: List-Unsubscribe, a countdown, and a
    shortened link. Bulk + urgency + shortener clears the junk threshold
    without coming close to `suspicious`, which is the distinction the two
    thresholds exist to draw."""
    return _message(
        gmail_id=f"demo-promo-{i}",
        subject=random.choice(
            [
                "Limited time: 30% off everything",
                "Your cart expires today",
                "Last chance - limited time offer inside",
                "We miss you - limited time 15% off",
            ]
        ),
        display="Northwind Deals",
        address="deals@promo.northwind.example.com",
        domain="northwind.example.com",
        body_text="Limited time offer - the sale expires today. Shop now.",
        body_html='<p>Shop the sale: <a href="https://bit.ly/4kNwDeal">Shop now</a></p>',
        bulk=True,
    )


def spam_unauthenticated(i: int) -> ParsedMessage:
    """Low-effort bulk spam that cannot authenticate. SPF failure plus the
    bulk signal makes junk without any phishing signals at all."""
    return _message(
        gmail_id=f"demo-spam-{i}",
        subject=random.choice(
            [
                "You have been selected for a reward",
                "Work from home - start today",
                "Your free trial is waiting",
            ]
        ),
        display="Rewards Team",
        address="offers@mail.rewards-hub.example",
        domain="rewards-hub.example",
        body_text="Claim your reward by following the link below.",
        body_html='<p><a href="https://rewards-hub.example/claim">Claim now</a></p>',
        spf="fail",
        dkim="none",
        dmarc="none",
        bulk=True,
    )


def phish_credential(i: int) -> ParsedMessage:
    """The classic: failed authentication, brand impersonation in the
    display name, a mismatched link, and urgent credential-request wording.
    Should score high enough to be flagged `suspicious`."""
    return _message(
        gmail_id=f"demo-phish-{i}",
        subject="Urgent: your account will be suspended in 24 hours",
        display="PayPal Security",
        address="service@paypa1-secure.example",
        domain="paypa1-secure.example",
        body_text=(
            "We detected unusual activity. Verify your password immediately "
            "or your account will be permanently suspended within 24 hours."
        ),
        body_html=(
            '<p>Verify now: <a href="https://paypa1-secure.example/login">'
            "https://www.paypal.com/signin</a></p>"
        ),
        spf="fail",
        dkim="fail",
        dmarc="fail",
        reply_to="recovery@mailbox.example",
        reply_to_domain="mailbox.example",
    )


def phish_invoice(i: int) -> ParsedMessage:
    """Business-email-compromise shape: authenticates weakly, links to a raw
    IP, and asks for an urgent payment action."""
    return _message(
        gmail_id=f"demo-invoice-{i}",
        subject="Outstanding invoice #4471 - immediate payment required",
        display="Accounts Payable",
        address="billing@invoice-portal.example",
        domain="invoice-portal.example",
        body_text=(
            "Your invoice is overdue. Confirm your billing details today to "
            "avoid a late fee."
        ),
        body_html='<p><a href="http://203.0.113.44/invoice/4471">View invoice</a></p>',
        spf="fail",
        dkim="none",
        dmarc="fail",
    )


def phish_shortener(i: int) -> ParsedMessage:
    """Softer signals only - a shortener plus urgency, no auth failure. This
    one usually lands in the middle of the score range, which is exactly the
    case the explainability panel exists for."""
    return _message(
        gmail_id=f"demo-short-{i}",
        subject="Action required: confirm your delivery address",
        display="Parcel Notice",
        address="notice@parcel-track.example.com",
        domain="parcel-track.example.com",
        body_text="Your parcel is on hold. Confirm your address immediately.",
        body_html='<p><a href="https://bit.ly/3xAbCdE">Confirm address</a></p>',
        spf="pass",
        dkim="none",
        dmarc="none",
    )


TEMPLATES = [
    (30, legit_personal),
    (22, legit_transactional),
    (14, marketing_plain),
    (16, marketing_pushy),
    (6, spam_unauthenticated),
    (5, phish_credential),
    (4, phish_invoice),
    (3, phish_shortener),
]


def _pick(rng: random.Random):
    total = sum(weight for weight, _ in TEMPLATES)
    roll = rng.uniform(0, total)
    upto = 0.0
    for weight, builder in TEMPLATES:
        upto += weight
        if roll <= upto:
            return builder
    return TEMPLATES[-1][1]


def seed(count: int, days: int, reset: bool, seed_value: int | None) -> dict:
    rng = random.Random(seed_value)
    init_db()

    verdict_counts: dict[str, int] = {}
    now = dt.datetime.now(dt.timezone.utc)

    with SessionLocal() as session:
        if reset:
            deleted = session.query(ScannedEmail).delete()
            session.commit()
            print(f"Removed {deleted} existing rows.")

        for i in range(count):
            builder = _pick(rng)
            msg = builder(i)
            result = analyze(msg)

            # Spread the messages across the window, with more of them on
            # recent days so the timeline has some shape instead of being a
            # flat block.
            age_days = min(days - 1, int(abs(rng.gauss(0, days / 3))))
            scanned_at = now - dt.timedelta(
                days=age_days,
                hours=rng.uniform(0, 23),
                minutes=rng.uniform(0, 59),
            )

            label = None
            if result.verdict == "suspicious":
                label = settings.label_suspicious
            elif result.verdict == "junk":
                label = settings.label_junk

            session.add(
                ScannedEmail(
                    # Suffixed with the index so re-running without --reset
                    # cannot collide on the unique gmail_id constraint.
                    gmail_id=f"{msg.gmail_id}-{int(now.timestamp())}-{i}",
                    thread_id=msg.thread_id,
                    from_address=msg.from_address,
                    from_display=msg.from_display,
                    from_domain=msg.from_domain,
                    reply_to=msg.reply_to or None,
                    subject=msg.subject,
                    date_sent=scanned_at.strftime("%a, %d %b %Y %H:%M:%S %z"),
                    spf=result.spf,
                    dkim=result.dkim,
                    dmarc=result.dmarc,
                    score=result.score,
                    verdict=result.verdict,
                    findings=result.findings_dict,
                    label_applied=label,
                    scanned_at=scanned_at,
                )
            )
            verdict_counts[result.verdict] = verdict_counts.get(result.verdict, 0) + 1

        session.commit()

    return verdict_counts


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fill the PhishGuard database with demo data.",
    )
    parser.add_argument("--count", type=int, default=120, help="messages to create")
    parser.add_argument("--days", type=int, default=21, help="spread over this many days")
    parser.add_argument("--reset", action="store_true", help="delete existing rows first")
    parser.add_argument("--seed", type=int, default=None, help="RNG seed, for repeatable data")
    args = parser.parse_args()

    counts = seed(args.count, args.days, args.reset, args.seed)

    print(f"Seeded {args.count} messages across {args.days} days:")
    for verdict in ("clean", "junk", "suspicious"):
        print(f"  {verdict:<11} {counts.get(verdict, 0)}")
    print("\nThese were scored by the real detection engine, not hard-coded.")
    print("Start the API and open the dashboard to see them.")


if __name__ == "__main__":
    main()
