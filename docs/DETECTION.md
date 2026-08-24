# Detection

How PhishGuard decides a message is phishing — every signal, every weight, and
what to change when it gets something wrong.

---

## The model in one picture

```
ParsedMessage
     │
     ├── auth.py       → SPF / DKIM / DMARC results
     ├── spoofing.py   → display-name and Reply-To tricks
     ├── urls.py       → link anchors, raw IPs, shorteners
     ├── typosquat.py  → lookalike domains (sender and links)
     └── language.py   → urgency and credential-request wording
                │
                ▼
         engine.analyze()
     each signal contributes a weighted Finding
                │
                ▼
      score = min(sum(weights), 100)
                │
     ┌──────────┼──────────┐
   ≥ 50       ≥ 25       else
     │          │          │
 suspicious    junk      clean
```

Nothing here is probabilistic. Each analyser answers a factual question about
the message, and the engine adds up the answers.

---

## Part 1 — Email authentication, from first principles

The three checks below are the closest thing email has to identity
verification, and they carry the heaviest weights in the engine. Understanding
what they actually prove is the difference between using PhishGuard and
trusting it blindly.

The underlying problem: **SMTP has no authentication**. The protocol was
designed in 1982 among mutually trusting hosts, and the `From:` header is
simply a string the sender types. Anyone can put `security@paypal.com` there.
SPF, DKIM, and DMARC are three layers bolted on afterwards to fix that.

### SPF — Sender Policy Framework

**The question it answers:** *is the server that sent this message on the list
of servers this domain says may send its mail?*

A domain publishes a DNS TXT record naming its authorised senders:

```
example.com.  TXT  "v=spf1 include:_spf.google.com ip4:203.0.113.0/24 -all"
```

The receiving server takes the connecting IP, looks up that record, and checks
whether the IP is covered. `-all` at the end means "and nothing else is
authorised".

**Its blind spot, and it is a big one:** SPF validates the **envelope sender**
(`MAIL FROM`, the SMTP-level address), *not* the `From:` header the user
actually sees. An attacker can pass SPF perfectly for a domain they control
while displaying `From: security@paypal.com`. **An SPF pass is not evidence
the visible sender is real.** It also breaks on forwarding: a forwarded
message arrives from the forwarder's IP, which is not in the original domain's
record.

That is why SPF failure is weighted 15 here, not 30.

### DKIM — DomainKeys Identified Mail

**The question it answers:** *was this message cryptographically signed by a
domain, and is the signature still valid?*

The sending server signs selected headers and the body with a private key and
attaches a `DKIM-Signature` header. The public key lives in DNS. The receiver
fetches it, verifies the signature, and learns two things: which domain signed,
and that the signed parts have not been altered in transit.

**Its blind spot:** the signing domain does not have to be the `From:` domain.
An attacker can validly sign mail as `evil.example` while displaying
`From: security@paypal.com`. DKIM survives forwarding much better than SPF,
which is its main advantage.

Weighted 15, same as SPF, for the same reason: a pass proves less than it
appears to.

### DMARC — the one that actually matters

**The question it answers:** *does SPF or DKIM pass **and align with the
`From:` domain the user sees**, and what does the domain want done if not?*

DMARC is the layer that closes the gap in the other two. It adds
**alignment**: it is not enough for SPF or DKIM to pass for *some* domain;
they must pass for the domain in the visible `From:` header. It also lets the
domain publish a policy:

```
_dmarc.example.com.  TXT  "v=DMARC1; p=reject; rua=mailto:reports@example.com"
```

`p=reject` means: if a message claims to be from us and fails alignment, throw
it away.

**Why it is weighted 30 — double the others.** A DMARC failure on a domain
that publishes a policy means the message claims to be from that domain and
the domain itself says it is not. That is about as close to proof of forgery
as email offers.

**The important caveat:** many domains publish no DMARC record at all. That is
`none`, not `fail` — it is the absence of a claim, not a failed one, and the
engine treats it that way. This is exactly why the dashboard's authentication
chart has **three** states rather than two: pass, fail, and *no claim made*.
Collapsing that third state into either pole would be wrong in both
directions.

### How PhishGuard reads them

It does not run these checks itself. Gmail already ran them at delivery and
recorded the outcome in the `Authentication-Results` header:

```
mx.google.com;
  spf=pass (google.com: domain of ...) smtp.mailfrom=news@example.com;
  dkim=pass header.i=@example.com;
  dmarc=pass (p=REJECT sp=REJECT dis=NONE) header.from=example.com
```

`auth.py` parses this with three small regexes, falling back to
`ARC-Authentication-Results` when the primary header is missing (ARC preserves
the original results across forwarding hops).

