# Gate evidence and adversarial test results

Snapshot: application commit `4a02efc61d6f89fdb78792a83b94a18a9ce3733c`, October 23, 2026. This is a code-reading map and test report, not the student-owned threat model. No application source, Copy binding or `THREAT_MODEL.md` is changed by this work. Line links point at unchanged source files in this branch; `test_evidence/adversarial_2026_10_23/gates.json` also records exact source text.

**Result: 438 passing assertions/cases and one failing Copy regression across 27 offline suites (26 suites pass).** The runner exits nonzero. The regression is not skipped, xfailed, or inverted. One additional real Chromium adversarial case passes using only an owned loopback canary. The separate sensitivity run detects all 15 temporary in-memory gate removals; these are negative controls, not 15 additional product passes.

## Run it

Use Python 3.12 without `-O`, with the existing test dependencies. From the repository folder:

```powershell
python -B test_copy_last_answer.py
python -B test_feature_adversarial.py
python -B scripts/run_offline_tests.py --output test-results/adversarial-new-run
# Real installed Chromium required; local loopback socket, no Internet:
python -B test_feature_adversarial_live.py
# Separate negative controls; refuses to overwrite its report:
python -B scripts/check_adversarial_sensitivity.py --report test-results/sensitivity-new.json
```

The full offline runner activates its socket-audit tripwire. Each suite runs in a separate process and failures do not stop later suites. The copy regression executes the actual `poll`, `clean`, `copy_text`, and actual button command AST with fake clipboard/widgets; it does not import or launch the GUI. Expected UTF-8 bytes and actual clipboard bytes are printed in its AssertionError. The malicious text fixture is created as a real temporary TXT file and parsed through `_parse`/`read_selected`; no personal file, model or Internet is used.

## Known failure and test-harness corrections

`test_copy_last_answer_preserves_fenced_python_and_backticks_byte_for_byte` fails: `poll` derives `last_answer` using `clean`, which removes backticks and bold markers. The Copy button copies that altered value. The raw reply is preserved separately, so the test verifies the loss occurs on the Copy path. The student owns the fix. Existing scorecard results and student files are unchanged.

The first adversarial harness run had 14/16 passes. One failure tried to patch a nonexistent `core.download_file`; the other patched a freshly imported workspace module rather than the module globals retained by the existing core harness. The harness now traps actual dispatcher entry and patches the actual reset function globals. Neither refusal assertion was relaxed. Initial failure logs are retained alongside release evidence.

## What these tests do and do not establish

- The fake model deliberately returns a tool call after reading injection text. Q&A must reject it even though the model disobeyed. The tests also reject an invented quote under a real citation ID and a quote laundered from a different source.

- Saved chat titles containing traversal syntax are allowed as inert SQL text; they are not paths. Numeric selectors and ZIP member paths must refuse. A real save/load/reopen is exercised in both plain and ZIP storage, with prior workspace permission/tickets, host approvals and stale Artifact IDs seeded before reopening. An adversarial next model call still needs fresh site approval.

- ZIP probes include the real 96 MB input boundary, forged over-limit central-directory expansion metadata that must refuse before opening a member, and a lying decompressor fixture that must use a bounded read. They do not extract any member to disk.

- HTML reduction and browser restrictions are tested separately. Raw hostile HTML bypasses reduction in real Chromium; scripts cannot change the green pixel canary, resource attempts cannot reach the owned server, and a forced second main-frame navigation is blocked. Offline route/option assertions prevent other defenses masking a missing individual gate.

- These are deterministic code-boundary tests, not a claim that a real model always ignores injection or that a valid quote proves a claim is true. A model can still write misleading text grounded in malicious reference text. The quote checker normalizes whitespace; it is not byte-for-byte quotation or semantic entailment validation. No authentication deployment, school network, full browser compatibility, OS sandbox or exhaustive repository audit is established.

- This pass adds focused tests for Q&A, saved chats/ZIP and HTML preview. The portal table below maps the newest website feature too; its existing 18-case suite was rerun, with no new portal implementation or deployment. Quota/worker rows beyond the focused attacks are mapped for reading, not claimed as newly adversarially tested here.

