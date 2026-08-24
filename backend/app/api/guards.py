"""Request guards for state-changing endpoints.

THE PROBLEM
-----------
PhishGuard listens on localhost with no authentication, which is fine for
reading: nothing else on the machine is interested in your scan history.

Writes are different. A browser will happily send a cross-origin POST to
http://127.0.0.1:8000 from any page you happen to be visiting. With
`fetch(url, {method: 'POST', mode: 'no-cors'})` the response is unreadable to
the attacker, but *the request still arrives*. So any website could trigger
scans, and -- once a shutdown endpoint exists -- silently switch off your mail
filter. That is a real, if small, attack: the tool goes quiet and you have no
reason to look.

THE FIX
-------
Require a custom header. Custom headers are exactly the thing that forces the
browser to send a CORS preflight (OPTIONS) first, and the preflight is checked
against this app's origin allowlist. A page on evil.example gets its preflight
refused and the real request is never sent. There is no way for a page to opt
out of that -- it is enforced by the browser, not by us.

Callers that are *not* pages are unaffected:
  * the dashboard is served from this same origin, so it just sets the header
  * the extension fetches with host_permissions, which are privileged and not
    subject to page CORS
  * curl and scripts set the header explicitly (see the README)

This is not authentication and does not pretend to be. Anything already
running locally can set a header. It closes the specific hole where a *remote
web page* drives your local API, which is the one that matters here.
"""

from __future__ import annotations

from fastapi import HTTPException, Request

CLIENT_HEADER = "X-PhishGuard-Client"


async def require_client_header(request: Request) -> None:
    """Reject state-changing requests that no first-party client would send."""
    if not request.headers.get(CLIENT_HEADER):
        raise HTTPException(
            status_code=403,
            detail=(
                f"Missing {CLIENT_HEADER} header. This endpoint changes state "
                f"and is protected against cross-site requests. Send the "
                f"header, e.g. curl -X POST -H '{CLIENT_HEADER}: cli' ..."
            ),
        )
