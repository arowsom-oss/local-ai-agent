# Local AI Agent with Code-Enforced Restrictions

A small Python 3.12 agent for Windows, using a local model through Ollama.
It reads approved websites, follows real links, searches simple GET forms, reads
attached text files from a sandbox, and does basic math. Permissions live in code.

## Browser tools

| Tool | What code allows |
|---|---|
| `browser_open(url)` | Open an approved HTTPS address |
| `browser_read()` | Return at most 4,000 characters, including numbered visible links and boxes |
| `browser_click(element)` | Look up a recorded link address and open it through the same checks |
| `browser_search(element, text)` | Build and open a URL for one named field inside a GET form |
| `propose_plan(goal, steps)` | Ask approval for 1 to 5 open/click steps |

The browser never types, clicks script-driven buttons, fills passwords, or runs
JavaScript chosen by the model. The element-listing JavaScript is fixed code that
only reads the DOM. Page JavaScript stays disabled.

## Approval tiers

| Tier | Actions | Approval |
|---|---|---|
| Low | Read the browser; do math | Logged, no popup |
| Medium | Follow a link; read a sandbox file; propose a plan | Approval required; a matching plan covers a link |
| High | Open/fetch a model-written URL; submit a search; approve a new website | Separate red dialog for every action; No is the default |
| Blocked | Download files, target passwords, run commands, control desktop apps | No executable tool is exposed |

A search on a new site needs **both** site approval and search approval. An
approved plan never covers a search or the exact-URL approval for an open/fetch.
Site approval permits a destination; it does not approve data in an address.
Every model-written URL needs its own approval, including paths, query names and
values, and encoded text. The popup shows the full exact URL; code binds execution
to that approved address. Approval must return literal `True`; errors deny. Enter, Escape and closing a red dialog deny
the action; Yes requires explicit selection. The terminal frontend uses its
existing text confirmation instead of a red window.

`download_file` is removed from the model schema and executable tool registry.
Requests for it are explicitly refused, even if the model invents the tool call.
The legacy `download.py` can remain on disk; the agent core does not import it.

## Search rules

The model supplies only an element number and search text. Code records the box's
name, its containing form's resolved action URL, and the form's method. A search
is refused unless the box was numbered, is a search/text box, has a name, belongs
to its containing form, and uses GET or an omitted method.

Text must be 1 to 100 printable characters, with no line breaks, `@`, or run of
7 or more digits. Unicode digits are checked too. All checks happen before a
popup. These rules reduce data leakage; they do not identify all private data.

`urlencode` builds the query. Only `{field_name: search_text}` is sent; existing
action queries, fragments and other fields are omitted. The approval dialog
shows the box label, exact search text and full URL. After approval, code opens
that exact URL without resolving the element again.

## Browser restrictions

- Chromium runs visibly, with a fresh non-persistent context per chat.
- Downloads are not accepted; service workers are blocked.
- The context is offline. Intercepted requests are fulfilled from HTTPX; the
  browser's normal context networking has no online fallback.
- Every intercepted HTTP request must be GET. Image, media, font, script,
  WebSocket and EventSource requests are blocked. WebSockets also have a
  separate blocking route installed before pages are created.
- Your existing `fetch.check_new_site` and `fetch.safe_ip` validate URLs and DNS.
  HTTPX connects directly to the checked IP, retaining Host and TLS SNI.
  Environment proxies are disabled for this fetch path.
- Each response is capped at 5,000,000 bytes while streaming. Compressed responses
  and attachments are refused. HTTPX uses 10-second operation timeouts plus
  elapsed-time checks. This is not a forcibly interruptible total deadline.
- Redirects are refused. No 3xx response is fulfilled into Chromium.
- Failed navigations dispose of the context before another navigation can run.
- One dedicated thread owns all Playwright objects. Other threads use queues
  with timeouts. `close_browser()` must succeed before New chat resets approvals.

The text-only `fetch_page` tool also streams at most 5,000,000 bytes, refuses
compressed responses/attachments/redirects, disables environment proxies, and
retains the checked IP with Host/SNI. Its displayed text limit remains 2,000.

Element numbers are not reused during a chat. Reading again invalidates old
numbers. Navigation clears the element map, including a same-URL reload. The map
also records the page URL and navigation version, so stale references fail
closed and ask for another `browser_read`.

Plans name links by their visible text, not numbers for pages that do not exist
yet. A planned click needs exactly one matching recorded label. Changes require
the existing plan-changed approval. Searches do not consume plan steps.

## Other existing features

- Sandbox file reads check the resolved path and have an 8,000-character limit.
- The person chooses attached files; the model has no file picker or upload tool.
- The Stop button checks its flag between model calls and tool actions.
- Chat summaries are labelled untrusted user-message data, never system messages.
- The JSON Lines audit log records approvals, refusals, results and tool risk.
  It stays outside the sandbox and is excluded from Git. It currently contains
  tool arguments, including search text: do not publish it.
- Every tool's actual arguments are checked in code, including rejecting extra
  parameters and booleans supplied as element numbers.

## Install the update

This folder is an update package, not a replacement for the whole project.

1. Close the agent window and keep a backup of the current files.
2. Copy `browser_tool.py`, `agent_core.py`, `chat_window.py`, and `fetch.py` into
   the existing project, beside `htmltext.py` and `attach.py`. Preserve any custom
   `ALLOWED_HOSTS`/`REGIONS` settings in your fetch file. Its URL and DNS validator
   functions are unchanged. Do not replace `identity.py`.
3. Install dependencies with `python -m pip install -r requirements.txt` and
   install the browser with `python -m playwright install chromium`.
4. Keep the existing Ollama models and launcher. Confirm the sandbox/audit paths
   in `agent_core.py` match the existing installation (`C:/dev/agent` by default).
5. Run `python chat_window.py`, or use the existing `start_chat.bat`.

No new paid API or cloud model is required. The fixed model allowlist is unchanged.

## Tests

Run without Python's `-O` option, because tests use plain asserts:

```text
python -B test_browser_search.py
python -B test_browser_network.py
python -B test_fetch_page.py
python -B test_browser_live.py
```

The search, network and fetch suites need only the standard library and fake
external modules. They have 62 offline tests. The live suite needs installed Playwright, Chromium
and HTTPX. It runs real visible Chromium against fake HTTPX responses, exercising
the real route handler and DOM extraction without needing an Internet site.

See `VALIDATION.md` for the actual checks run and remaining limitations.

## Known limits and next stages

- A live Wikipedia Dog article read passed. Its `dog` search returned a redirect
  and was correctly refused. Search sites must return their result directly;
  redirect support requires a separate design, not disabling the checks.
- Sites requiring JavaScript, POST, hidden form fields or authentication may not
  work. GET requests can have side effects on poorly designed sites; these rules
  cannot prove that every endpoint is semantically read-only.
- Chromium routing and offline emulation are not an OS network sandbox for all
  browser background activity. Strict process-wide egress isolation is separate.
- Account-link blocking uses the existing keyword checks; it is not a complete
  classifier of every login or payment endpoint.
- Stop cannot forcibly interrupt a Python worker thread already inside a
  blocking operation. A separate browser process is a future improvement.
- Longer-page reading, page search, request budgets, audit-log redaction and
  third-party-resource restrictions remain future enhancements.
- Desktop app control, model routing, image generation and larger models remain
  later roadmap stages. This update grants none of those powers.