## Selected-document Q&A

Focused new tests: first three cases in `test_feature_adversarial.py`. Existing extraction/budget tests: `test_document_qa.py`.

| Limit / boundary | Exact enforcing function and line |
|---|---|
| Only absolute local PDF/TXT/MD selections; no UNC or alternate-data-stream names | `read_selected` — [document_sources.py:39](document_sources.py#L39) |
| Refuse network drive types on Windows | `read_selected` — [document_sources.py:45](document_sources.py#L45) |
| Refuse symlink/reparse paths, including ancestors | `read_selected` — [document_sources.py:48](document_sources.py#L48) |
| Regular file, 1–8,000,000 bytes | `read_selected` — [document_sources.py:51](document_sources.py#L51) |
| Bounded read and before/open/after identity-size-time comparison | `read_selected` — [document_sources.py:56](document_sources.py#L56) |
| PDF signature and strict parser | `parse_pdf` — [document_sources.py:66](document_sources.py#L66) |
| Encrypted PDFs refuse | `parse_pdf` — [document_sources.py:67](document_sources.py#L67) |
| 1–100 physical PDF pages | `parse_pdf` — [document_sources.py:68](document_sources.py#L68) |
| 20,000 characters/page; 200,000 extracted total | `parse_pdf` — [document_sources.py:73](document_sources.py#L73) |
| No text / scanned-only PDF refuses | `parse_pdf` — [document_sources.py:75](document_sources.py#L75) |
| TXT/MD strict UTF-8; nonempty and at most 200,000 characters | `_parse` — [document_sources.py:86](document_sources.py#L86) |
| Parser worker 768 MiB committed-memory bound | `import_source` — [document_sources.py:98](document_sources.py#L98) |
| Parser receive deadline 20 seconds and Stop | `import_source` — [document_sources.py:99](document_sources.py#L99) |
| Worker result exact schema, name ≤120, digest/tuple/page and character validation | `import_source` — [document_sources.py:103](document_sources.py#L103) |
| Recheck worker result content/type/digest/page totals before Source creation | `import_source` — [document_sources.py:111](document_sources.py#L111) |
| Always stop parser worker | `import_source` — [document_sources.py:115](document_sources.py#L115) |
| Fresh monotonically numbered source, no duplicate snapshot digest | `Collection.add` — [document_qa.py:43](document_qa.py#L43) |
| At most five sources and 500,000 collection characters | `Collection.add` — [document_qa.py:45](document_qa.py#L45) |
| Question 1–500 chars, ≤1000 UTF-8 bytes, supported controls | `question_text` — [document_qa.py:62](document_qa.py#L62) |
| Repeat collection/unique-number checks at retrieval | `retrieve` — [document_qa.py:72](document_qa.py#L72) |
| At most 6000 prompt bytes | `retrieve` — [document_qa.py:95](document_qa.py#L95) |
| At most four excerpts | `retrieve` — [document_qa.py:98](document_qa.py#L98) |
| Code-generated excerpt IDs/text in user data, no filename/path/metadata | `prompt` — [document_qa.py:105](document_qa.py#L105) |
| Missing retrieval evidence returns fixed abstention without inference | `ask` — [document_qa.py:152](document_qa.py#L152) |
| Installed model allowlist only | `ask` — [document_qa.py:150](document_qa.py#L150) |
| No tools; no thinking; context 8192; output ≤1000 tokens requested | `ask` — [document_qa.py:153](document_qa.py#L153) |
| Reject model tool calls independently of supplied tool menu | `ask` — [document_qa.py:157](document_qa.py#L157) |
| Stop before request and discard late results | `ask` — [document_qa.py:155](document_qa.py#L155) |
| Response ≤12000 chars; parse JSON | `validate_answer` — [document_qa.py:121](document_qa.py#L121) |
| Exact outer/claim schemas and boolean answerable | `validate_answer` — [document_qa.py:124](document_qa.py#L124) |
| 1–5 supported claims, no claims for abstention | `validate_answer` — [document_qa.py:130](document_qa.py#L130) |
| Claim ≤600 chars, quote 12–400, printable strings, real citation ID | `validate_answer` — [document_qa.py:137](document_qa.py#L137) |
| Normalized quote must belong to THAT cited excerpt | `validate_answer` — [document_qa.py:140](document_qa.py#L140) |

## Saved chats and Projects

New cases exercise inert traversal titles, numeric selectors, authority schemas and the actual reopen path. Existing storage/version cases: `test_chat_library.py`.

| Limit / boundary | Exact enforcing function and line |
|---|---|
| Titles 1–80 printable chars; names stay metadata | `title_text` — [chat_library.py:27](chat_library.py#L27) |
| Positive int IDs, excluding bool/path strings | `identifier` — [chat_library.py:33](chat_library.py#L33) |
| At most 400 explicit text messages | `transcript_text` — [chat_library.py:40](chat_library.py#L40) |
| Exact role/content keys; only user/assistant, no system/tool/call state | `transcript_text` — [chat_library.py:45](chat_library.py#L45) |
| Unsupported controls refuse; transcript ≤1,000,000 UTF-8 JSON bytes | `transcript_text` — [chat_library.py:52](chat_library.py#L52) |
| At most 20 Artifacts, 12 versions, exact kind/payload schemas | `decode_artifacts` — [chat_library.py:59](chat_library.py#L59) |
| Saved text uses bounded Store; media single version, base64 ≤20 MB decoded | `decode_artifacts` — [chat_library.py:76](chat_library.py#L76) |
| Snapshot ≤96,000,000 UTF-8 bytes | `snapshot` — [chat_library.py:96](chat_library.py#L96) |
| Reopen exact schema=1: no permission/plan/host fields | `decode_snapshot` — [chat_library.py:105](chat_library.py#L105) |
| Project notes ≤2000 chars; restored model archive tail ≤4000 chars | `restored_context` — [chat_library.py:117](chat_library.py#L117) |
| Restored history is one user reference entry, no executable tool/system protocol | `restored_context` — [chat_library.py:118](chat_library.py#L118) |
| Fixed library.sqlite3 path, not title-derived | `Library.connection` — [chat_library.py:134](chat_library.py#L134) |
| Library root/database/journal links/reparse paths refuse | `Library.connection` — [chat_library.py:138](chat_library.py#L138) |
| Database file ≤280 MB; SQLite busy timeout 2 s; max 65536 pages | `Library.connection` — [chat_library.py:147](chat_library.py#L147) |
| Project notes validation ≤2000 and printable/newline/tab | `Library.notes` — [chat_library.py:177](chat_library.py#L177) |
| At most 20 Projects | `Library.save_project` — [chat_library.py:186](chat_library.py#L186) |
| Title query ≤100 chars; parameterized literal search, limit 100 rows | `Library.list_chats` — [chat_library.py:204](chat_library.py#L204) |
| At most 100 saved chats | `Library.save` — [chat_library.py:219](chat_library.py#L219) |
| Update requires matching saved version | `Library.save` — [chat_library.py:223](chat_library.py#L223) |
| Library retained payload ≤256,000,000 bytes | `Library.save` — [chat_library.py:225](chat_library.py#L225) |
| ZIP decode AND snapshot validation before exposing a loaded chat | `Library.load` — [chat_library.py:242](chat_library.py#L242) |
| Delete requires matching numeric ID/version | `Library.delete_chat` — [chat_library.py:249](chat_library.py#L249) |
| Reopen validates before reset, then clears previous session | `open_saved_chat` — [chat_window.py:953](chat_window.py#L953) |
| Close Edge/browser/desktop/notepad/workers before new context | `clear_chat_state` — [chat_window.py:908](chat_window.py#L908) |
| Clear old messages and Artifacts; revoke old site/workspace approvals | `clear_chat_state` — [chat_window.py:927](chat_window.py#L927) |
| Actual host approval reset | `forget_sites` — [agent_core.py:393](agent_core.py#L393) |
| Workspace revoke invalidates pending tickets and observations | `Workspace.revoke` — [workspace_documents.py:78](workspace_documents.py#L78) |
| Restored Artifacts get fresh IDs | `Store.replace_saved` — [artifacts.py:73](artifacts.py#L73) |
| Fresh new-site popup still required after reopen | `_run_turn_impl` — [agent_core.py:883](agent_core.py#L883) |
| Approved plan is a local new-turn variable, not deserialized history | `_run_turn_impl` — [agent_core.py:548](agent_core.py#L548) |

## Automatic ZIP archives

New cases cover bad member names, oversized input/declared expansion, bounded inflation and forged archived authority. Existing scheduler/rollback cases: `test_chat_archives.py`.

| Limit / boundary | Exact enforcing function and line |
|---|---|
| Plain payload / ZIP input ≤96,000,000 bytes | `unpack` — [chat_archives.py:15](chat_archives.py#L15) |
| Exactly one member | `unpack` — [chat_archives.py:20](chat_archives.py#L20) |
| Only exact chat.json; no paths, directories, encryption; DEFLATE only; declared size 1–96 MB | `unpack` — [chat_archives.py:22](chat_archives.py#L22) |
| Bounded inflate reads only MAX_BYTES+1 | `unpack` — [chat_archives.py:26](chat_archives.py#L26) |
| Actual length must match metadata and remain ≤96 MB | `unpack` — [chat_archives.py:27](chat_archives.py#L27) |
| CRC/decompression/UTF-8 failures refuse | `unpack` — [chat_archives.py:30](chat_archives.py#L30) |
| Packing checks Stop/deadline every 262144-byte chunk; deadline 20 s | `pack` — [chat_archives.py:42](chat_archives.py#L42) |
| Byte-for-byte verification before replacement | `pack` — [chat_archives.py:46](chat_archives.py#L46) |
| Only bool archive setting accepted; disabled means no archive work | `Library.set_archive_enabled` — [chat_library.py:259](chat_library.py#L259) |
| Validate exclusion IDs and finite positive clock | `Library.archive_unused` — [chat_library.py:269](chat_library.py#L269) |
| Seven-day updated/last-use threshold; one-day retry backoff; query ≤8 | `Library.archive_unused` — [chat_library.py:279](chat_library.py#L279) |
| Never archive current/excluded chat; ≤3 processed per pass | `Library.archive_unused` — [chat_library.py:286](chat_library.py#L286) |
| Validate full snapshot before packing | `Library.archive_unused` — [chat_library.py:290](chat_library.py#L290) |
| Require ≥4096 bytes AND ≥5 percent payload saving | `Library.archive_unused` — [chat_library.py:294](chat_library.py#L294) |
| Rollback whole uncommitted archive batch on Stop/error | `Library.archive_unused` — [chat_library.py:303](chat_library.py#L303) |
| VACUUM only after commit and enough temporary free disk | `Library.archive_unused` — [chat_library.py:312](chat_library.py#L312) |
| VACUUM progress cancellation/deadline 10 s | `Library.archive_unused` — [chat_library.py:316](chat_library.py#L316) |
| Maintenance skips busy/stopped/active/absent-library, checks hourly after 5 s startup | `start_maintenance.tick` — [chat_archive_service.py:28](chat_archive_service.py#L28) |

## HTML/CSS pixel preview

New cases cover reduction, independent options/CSP, hostile routes, navigation and real Chromium canaries. Existing worker/pixel/locking cases: `test_artifact_web_preview.py`.

| Limit / boundary | Exact enforcing function and line |
|---|---|
| Only recognized HTML/CSS, source 1–32000 chars | `html_source` — [artifact_web_preview.py:28](artifact_web_preview.py#L28) |
| At most 2500 start elements | `_StaticHTML.handle_starttag` — [artifact_web_preview.py:48](artifact_web_preview.py#L48) |
| Drop script/frame/active subtrees | `_StaticHTML.handle_starttag` — [artifact_web_preview.py:52](artifact_web_preview.py#L52) |
| Tag and attribute allowlists; no href/src/action/on* targets | `_StaticHTML.handle_starttag` — [artifact_web_preview.py:59](artifact_web_preview.py#L59) |
| Attribute quote escaping and restricted input/button types | `_StaticHTML.handle_starttag` — [artifact_web_preview.py:60](artifact_web_preview.py#L60) |
| Chromium sandbox plus dead local proxy/background flags | `render_document` — [artifact_web_preview.py:107](artifact_web_preview.py#L107) |
| JavaScript OFF, offline, no downloads/permissions, service workers blocked, 800x1000 viewport | `render_document` — [artifact_web_preview.py:112](artifact_web_preview.py#L112) |
| Only first synthetic GET main-frame navigation may be fulfilled; every other route aborts | `render_document.intercept` — [artifact_web_preview.py:118](artifact_web_preview.py#L118) |
| Deny script/connect/frame/image/media/base/form via sandbox CSP | `render_document.intercept` — [artifact_web_preview.py:122](artifact_web_preview.py#L122) |
| Close WebSockets, dialogs, downloads, file chooser and extra pages | `render_document` — [artifact_web_preview.py:128](artifact_web_preview.py#L128) |
| 5 s navigation; URL and single-page postcondition | `render_document` — [artifact_web_preview.py:134](artifact_web_preview.py#L134) |
| 5 s screenshot; PNG 1–8 MB; fixed viewport, no full-page expansion | `render_document` — [artifact_web_preview.py:138](artifact_web_preview.py#L138) |
| Always close browser | `render_document` — [artifact_web_preview.py:142](artifact_web_preview.py#L142) |
| Serialize previews, acquire deadline 5 s, Stop checked | `prepare_web_preview` — [artifact_web_preview.py:158](artifact_web_preview.py#L158) |
| Renderer process tree 1536 MiB, receive deadline 20 s | `prepare_web_preview` — [artifact_web_preview.py:165](artifact_web_preview.py#L165) |
| Require exact preview dimensions and stop worker/release lock | `prepare_web_preview` — [artifact_web_preview.py:171](artifact_web_preview.py#L171) |
| Worker cannot start target before Windows Job assignment | `Worker.__init__` — [process_guard.py:94](process_guard.py#L94) |
| Windows Job committed process/job memory limits; kill descendants on close | `Job.__init__` — [process_guard.py:44](process_guard.py#L44) |
| Worker receive enforces monotonic deadline and Stop | `Worker.receive` — [process_guard.py:104](process_guard.py#L104) |

## Newest local website preview (scope map, existing tests rerun)

No new portal feature or public access. Existing 18 `test_portal.py` cases remain separate from the 16 new adversarial cases. This is development-only HTTP on this laptop, not production owner/MFA authentication.

| Limit / boundary | Exact enforcing function and line |
|---|---|
| Literal loopback bind 127.0.0.1, default port 8765 | `Portal.__init__` — [portal_server.py:224](portal_server.py#L224) |
| Fixed opaque 32-hex IDs; no caller-supplied paths | `identifier` — [portal_store.py:17](portal_store.py#L17) |
| Fixed store path, ancestor/link/reparse refusal, file ≤8 MB / SQLite ≤1950 pages | `Store.db` — [portal_store.py:50](portal_store.py#L50) |
| 20 web chats; title ≤80 chars | `Store.new_chat` — [portal_store.py:63](portal_store.py#L63) |
| 96 requests; one pending per chat; message ≤4000 chars / 5000 UTF-8 bytes | `Store.submit` — [portal_store.py:72](portal_store.py#L72) |
| Retry same request ID must match full payload digest | `Store.submit` — [portal_store.py:78](portal_store.py#L78) |
| Owner checked for chat access | `Store.require_chat` — [portal_store.py:68](portal_store.py#L68) |
| Owner checked for job access | `Store.job` — [portal_store.py:89](portal_store.py#L89) |
| Owner checked for Artifact access | `Store.artifact` — [portal_store.py:133](portal_store.py#L133) |
| Retained payload ≤4,000,000 bytes; transaction rollback on excess | `Store.quota` — [portal_store.py:58](portal_store.py#L58) |
| Reply ≤32000 chars; errors ≤200; completed states immutable | `Store.update` — [portal_store.py:100](portal_store.py#L100) |
| At most 30 web Artifacts; completed document/code only | `Store.keep` — [portal_store.py:127](portal_store.py#L127) |
| On startup unfinished owned jobs become interrupted, no replay | `Store.__init__` — [portal_store.py:35](portal_store.py#L35) |
| Only allowed model; three waiting queue slots | `Controller.submit` — [portal_server.py:44](portal_server.py#L44) |
| History ≤10 completed pairs and combined recent content ≤6000 bytes | `Controller.work` — [portal_server.py:81](portal_server.py#L81) |
| No web tools/thinking; context 8192; output request 1024 tokens; Stop passed to shared slot | `Controller.work` — [portal_server.py:84](portal_server.py#L84) |
| Reject tool calls/truncated/invalid text; no automatic retry | `Controller.work` — [portal_server.py:87](portal_server.py#L87) |
| Cancellation discards late model replies | `Controller.work` — [portal_server.py:85](portal_server.py#L85) |
| Expired/revoked sessions refuse | `API.session` — [portal_server.py:115](portal_server.py#L115) |
| Peer/Host/Origin/Fetch Metadata checks | `API.dispatch` — [portal_server.py:123](portal_server.py#L123) |
| Only GET/POST; API body ≤16000 bytes | `API.dispatch` — [portal_server.py:128](portal_server.py#L128) |
| Only four fixed public assets; no static project/generated directory | `API.dispatch` — [portal_server.py:131](portal_server.py#L131) |
| Duplicate JSON keys refuse | `unique_object` — [portal_server.py:26](portal_server.py#L26) |
| Every POST needs exact same-origin JSON | `API.dispatch` — [portal_server.py:138](portal_server.py#L138) |
| Five failed sign-ins per 60 s; constant-time temporary-key comparison | `API.dispatch` — [portal_server.py:145](portal_server.py#L145) |
| At most 8 sessions, absolute 30-minute expiry, HttpOnly/SameSite Strict cookie | `API.dispatch` — [portal_server.py:149](portal_server.py#L149) |
| Authenticated mutations need CSRF token | `API.dispatch` — [portal_server.py:155](portal_server.py#L155) |
| Exact endpoint schemas; no remote browser/shell/tool endpoint | `API.dispatch` — [portal_server.py:170](portal_server.py#L170) |
| Sign-out revokes server session | `API.dispatch` — [portal_server.py:176](portal_server.py#L176) |
| Eight HTTP slots/backlog and three-second connection timeout | `LocalServer.__init__` — [portal_server.py:189](portal_server.py#L189) |
| Reject duplicate critical headers/chunked transfer and oversized declared body | `Handler.handle_request` — [portal_server.py:207](portal_server.py#L207) |
| Rendered replies/Artifacts use inert textContent, no execution | `el` — [portal_web/app.js:24](portal_web/app.js#L24) |
| Async render response generation guards after logout; clears private DOM | `signedOut` — [portal_web/app.js:6](portal_web/app.js#L6) |
| Authorized Artifact refetch before inert .txt download | `download handler` — [portal_web/app.js:77](portal_web/app.js#L77) |
| Shared process model slot checks Stop while queued | `inference_slot` — [model_router.py:72](model_router.py#L72) |

## Copy regression: read these three locations

| Raw reply is stored, but displayed/copied last_answer is cleaned (known failing path) | `poll` — [chat_window.py:1221](chat_window.py#L1221) |
| clean removes backticks and bold markers (student-owned fix) | `clean` — [chat_window.py:346](chat_window.py#L346) |
| Copy button uses altered last_answer (unchanged) | `build_window` — [chat_window.py:1494](chat_window.py#L1494) |

## Evidence files

See [release summary](test_evidence/adversarial_2026_10_23/summary.json), [failing Copy traceback](test_evidence/adversarial_2026_10_23/test_copy_last_answer.py.log), [new attack cases](test_evidence/adversarial_2026_10_23/test_feature_adversarial.py.log), [Chromium result](test_evidence/adversarial_2026_10_23/chromium.log), and [15 sensitivity results](test_evidence/adversarial_2026_10_23/sensitivity.json). Initial harness failures are retained in `initial_harness.log`. No model weights, personal chat databases, or actual confidential data are fixtures.

The CI workflow should be red for the same Copy regression until the student fixes it. Do not merge or delete/skip/invert that test to restore green. A passing attack test only covers its exercised boundary; unmapped attacks and deployment review remain separate work.
