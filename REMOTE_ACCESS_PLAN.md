# Private remote chat and media: planned next stage

Status: roadmap recorded 2026-10-19 and expanded 2026-10-22 at Alexander's
request. October 23 adds a local-only working preview (LOCAL_WEB_PORTAL.md);
remote authentication, connectivity and deployment remain planned. The local app has static
HTML/CSS Artifact previews; that is separate from exposing the AI on a website.
The desktop can explicitly start a loopback-only preview. No tunnel/model or
account was added, and no firewall/router setting changed.

## Intended experience

Alexander opens a private HTTPS address in a browser away from the laptop, signs
in with his own account, chats with the local model, and requests image/video
generation. A web Artifacts gallery shows job status and completed media. The
Acer runs inference and retains outputs; it must be powered on, awake, connected
and running the service. Remote browser access does not make laptop inference
available while the laptop is off.

The longer-term local goal remains broader computer use through individually
guarded adapters. The remote surface will offer text chat, image generation,
video generation and viewing/exporting that account's media only. It must not
offer computer control, screenshots, browser automation, shell execution,
filesystem browsing or access to the existing desktop tool dispatcher.

## School/browser access: explicit product requirements (October 22)

- Alexander opens a private HTTPS address using an ordinary permitted browser
  at school or on his own phone. No special client should be required for the
  browser-only option. School/device policy can still prevent access; this plan
  does not bypass it. Desktop and web should refer to one owner's saved jobs and
  chats once owner-bound remote storage exists. The local saved-chat library now
  persists explicit snapshots, but web sync and account authorization are not
  implemented. A local library ID is not an authenticated remote owner.
- Restrict access to one provisioned owner, with no public signup. Use a maintained
  login system or identity provider, password/passkey support and MFA. An emailed
  one-time code alone is not automatically two-factor authentication. A shared
  link is only an address, never sufficient authorization. Short, revocable
  sessions and explicit sign-out must work on a shared browser.
- The web MVP offers text chat, explicit image/video requests, job status and
  the owner's Artifacts/media. No remote clicks, typing, screen capture, browser
  automation, arbitrary local-file access, shell or desktop dispatcher. The server
  enforces the capability list even if a caller invents an endpoint/tool name.
- The laptop stays awake, online and running the service. If unavailable, show
  an honest offline message. Reconnect to existing job IDs after network loss;
  never duplicate an expensive image/video job because its response was lost.
- Put a reviewed HTTPS gateway/tunnel in front of a loopback-bound web backend.
  Cloudflare Tunnel with Access is one browser-only candidate; Tailscale Serve
  is a private-network alternative for devices allowed to run its client.
  These are options, not a selected vendor or deployed service. Do not expose
  Ollama's port, a development server, or the existing desktop app to the Internet.
- If using gateway identity, validate its signed tokens and expected issuer,
  audience and owner server-side. Do not trust a caller-supplied email/header or
  leave a direct route around authentication. Every API and media response needs
  authorization, including previews, cancellation and downloads.
- Inference remains on the Acer. A tunnel/gateway provider transports traffic
  and may terminate HTTPS; do not describe that as end-to-end private from the
  provider. Document retention and the chosen provider's trust boundary before
  deployment. Authentication reduces access risk; it cannot guarantee perfection.
- Local and remote work share one GPU job manager, with admission limits and a
  bounded queue. A separate web process must not copy the current Python lock
  and assume it synchronizes with the desktop process. One broker/IPC design is
  required before concurrent local/remote media work is enabled.

## Build order and boundaries

1. Define separate web request schemas and a server-side capability allowlist.
   Text chat uses no tools. Image/video actions are explicit, exact-prompt
   requests with fixed generation parameters. Model output cannot invoke other
   local capabilities. A hidden button is not an authorization check.
2. Introduce persistent, bounded job and media records. Bind every job, cancel,
   preview and download to the authenticated owner. Use opaque IDs, not caller
   paths. Serve only the owned immutable media bytes, never a static directory
   rooted at the project or Downloads. Keep old local files private until an
   explicit import/migration policy exists.
