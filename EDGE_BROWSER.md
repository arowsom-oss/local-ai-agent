# Edge work profile and selected personal-tab handoff

October 21, 2026. Alexander chose a **separate Edge work profile for the AI**.
Clicks and typing are confined to the app-owned work browser. A tab in personal
Edge can be shared for reading or copying its address; it is not an action target.

## Start using the work browser

1. Restart Local Studio after updating this branch. Choose **Edge tab** in the
   sidebar, then **Start work Edge**. Review the No-default dialog.
2. The app opens Microsoft Edge using only `edge_work_profile/` inside the app
   folder. This is separate from your normal Edge profile. You can open a site
   manually there, then choose **Choose a work tab** in the app; or ask the AI
   to open an exact HTTPS address and approve it.
3. Try "Read my Edge work tab." Approve the read. The result has page text,
   regular text-field values and fresh numbered controls. Only visible,
   uncovered controls in the main frame receive numbers.
4. Ask for a numbered link/button, a text replacement or an up/down scroll.
   Every operation gets its own exact preview. A plan never approves Edge work.
   Read again afterward to observe the result; a dispatched action is not proof
   that a server-side task completed.
5. Stop, New chat or **Disconnect / close work Edge** revoke commands and close
   only the owned work browser. Profile cookies/site data stay on disk. No
   personal browser process is killed or attached to.

The work browser needs installed Microsoft Edge and the existing Playwright
runtime. No model weights, new Python packages, browser profile import, public
debugging port or extension are needed for work-profile interaction. It is a
separate browser data directory, not an OS sandbox or a VM. Do not treat it as an
anonymous identity; manually signing into a website creates a work-profile login.

## Use a page already open in personal Edge

This part has a one-time, **person-operated extension installation**:

1. In your normal Edge, open `edge://extensions`. Enable Developer mode, choose
   **Load unpacked**, and select `C:\dev\local-ai-agent\edge_extension`.
2. In Local Studio choose **Edge tab > Share a personal Edge tab (read/handoff)**.
   Review the dialog. A fresh pairing code is shown in its own window; keep it private.
3. Select the website tab in Edge and click the Local Studio extension icon.
   Enter the code in the connector window and choose **Share selected tab**.
   Keep that connector window open. It uses RAM only, without localStorage.
4. Ask the AI to read the shared personal tab (`edge_shared_read`), copy its
   address to the isolated read-only browser (`edge_copy_to_browser`), or open
   that address in the already-started work profile (`edge_open_shared`).

Each operation needs a separate app approval showing the full address. No
cookies, passwords, personal browser profile or login session are copied. The
work profile may therefore show a sign-in page. Personal Edge clicks/typing are
blocked both by the Python relay and extension panel. The extension requests
only activeTab/scripting and loopback access, not all-websites, history, cookies,
downloads or debugger access. Cross-origin navigation requires sharing again.

Microsoft documents activeTab/site permissions here:
https://learn.microsoft.com/microsoft-edge/extensions-chromium/developer-guide/declare-permissions

The local relay binds only literal 127.0.0.1 on an ephemeral port, accepts JSON
POSTs with bounded bodies and a random RAM-only bearer secret, checks the Host
and extension Origin, then binds to one extension origin/tab. Polling command
IDs, expiry, one-use results and a heartbeat keep late/disconnected replies from
granting access. Normal web origins cannot pair. The code is never a model tool
argument, transcript, audit entry or persistent setting. It is not remote access
from school, and it is not a multi-user authenticated web server.

## What the code enforces

- One long-lived owner thread runs sync Playwright for the work profile. Commands
  use a queue and deadlines. The model cannot supply a profile, PID, selector,
  coordinates, JavaScript, endpoint or approval ticket.
- Fresh numbered controls and pending tickets live in a fixed isolated JS world.
  Website JS cannot read/edit that map or substitute its own helper builtins.
  A snapshot of URL, page text and control metadata is rechecked immediately
  before a one-use, 30-second commit. Counters continue across document changes;
  a new session receives a distinct number range. Changed pages fail closed.