Re-running the checks locally would mean re-resolving DNS long after delivery,
against records that may have changed, from an IP that is not the one that
received the message. Gmail's answer is both more accurate and free.

**Result bucketing:**

| Bucket | Values | Treated as |
|---|---|---|
| pass | `pass` | Verified |
| fail | `fail`, `softfail`, `permerror`, `reject`, `quarantine` | Failed — scored |
| other | `none`, `neutral`, `temperror`, missing header | No claim — **not** scored |

`softfail` is bucketed with failure deliberately. It means "this probably is
not us" — a real negative signal, even if a soft one.

---

## Part 2 — Every signal and its weight

Weights are set so that **one strong signal alone is never enough** to reach
`suspicious` (50). It always takes a combination. This is the single most
important property of the scoring table, because any individual heuristic has
false positives, and combinations of them have far fewer.

### Authentication

| Code | Weight | Fires when |
|---|---|---|
| `dmarc_fail` | **30** | DMARC result is in the fail bucket |
| `spf_fail` | **15** | SPF result is in the fail bucket |
| `dkim_fail` | **15** | DKIM result is in the fail bucket |

DMARC failure alone scores 30 → `junk`, not `suspicious`. Broken mail server
configurations are common enough that a single failure should not accuse
anyone of phishing. All three failing together is 60 → `suspicious`, and mail
that fails all three is genuinely almost never legitimate.

### Sender spoofing (`spoofing.py`)

| Code | Weight | Fires when |
|---|---|---|
| `display_name_spoof` | **30** | The display name contains a brand name the sending domain does not own |
| `display_email_mismatch` | **20** | The display name embeds an email address on a different domain than the real sender |
| `reply_to_mismatch` | **15** | `Reply-To` is on a different registrable domain than `From` |

**Display-name spoofing** is the most common trick in commodity phishing,
because mobile mail clients show the display name and hide the address
entirely. `From: "PayPal Security" <service@paypa1-secure.example>` renders as
just **PayPal Security** on a phone. The check is a substring match of each
brand in `BRAND_DOMAINS` against the lowercased display name, firing only when
the sending domain is not one the brand actually owns.

**Reply-To mismatch** is weighted low at 15 on purpose. It is a real phishing
technique — send from a throwaway domain, collect replies somewhere else — but
it is also completely normal for mailing lists, ticketing systems, and
no-reply senders. On its own it should never accuse anything.

### Typosquatting (`typosquat.py`)

| Code | Weight | Fires when |
|---|---|---|
| `typosquat_domain` | **30** | The **sender** domain impersonates a brand |
| `typosquat_link` | **25** | A **link** domain impersonates a brand |
| `lookalike_domain` | **30** | Fallback: `spoofing.py`'s simpler check, only when the dedicated detector finds nothing |

Four techniques are recognised:

| Technique | What it is | Example |
|---|---|---|
| `homoglyph` | Characters that look like other characters | `paypa1.com`, `g00gle.com`, `rnicrosoft.com` (`rn` → `m`) |
| `typo` | Small edit-distance change | `gogle.com`, `micrsoft.com`, `amazn.com` |
| `combo` | Brand embedded with extra words | `paypal-secure.example`, `secure-amazon-billing.example` |
| `tld_swap` | Real brand label, wrong TLD | `paypal.co`, `netflix.tv` |

Detection normalises homoglyphs first (`paypa1` → `paypal`), then measures
Levenshtein distance to each known brand, then checks for the brand appearing
as a token in a hyphen- or dot-split label.

**Links are weighted slightly lower (25) than senders (30)** because a
legitimate message can carry a link to a domain the sender does not control —
a tracking redirector, a partner site — whereas the sender domain is the
sender's own claim about who they are.

The brand list in `spoofing.py` is short and deliberately so: the most-phished
consumer brands. Every entry adds false-positive surface, so adding one should
mean it is worth that cost.

### Links (`urls.py`)

| Code | Weight | Fires when |
|---|---|---|
| `url_mismatch` | **25** | Anchor text looks like a URL but points somewhere else |
| `ip_url` | **20** | A link's host is a raw IP address |
| `url_shortener` | **10** | A link uses a known shortening service |

**Anchor mismatch** is the classic. `<a href="https://evil.example/login">
https://www.paypal.com/signin</a>` displays one destination and goes to
another. The check only fires when the anchor *text itself parses as a URL* —
comparing registrable domains, so `www.paypal.com` vs `paypal.com` does not
trip it. Ordinary link text ("click here", "View invoice") is ignored, because
there is nothing to compare.

**Raw IP links** at 20: legitimate senders use hostnames. A raw IP in a
consumer email is either an attacker's box or a badly misconfigured system,
and both are worth flagging.