3. Serialize remote and local GPU use through a common queue. Start with one
   active generation and a small bounded queue; retain timeouts, cancellation,
   output-size limits and model unloading. Define disk quotas and person-approved
   cleanup before enabling persistent generation. No endless queued jobs or
   automatic mutation retries after an uncertain result.
4. Build the chat, image and silent video UI with queued/running/completed/failed
   states and mobile-friendly media previews. Display generated HTML/code as
   inert text initially. A later server-side static HTML/CSS picture preview
   must retain the local renderer's isolation, quotas and owner checks; it must
   never become an unrestricted browser or executable webview. Reconnect to job
   IDs after a dropped connection rather than
   submitting the same generation again.
5. Add and verify authentication and transport before any off-laptop exposure.
   Use a maintained authentication component with one administrator-provisioned
   owner account, no public signup, username/password support, secure password
   hashing, MFA, throttling and generic login failures. Keep credentials out of
   source and logs. Use HTTPS, server-managed expiring/revocable sessions,
   Secure/HttpOnly/SameSite cookies and CSRF protection for state changes.
6. Choose connectivity with Alexander. A private authenticated network can keep
   the service off the public Internet, but needs a permitted client on the
   visiting device. Browser-only access without that client needs an authenticated
   HTTPS gateway. Do not expose Ollama, the current desktop app or a development
   server directly. No deployment or credentials are selected by this roadmap.

## Acceptance checks before remote use

- Unauthenticated, logged-out, expired and revoked sessions cannot chat, submit
  jobs or retrieve any preview/download. CSRF and cross-origin requests refuse.
- Another session/account cannot access a guessed job/media ID or cancel it.
  Authentication is checked on media downloads as well as the page itself.
- Malformed requests, arbitrary file paths and every desktop/browser/shell tool
  name refuse at the server dispatcher. Prompt injection cannot enlarge its
  fixed capabilities. The text endpoint has no tool execution path.
- Denial/Stop, cancellation, restarts, lost replies, GPU contention, queue limits,
  disk limits and a sleeping/offline laptop produce explicit states, not a
  false success or duplicate generation. Existing files are not overwritten.
- Test from a second device only after local fake/offline tests, authenticated
  loopback integration and deployment configuration review pass.

Authentication reduces unauthorized access; it is not a promise of perfect
security. Remote use adds an attack surface and needs its own review and tests.
The local website preview has not passed those deployment gates and must not
be forwarded publicly as a remote service.

## Design references

The authentication and session requirements above draw on OWASP guidance:
[Authentication](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html)
and [Session management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html).
For the private-network option, Tailscale documents
[Serve](https://tailscale.com/docs/features/tailscale-serve) as a way to share a
local service within a tailnet. This is an option to evaluate, not an installed
dependency or a selected deployment.


Current connectivity references checked October 22, 2026:
[Cloudflare private browser application](https://developers.cloudflare.com/cloudflare-one/setup/secure-private-apps/private-web-app/),
[Tailscale Serve](https://tailscale.com/docs/features/tailscale-serve).
PRODUCT_FEATURE_PLAN.md proposes the broader saved-chat, document-search and
model evaluation stages. All remain planned unless explicitly marked delivered.

## First local stage delivered - October 23

More > Local website starts an explicitly controlled loopback-only chat/Artifact
preview in the desktop process. It uses the same model lock, bounded persistent
web jobs, idempotency keys and temporary local sessions. This avoids separate
Python locks, but it is not a broker for other apps/processes. No remote identity,
MFA, HTTPS gateway, media endpoint or account creation is implemented. The
standard-library HTTP preview is not the production server. LOCAL_WEB_PORTAL.md
records 422 offline cases, five native suites, synthetic browser checks and a
real e2b HTTP smoke. Next is maintained authentication/transport and deployment
review, with the human scorecard still unfinished. No school reachability claimed.