- Password/file/email and known credential/payment-code fields are excluded.
  Regular text replacements are 1-500 printable characters, without @ or a run
  of seven digits. These patterns do not recognize every possible secret.
- HTTP requests use `safe_ip` for checked public addresses, HTTPX connected to
  that IP, the original Host header and TLS SNI, no proxies and no auto redirects.
  Work cookies come only from the work context and response cookies return to
  it. The existing stateless browser/fetch tools are unchanged.
- GET is allowed. A successfully proposed, person-approved click/type commit
  opens a five-second POST window restricted to that page's origin. It is an
  origin/time permission, **not consent bound to each individual POST body**.
  Website effects remain unverified; a button label cannot establish its meaning.
  Other methods, cross-origin POSTs, multipart/binary uploads and bodies over
  256 KB are blocked. HTTP responses cap at 5 MB/10 seconds; requests/body budget
  is 250/20 MB per approved navigation or click/type. Reads do not renew it.
- Redirects, attachments, compressed responses, WebSockets and service workers
  are blocked. Downloads are not accepted; download events are cancelled and
  file chooser events select nothing. No model API can supply file paths/files.
  Unsolicited permissions are not granted and website JS dialogs are dismissed.
- Denials or errors pause the Edge workflow and discard queued actions. Stop
  revokes pending operations. An already-dispatched action cannot be rolled back,
  and an active synchronous DNS/HTTP/DOM call can take time to finish. A timed-out
  owner is not abandoned in favor of a concurrent browser on the same profile.

Playwright documents dedicated persistent contexts, Edge channel and profile
constraints here: https://playwright.dev/python/docs/api/class-browsertype#browser-type-launch-persistent-context

## Evidence and remaining checks

All 353 offline cases across nineteen suites pass, including twenty-three new
Edge cases. Production dispatch tests cover absent capabilities, strict args,
approval inside plans, denied batches, immutable approvals, one-use commits,
relay identity/transport, stale replies, Stop, source-only access, public-IP/Host/
SNI fetching, cookie forwarding, POST gating and response caps/refusals.

The real headed **Microsoft Edge** fixture uses a randomly named disposable
profile and fake HTTPS through production HTTPX routing. It tests two response
cookies, private isolated-world state, visible text values, approved typing and
buttons, independent DOM changes during approval, stale numbers after navigation,
download/attachment blocking, file chooser interception, scrolling, callers on
different threads, tab selection and owner cleanup. A real Chromium extension
fixture tests loopback pairing, reads, exact address handoff, changed-page refusal
and disconnect. Its fixture-only website permission substitutes for a human's
toolbar activeTab grant; it does **not** prove installation/toolbar consent in
your ordinary Edge. No personal tab, account, live Internet or model was used.

The native Tk fixture checks the new controls and full URL/text preview, with
Return returning No. These are automated fixtures, not your human acceptance run.
Early experiments retained failures involving missing user activation, a fixture
blocking its own packaged scripts, an offscreen-text assertion, download-event
assumptions and a failed-navigation race. The final behavior preserves a failed
tab for review and uses a fresh target on a later approved navigation.

Compatibility is deliberately limited: redirects/SSO flows, large media, complex
SPAs, cross-origin forms, WebSockets, shadow DOM, iframe controls, rich-text
editors, canvas and offscreen controls may not work. Background DOM changes can
invalidate approvals. Websites can run their own scripts and perform actions
within an approved POST window; server-side success and action meaning are not
verified. Chromium background traffic is not an OS-level network sandbox.
Manual Edge extension installation, toolbar sharing and a real chosen website
remain person checks. The main scorecard stays deferred and unchanged.

Run offline: `python -B test_edge_tools.py`. Native fixture:
`python -B test_edge_live.py`. The latter launches only owned test browsers and
removes only its verified randomly named fixture directories afterward.
