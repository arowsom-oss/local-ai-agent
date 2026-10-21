# Research from a topic

The earlier browser could search a numbered GET form only after someone opened
a suitable page. It could not discover sources from a topic. The new
`browser_web_search(query)` builds a fixed DuckDuckGo Lite URL in Python, opens
it through the existing pinned browser and returns up to 4000 characters of
untrusted text and recorded link numbers. No API key, package or model is added.

DuckDuckGo documents its non-JavaScript search interfaces here:
https://duckduckgo.com/duckduckgo-help-pages/features/non-javascript

## Model and approval flow

Ask, for example: "Research the atmosphere of Mars using NASA sources and give
one short fact with a source link. Find the source yourself; I do not have a link."

1. The model proposes `browser_web_search` with only `query`.
2. Code validates 1-100 printable characters, a nonblank topic, no @, no run of
   seven digits and no !bang shortcuts. Extra arguments, including a model URL
   or approval flag, are rejected before any popup.
3. An unapproved provider needs New website approval. Every search additionally
   needs its own exact query/provider/full URL approval, including inside a plan.
   No is the default. Search sends that approved text to an external provider;
   the pattern filters cannot recognize every possible secret.
4. Code opens exactly the approved URL; no second model-built address is used.
   Results include numbered links. The model picks `browser_click(element)`;
   the recorded destination retains normal site/action checks and approval.
5. The click result reports the full opened source URL. `browser_read` takes
   no arguments and reads the current page. Earlier result numbers are stale
   after navigation. The model is guided to answer from source text and cite
   the URL, rather than asking the person for an initial link.

The existing `browser_search(element, text)` remains the numbered-form tool.
Neither kind of search can be approved as a plan step. Persistent audit records
still redact query/URL/content values. The live UI log may show tool arguments.

## Network boundary

All browser loads still use the dedicated Playwright thread, JavaScript-off,
fresh offline context, blocked service workers and intercepted requests. Python
checks public DNS addresses for every request and connects to the pinned IP
with Host and TLS SNI preserving the hostname. Only GET, existing response/page
budgets and exact-page-host resources are allowed; redirects remain blocked.
Stop after search navigation is checked before automatically reading results.

Observed DuckDuckGo Lite results wrap destinations in
`https://duckduckgo.com/l/?uddg=...`. On the exact Lite results page only, code
decodes one recorded `uddg` value once. It rejects malformed, ambiguous, raw-IP,
non-HTTPS or credential-bearing targets. It does not request the redirect or
recursively unwrap it. The destination is still untrusted and checked again
before opening, including public-IP resolution at request time. Similar-looking
domains receive no special treatment. This parser depends on observed provider
markup, not a guaranteed search API contract.

## Verification and honest limits (October 20, 2026)

All 325 plain-assert offline cases across eighteen suites pass in the lean
Python 3.12 environment. Fourteen new cases cover the fixed URL/encoding,
pre-popup refusals, hostile arguments, search approvals inside plans, new-site
denial, exact URL immutability, wrapped destinations, stale numbers, resume
evidence, opened-source citation address, wrong read arguments and Stop.
The existing eight injection fixtures still pass. The native headed Chromium
fixture passes with fake HTTPS: search text, direct result decoding, numbered
source opening and IP/Host/SNI routing all run through real browser code.

A live public query from this laptop returned ten relevant NASA/search links
from Lite (HTTP 200, no content encoding). The HTML endpoint instead returned
HTTP 202 with a challenge; it is not used as an automatic fallback.

Live Ollama e2b trials exposed two failures retained locally: the first model
passed a URL to browser_read and answered from snippets after a test-fixture
site refusal; the second reused stale numbers and reached the seven-round
limit. No checks were relaxed. Specific tool guidance, stale-number reminders
and full opened source URLs were added. A later two-fact trial searched,
clicked, read NASA and replied, but one detailed claim was not independently
confirmed in the returned excerpt. Do not treat that as fully verified research.
A final one-fact trial followed the same search/click/read sequence and returned
"Mars has a very thin atmosphere" with the NASA source URL, supported by the
actual returned page text. These are smoke tests, not a relevance/accuracy score.

An Auto-mode one-fact probe also searched from the topic and returned a
page-supported NASA answer/URL. Auto chose e2b. It first tried to click the
numbered search box, was refused, then opened the recorded NASA address through
the normal exact new-site approval and read it. Recovery worked; this is not
evidence of flawless link selection or performance with the 12b model.

Approval callbacks in live probes were bounded fixtures permitting only the
synthetic public NASA search and named NASA destinations. They did not click or
approve real UI dialogs, and no private user query was sent. Hidden reasoning
was not retained. The separate main scorecard remains deferred and unchanged.

Search availability, CAPTCHA/rate limits and future markup are external
dependencies. The model can still choose a poor result or make unsupported
claims. Source text is truncated at 4000 characters, so long pages may omit the
needed section. Script-dependent sites, redirects and sign-ins remain limited.
Chromium routing/offline mode is not a complete OS-level network sandbox.

Local raw evidence is in `work/topic_search_live_first.json`,
`topic_search_live_second.json`, `topic_search_live_third.json`,
`topic_search_live_one_fact_e2b.json` and `topic_search_verified_tests/`.
The Auto result is retained in `work/topic_search_live_one_fact_auto.json`.
Those probes are not the human scorecard and are not merged-main measurements.

## Person-operated check

Restart the normal app after updating this branch and start a new chat. Use the
NASA prompt above without a URL. Review the new-provider and exact-search
dialogs, then the proposed source. Confirm that No sends no request for that
action, that searches need separate approval even on approved sites, and that
the answer cites a page actually opened/read. A CAPTCHA or a refused source is
a visible limitation, not permission to bypass safeguards or fabricate results.
