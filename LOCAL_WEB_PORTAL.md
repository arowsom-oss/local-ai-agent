# Local website preview: stage 1 of school access

October 23, 2026. Implemented locally, **not ready or deployed for school access**.

## Open it on this laptop

1. Restart Local Studio and choose **More > Local website**.
2. Choose **Start preview**, then **Open preview**. The desktop app gives a private
   access link with a temporary key in the fragment. Copy access link is available.
   Do not publish/share this key. It is not a school password or production account.
3. Chat with either existing allowed installed model. Create conversations, keep
   a reply as a document or inert code Artifact, preview it and download text.
4. **Sign out** revokes that browser session and clears visible/private page text.
   It does not cancel already accepted jobs; use a job's Cancel or desktop Stop.
5. **Stop website** cancels web jobs, revokes all preview sessions and closes the
   listener. Closing its control window keeps an already started website running.
   The app does not start any listener automatically. App exit stops the server.

The backend binds exactly 127.0.0.1:8765. No LAN bind, tunnel, public site, firewall
rule, Ollama exposure, account registration or cloud deployment was added. A
Chromebook cannot reach this address on the Acer. The responsive browser UI is
the first stage toward that experience, not a claim of remote access today.

## What it does

- Local web chat with queued/running/completed/failed/cancelled/interrupted states.
  A single worker has at most three waiting jobs plus its active request. One
  pending request per web conversation. A running job may be waiting for the GPU.
- Reconnect/reload finds persisted job IDs. A repeated request ID with the exact
  same chat/message/model returns its original job, never another inference.
  Reusing an ID with changed content refuses. An uncertain browser submission
  keeps its ID for a deliberate retry; there is no automatic resubmission.
- Web conversations and text/code Artifacts persist in a separate, gitignored
  portal_data/portal.sqlite3. No primary desktop chat database, generated file,
  sandbox, Documents folder or arbitrary local path is served or imported.
- Every model answer uses tools=[], think=False and the existing model allowlist,
  loopback Ollama client, shared 8192-token context and lifecycle manager. Older
  context is limited to recent complete pairs within a 6000-byte content budget;
  this is not unlimited conversation memory. Output is capped at 1024 tokens;
  malformed, empty, truncated or tool-call output fails without automatic retry.
- Model HTML/code is inert text through textContent, never innerHTML, eval or an
  iframe. The first-stage Artifact download is .txt, with authorization rechecked
  before fetching its bytes. Executable website previews and media are not added.

## Shared GPU use and cancellation

The website runs as a background server **inside the desktop Python process**.
Its model requests and desktop chat/media reuse the same model_router lock.
This intentionally avoids a second process with an unrelated Python lock.
Web, desktop Auto/manual, media-analysis and Sources Q&A requests pass their
Stop signal while waiting for the lock. Cancelled queued requests never start
inference. A late cancelled compaction preserves original desktop history.
Desktop Stop cancels web jobs too. A running Ollama request can still finish or
reach the existing client timeout; its late answer is discarded, but the shared
model slot stays held until the request returns. Completed work is not undone
by a late Cancel, and the API reports that distinction honestly.

This is not a system-wide GPU broker. Other Ollama clients, older app instances
or external generation tools do not join this lock. Moving the server into a
separate service requires a real shared broker/IPC protocol first. Image/video
requests, uploads and remote computer/browser control are absent from this MVP.

## Local preview access controls

The temporary launch key is generated per server start. JavaScript consumes its
URL fragment, removes it from the address/history entry and trades it for a
server-managed session cookie. Up to eight sessions, 30-minute absolute expiry,
HttpOnly and SameSite=Strict; sign-out revokes the session. Five failed local
sign-ins in 60 seconds trigger a temporary throttle. No password/passkey/MFA or
external identity is implemented. The loopback HTTP cookie does not have Secure;
that is another reason this must not be deployed as the remote service.

API reads, Artifacts, cancellations and mutations require a valid session.
Records are always looked up against the internally fixed preview owner; callers
cannot choose another owner or pass a filesystem path. State changes additionally
require exact same-origin JSON and a session CSRF token. Wrong Host/Origin,
cross-site Fetch Metadata and non-loopback peers refuse. Only four fixed public
assets are served. There is no CORS wildcard or static project/generated folder.
Prompt/secret/cookie access logs are disabled, and no browser localStorage is used.
Late asynchronous responses cannot restore old private views after sign-out.

These are local development controls, not a completed security review or an
owner identity system for the Internet. Python's http.server is intentionally
used only for this bounded loopback prototype; Python does not recommend it for
production. Before any off-laptop use, use a maintained server/authentication
stack, one provisioned owner with MFA, reviewed Secure cookies/CSRF and a reviewed
HTTPS gateway. Validate signed gateway tokens/issuer/audience/owner server-side;
do not trust a supplied email header. Do not forward this preview port publicly.

