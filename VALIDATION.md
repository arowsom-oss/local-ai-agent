# Validation

Checked on Windows with Python 3.12.10, Playwright 1.64.0, HTTPX 0.28.1 and
Ollama's Python package 0.6.3. The existing installed Chromium was used.

## Passed

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

The original files in Downloads and the working `C:/dev/agent` installation were
left unchanged. The GitHub update is proposed separately for review.
