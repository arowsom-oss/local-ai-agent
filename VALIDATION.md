# Validation

Checked on Windows with Python 3.12.10, Playwright 1.64.0, HTTPX 0.28.1 and
Ollama's Python package 0.6.3. The existing installed Chromium was used.

## Current vision and model-routing checks

- 95 offline plain-assert tests passed: the prior 72 plus 23 model/vision tests.
  The new suite needs Pillow but uses fake inference, networking and capture.
- Cases cover fixed local endpoint despite OLLAMA_HOST/proxies, model allowlist,
  malformed/extra-key routing output, missing models, unload ordering/failure,
  serialized caller threads, vision capability checks, exact-URL consent after
  auto routing, image dimensions/metadata stripping, invalid/oversize/animated
  image refusal, stop behavior, no image-tool execution, no pixel history/audit,
  capture consent and No-default preview behavior.
- Real Windows/Tk fixture passed: new controls visible, synthetic image displayed,
  No focused and visible, Enter/Escape denied, explicit Use approved, Clear removed
  the pending image. No actual desktop capture was performed.
- Live local Ollama: two classifier examples selected expected roles; synthetic
  vision read TEST SCREEN and STATUS: READY; switching to 12b returned 42 for
  17 + 25; explicit unloading left no models in Ollama ps. Full core auto-image
  flow also read both labels, retained text-only history, and unloaded cleanly.
  See MODEL_ROUTING.md for individual timings and their limits.
- Real headed Chromium fixture passed again with mocked HTTPX; existing request
  limits, third-party rejection, redirects and separate caller threads passed.
- All Python files parse; git diff --check passes. No model downloads, no changes
  to server configuration or original installation, and no real screenshots used.

This stage is screenshot observation and constrained model selection, not desktop
control or real-time video. Actual screen capture is tested using a fake provider;
we did not capture the person's desktop as a test. The idle-60-second API setting
was tested in fakes; wall-clock idle expiration was not separately timed. Explicit
unload was verified against the real server. Routing quality and public website
compatibility were not benchmarked, and text can hallucinate or copy sensitive
information from an image.

## Previous page containment checks

- 72 offline plain-assert tests passed: 38 core/search/approval, 24 browser-network
  and 10 direct-fetch tests.
- New network cases cover no page scope, approved/session third-party and sibling
  subdomain refusal before DNS, allowed same-host CSS/frames with IP pinning,
  exact default 100-request exhaustion before DNS/HTTP, blocked requests and
  WebSockets sharing the count, aggregate byte limits across frames/responses,
  declared/streamed overflow, failed-response byte accounting, navigation/read
  preserving budgets, explicit open renewal, and 4,000-character read output.
- Real headed Chromium with fake HTTPX passed the existing integration suite plus
  same-host stylesheet/frame loading, denial of another independently approved
  host before DNS, and an over-budget page of stylesheets. A 4-request fixture
  admitted exactly the document plus 3 stylesheets; reading did not renew it,
  and an explicit new open did. Default 100 is exercised in the offline suite.
- All Python files parse; git diff --check passes. No new packages required.

The defaults are 100 intercepted requests and 10,000,000 streamed body bytes per
explicit open. Per-response 5,000,000 bytes remains. One body chunk may cross the
aggregate limit on arrival and is rejected without buffering or fulfillment.
These limits do not cover headers/TLS overhead, total chat traffic, Chromium
process memory, or background browser egress. No public-site compatibility or
latency benchmark was performed for this step. Older audit reports describe
the previous revision's resource policy, which this step intentionally tightens.

## Previous consent hardening checks

- 62 offline tests passed: 38 core/search/approval tests, 14 browser-network
  tests, and 10 direct-fetch tests. Fakes require no Internet.
- Regression cases cover raw URLs containing query/path/encoded data, mandatory
  per-URL approval during plans and after site approval, callback exceptions,
  literal-True approval, approved-URL mutation, and malformed URL refusal.
- Fetch tests cover streaming limits, exact 5 MB boundary, Host/SNI/IP pinning,
  proxy disabling, redirects, compression, attachments, errors and DNS rejection.
- Real headed Chromium with fake HTTPX responses passed again after the changes.
- Syntax parsing and diff whitespace checks passed.

The scoped security review found the privacy approval bypass in both URL tools
and a pre-existing unbounded response buffer in fetch_page. Both are addressed
in this package. Review does not prove that no further vulnerabilities exist.

## Earlier integration checks

- 30 plain-assert offline search, approval, plan, argument-validation and
  stale-element tests in `test_browser_search.py`.
- 14 plain-assert offline interception, DNS rejection, IP/Host/SNI pinning,
  resource blocking, size-limit, error and worker-timeout tests in
  `test_browser_network.py`.
- Real headed Chromium integration with fake HTTPX responses: fixed DOM
  extraction with page JavaScript off; visible form/link enumeration; password
  and hidden-element exclusion; GET search URL construction; POST and nameless
  form refusal; stale-number refusal; blocked redirects; and commands from
  separate caller threads. The context was offline throughout.
- Real Windows/Tk dialog check with Computer Use: red header and full search
  details visible, buttons visible at the current display scaling, No focused,
  Enter returned False, explicit Yes click returned True, Escape returned False.
  This was a local dialog fixture; no search was submitted by those clicks.
- Live Internet check using the existing fetch policy: the Wikipedia Dog article
  opened and readable article text was returned. Its search box resolved to
  `https://en.wikipedia.org/w/index.php?search=dog`.
- Live Ollama smoke check using the existing `gemma4:e2b`: the updated core
  executed `add(a=17, b=25)`, logged it as low risk, and returned 42.

## Expected refusal found during live testing

The Wikipedia `dog` search returned a redirect. It was blocked and returned:

`Error: Redirects are blocked; no redirected request was sent.`

The full Wikipedia search workflow is therefore NOT a passing acceptance test
under the existing redirect policy. Direct-result GET search passed in the real
Chromium integration fixture. No exception to redirect checks was added.

## Problems found and fixed while testing

- Chromium could still be navigating to its error page after an aborted
  redirect, interrupting the next navigation. A failed navigation now disposes
  of the context, so the next open starts cleanly.
- At the current display scaling, the approval text could consume space meant
  for the buttons. The dialog now reserves button space before allocating the
  scrolling text area and is centered within the available screen dimensions.

## Not established by these tests

- Full browser workflows chosen by an actual Ollama model were not tested.
  Browser enforcement was exercised with scripted model replies; the actual
  model smoke check covered the math tool and core/schema integration only.
- Compatibility with every public website is not established.
- No claim of OS-level network isolation or a hard interruptible DNS deadline.
- The full existing attach/compaction application was not exhaustively retested.

The earlier Internet, Ollama and Windows dialog results above apply to the
previous integration build; those external checks were not repeated for this
hardening patch. The new exact-URL dialog content is checked with a fake widget
harness; its shared No-default dialog implementation is unchanged.

The original files in Downloads and the working `C:/dev/agent` installation were
left unchanged. The GitHub update is proposed separately for review.