**Shorteners** at 10 — deliberately weak. Shorteners hide destinations, which
is useful to an attacker, but they are also used constantly by legitimate
marketing. This is a tiebreaker, never an accusation.

### Language (`language.py`)

| Code | Weight | Fires when |
|---|---|---|
| `credential_request` | **20** | Text matches a credential-request pattern |
| `urgency` | **10** | Text matches an urgency/pressure pattern |

Two regex sets over subject + plain-text body:

- **Credential requests** — "verify your account", "confirm your password",
  "update your billing", "click here to verify", "enter your PIN". Asking for
  credentials by email is the actual payload of most phishing.
- **Urgency** — "urgent", "immediately", "within 24 hours", "account will be
  suspended", "final notice", "unusual sign-in activity", "limited time".
  Manufactured time pressure is the standard social-engineering lever: it
  exists to stop you thinking.

Both are weighted low because **legitimate mail uses this language too**. Your
bank really does send "unusual sign-in activity" alerts. A retailer really
does say "limited time". These are supporting evidence, never the case.

### Bulk mail (`engine.py`)

| Code | Weight | Fires when |
|---|---|---|
| `bulk_mail` | **12** | `List-Unsubscribe` or `List-Id` header present |

Weighted at 12 for a very specific reason: it is under the junk threshold of
25 on its own, so a well-behaved newsletter you subscribed to stays `clean`.
Combined with anything else — urgency (22), a shortener (22), or both (32) —
it tips into `junk`. And 12 is small enough that bulk mail can never reach
`suspicious` on the strength of being bulk.

That is the whole design of this signal: mailing lists are not phishing, and
the verdict should say so.

---

## Part 3 — Thresholds

```python
suspicious_threshold: int = 50   # SUSPICIOUS_THRESHOLD
junk_threshold: int = 25         # JUNK_THRESHOLD
```

The final score is capped at 100 (`score = min(score, 100)`) so the meter and
the score column always mean the same thing.

**Worked examples** — the demo data in `app/tools/seed_demo.py` produces
exactly these:

| Message | Signals | Score | Verdict |
|---|---|---|---|
| Personal email, all auth passing | none | 0 | clean |
| Newsletter, all auth passing | bulk (12) | 12 | clean |
| Promo with countdown + shortener | bulk (12) + urgency (10) + shortener (10) | 32 | **junk** |
| Unauthenticated bulk spam | bulk (12) + SPF fail (15) | 27 | **junk** |
| Fake invoice, raw-IP link | DMARC (30) + IP link (20) + SPF (15) | 65 | **suspicious** |
| Full PayPal lure | DMARC 30 + display spoof 30 + typosquat 30 + url mismatch 25 + credentials 20 + SPF 15 + DKIM 15 + Reply-To 15 + urgency 10 = 190, capped | 100 | **suspicious** |

Note the last one: nine independent signals. That is what a real commodity
phishing message looks like to this engine, and it is why the thresholds do
not need to be aggressive.

---

## Part 4 — Tuning it

Everything below is a `.env` change plus a restart. **No code edit required.**

### Too many false positives (legitimate mail getting flagged)

1. Open the message in the dashboard and read its findings list. The panel
   shows every signal that fired and what it added.
2. If one signal is doing all the damage, raise `SUSPICIOUS_THRESHOLD` so that
   signal plus one other is needed rather than that signal alone.
3. If a domain you trust is being caught by `typosquat_domain`, check whether
   it genuinely resembles a brand in `BRAND_DOMAINS` — sometimes the honest
   answer is that the domain really is confusable and the finding is correct.

Sensible first move: `SUSPICIOUS_THRESHOLD=60`.

### Too many false negatives (phishing getting through)

1. Run the message through the offline scanner to see what fired:

   ```bash
   python -m app.tools.scan_eml suspicious_message.eml
   ```
   (Save the message from Gmail via **⋮ → Download message**.)

2. If nothing fired, no threshold change will help — the engine has no signal
   for whatever that message did. Consider adding the impersonated brand to
   `BRAND_DOMAINS`, or a new pattern to `language.py`.
3. If signals fired but summed under 50, lower `SUSPICIOUS_THRESHOLD` to 40
   and watch the false-positive rate.

### Tuning safely

Because PhishGuard only ever adds labels, you can run aggressive settings for
a week and read the results rather than reasoning about them. Set
`SUSPICIOUS_THRESHOLD=40`, leave it, then look at the Suspicious filter in the
dashboard and count how many were actually wrong. That is a real measurement,
and it costs you nothing but labels you can remove.

### Verifying a change without waiting

`app/tools/scan_eml.py` scores any `.eml` file offline. `app/tools/seed_demo.py`
regenerates the demo dataset through the real engine — after changing weights,
re-seed and the dashboard immediately shows what the new settings do to a
realistic mix.

