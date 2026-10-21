# Private remote chat and media: planned next stage

Status: roadmap recorded 2026-10-19, not an implemented or deployed web service.
The current change fixes local generated-media delivery to Artifacts. It opens
no listening socket, creates no account and changes no firewall/router setting.

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
   inert text. Reconnect to job IDs after a dropped connection rather than
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
The current local app and this media fix have not passed those future gates.

## Design references

The authentication and session requirements above draw on OWASP guidance:
[Authentication](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html)
and [Session management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html).
For the private-network option, Tailscale documents
[Serve](https://tailscale.com/docs/features/tailscale-serve) as a way to share a
local service within a tailnet. This is an option to evaluate, not an installed
dependency or a selected deployment.