## Storage, load and privacy bounds

- 20 web conversations, 96 submitted jobs, 30 Artifacts. Stored message/answer/
  Artifact bytes are capped at 4 MB; a separate SQLite page/file ceiling applies.
  No automatic cleanup or original-file deletion is added. Reaching a limit
  refuses more work. Reviewed export/deletion/retention is needed before media.
- Messages: 1–4000 characters and at most 5000 UTF-8 bytes. Replies: at most
  32000 characters. Request bodies: at most 16000 bytes; strict known fields and
  duplicate JSON-key refusal. Fixed UUID-like IDs; SQL parameters and ordinary
  SQLite transactions. Link/reparse paths are refused for the store.
- Eight HTTP connection slots, three-second connection read timeout, bounded
  headers from the standard parser. Chunked transfer, duplicate critical headers,
  arbitrary methods and unknown action endpoints refuse.
- Web text is saved automatically once submitted and is **unencrypted local
  data**, unlike the desktop's explicit Save workflow. This preview has one
  local owner only. A local process running as the same Windows user may read
  these files/keys or change this code; it is not an OS isolation boundary.
- On restart, queued/running records become interrupted, with no silent replay.
  Desktop New chat does not erase independent web history or revoke a running
  website. Stopping/signing out does not delete saved web conversations.

## Evidence and limitations

422 cases across 25 offline suites pass. Eighteen portal cases cover fixed assets,
unauthorized/expired/logged-out access, owner isolation, CSRF/Host/Origin/peer
refusal, throttling, strict schemas, path/tool endpoint refusals, idempotency,
queue/chat/storage bounds, cancelled queued/running work, completed-cancel
truthfulness, context limits and inert markup. Actual shared-lock behavior is
tested while a simulated desktop media lease is held. Regression cases also
cover desktop Auto/manual and Sources cancellation while queued, plus Stop
during compaction preserving the original history. No real network/inference
is used in the offline suites.

Five affected native suites pass: portal/Tk/HTTP, Sources Q&A, saved chats,
popups and efficiency UI. Genuine loopback HTTP tests cover sign-in/cookies,
CSRF, chat/retry, Artifact reads, host refusal and sign-out revocation. Actual
desktop Start/Stop and Close/Escape/X controls pass in lean/full environments.

The in-app Chromium browser, using synthetic data and a fake model only, completed
a chat, kept/inspected an Artifact, reloaded to existing jobs, downloaded 188 exact
text bytes and signed out with messages, Artifact body and chat names cleared.
A literal script tag rendered as text and produced no script elements in those
panes. DOM layout checks fit 1280px and 390px viewports without horizontal overflow;
the browser's original viewport was restored. This is not a physical Chromebook
or school-network test. Full-page/overridden-viewport captures failed in the
preview tooling; a normal viewport screenshot succeeded and was inspected.

One real gemma4:e2b request through the genuine HTTP API returned exactly the
synthetic requested text in 9.719 seconds. Repeating the same request ID returned
the same job with one inference call total, tools empty and num_ctx 8192. This
is a small smoke test, not a throughput, broad security or quality benchmark.
No model download or real media generation was performed.

Current main scorecard: a new actual attempt on 526497f submitted the first exact
prompt and reached a New website permission popup; Alexander's input is pending.
No step is graded. The older prepared 58adaf fixture is unchanged. Tests above
do not replace the human scorecard, and all draft branches remain unmerged.

## Before school access

1. Review this draft and complete the existing scorecard; fix observed failures.
2. Select a maintained login/gateway approach with Alexander; configure one
   owner, MFA, HTTPS, transport/session validation and no authentication bypass.
3. Review deployment and test unauthenticated/revoked/guessed-ID requests through
   the real gateway. Keep computer control and direct Ollama access unavailable.
4. Test from a permitted second device; school/device policy may block access.
   Do not bypass that policy. The Acer must remain awake, online and serving.
5. Add media jobs only after reviewed disk retention, exact request previews and
   shared queue/resource admission checks. Persisted desktop/web synchronization
   also needs an explicit owner-bound import policy; it is not delivered here.

Primary references:
- https://docs.python.org/3.12/library/http.server.html
- https://docs.python.org/3.12/library/http.cookies.html
- https://developers.cloudflare.com/cloudflare-one/access-controls/applications/http-apps/
- https://developers.cloudflare.com/cloudflare-one/access-controls/applications/http-apps/authorization-cookie/validating-json/