---

## Part 5 — What real mail actually did to it

Synthetic test data tells you the engine works. Real mail tells you what it
gets wrong. Two rounds against a live inbox, recorded here because the failure
modes are more instructive than the successes.

### Round one: 11 messages, 2 flagged, both wrong

Both flags were `typosquat_link`:

| Sender | Link | Flagged as |
|---|---|---|
| `microsoft.com` | `microsoftonline.com` | impersonating *microsoft* |
| `google.com` | `googleusercontent.com` | impersonating *google* |

Both are the brand's **own infrastructure**. The combosquat rule fires on
"brand name embedded in a longer domain", which those are — legitimately.

Fixed two ways: first-party infrastructure domains were added to
`BRAND_DOMAINS`, and because that list can never be exhaustive, a sender is
now exempt from link-typosquat findings against **its own** brand. Four
regression tests cover it.

### Round two: 822 messages, 81 flagged, 10 suspicious — all 10 still wrong

A larger window exposed two *systematic* false-positive sources that remain
open:

**1. Click-tracking redirects trip `url_mismatch` (65 occurrences).**
Newsletters route links through their own tracking domain while displaying the
publisher's name:

```
anchor text: tldr.tech      href: tldrnewsletter.com     -> +25
anchor text: playstation.com href: playstationemail.com   -> +25
```

This is the single most common signal in the whole corpus, and in this inbox
it was **never** phishing. It is also a genuine phishing technique, which is
what makes it hard: the mechanism is identical, only the intent differs.

**2. Brand-owned alternate domains trip `typosquat_*` (11 occurrences).**

| Domain | Flagged as | Reality |
|---|---|---|
| `amazon.jobs` | tld_swap of *amazon* | Amazon's careers site |
| `google.dev` | tld_swap of *google* | Google's developer site |
| `googleblog.com` | combo of *google* | Google's blog |
| `microsoft.ai` | tld_swap of *microsoft* | linked news article |

The `tld_swap` rule assumes a brand label under an unexpected TLD is hostile.
Large companies own dozens of TLDs, so that assumption is wrong often.

### What this tells you

**Precision on this corpus was 0%.** 822 messages, 81 flags, zero real
phishing. Two honest readings, and both are true:

- The inbox genuinely contained no phishing, so there were no true positives
  *available* to find. A 0% rate over a corpus with zero positives says
  nothing about recall.
- The false-positive rate is nonetheless too high to leave alone. 10
  "suspicious" verdicts a month, all wrong, trains you to ignore the label —
  which is the precise failure that makes a filter worse than none.

This is why the label-only design matters: a month of 100%-wrong verdicts cost
nothing but labels. Had it been deleting or archiving, the same tuning
exercise would have meant lost mail.

Candidate fixes, not yet applied:

- Treat an anchor/href mismatch as weak (10) when the href domain's mail
  authenticates and aligns with the From domain — a tracker on authenticated
  bulk mail is not the same as a link swap on unauthenticated mail.
- Extend `BRAND_DOMAINS` with brand-owned alternate TLDs, and drop `tld_swap`
  confidence for TLDs large brands actually use (`.dev`, `.jobs`, `.ai`).
- Require a second, independent signal before `typosquat_link` alone can push
  a message to `suspicious`.

## Part 6 — Honest limitations

**What this catches well:** mass-mailed commodity phishing. Failed
authentication, brand impersonation in display names, lookalike domains,
mismatched links, urgency plus credential requests. This is the overwhelming
majority of what reaches a personal inbox.

**What it will not catch:**

- **Targeted spear-phishing.** A message written for you specifically, sent
  from a properly authenticated compromised account, with no urgency language
  and no suspicious links. Every signal here reads clean, because every signal
  *is* clean — the attack is in the content, not the mechanics.
- **Compromised legitimate accounts.** If a real colleague's account is taken
  over, SPF, DKIM, and DMARC all pass correctly. They are supposed to.
- **Attachment-based attacks.** Malicious PDFs and Office macros are not
  examined at all. Attachment analysis is a genuinely different problem
  requiring sandboxing.
- **Non-English social engineering.** The language patterns are English-only.
- **Brands outside the list.** Impersonation of a company not in
  `BRAND_DOMAINS` gets no display-name or typosquat signal.
- **URL redirect chains.** A link to a legitimate-looking redirector that
  bounces to an attacker's site is judged on the redirector's domain.
  Following redirects would mean making outbound requests to URLs from
  untrusted email, which is a worse idea than the detection is worth.

**The correct mental model** is a smoke detector, not a security guard. It is
a fast, cheap, local heuristic that catches the obvious cases and shows its
reasoning, so that the judgement about anything it flags stays yours.
