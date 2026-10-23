# Local Studio project record and development plan

A safe local AI assistant for Alexander's Windows laptop

Running record updated October 22, 2026. Earlier measurements remain labeled by milestone; later chapters record subsequent changes and failures.

Current handoff: saved chats/Projects now support verified automatic ZIP storage after seven days unused, transparent reopening, visible controls and actual disk-savings reports. AUTO_ARCHIVE.md explains the scope, migration grace and 388-offline/3-native evidence for Claude. Only saved snapshots are compressed; personal folders, original media and model weights remain untouched. Selected-document Q&A is the next proposed stage. No new model, private portal or human scorecard result is claimed.

## Purpose and current position

The goal is an assistant that helps with real computer tasks, understands selected images and media, and creates useful work on this laptop. Python decides what is permitted. The local model proposes requests; its promises, instructions and tool schemas never grant permission.

The project now has a chat and Artifacts interface, a guarded text browser, local model routing, selected-media analysis, experimental local generation, an owned practice application, a scratch Notepad adapter, and an approved folder for saved plain-text documents. It has not reached general control of all Windows applications.

Saved Documents makes drafts useful beyond a disposable chat. A person can approve saving a document Artifact, reopen it later, and save a revised version while keeping earlier files. Saving uses a dedicated filesystem adapter. It does not give Notepad a Save command or grant access to other files.

## Main design decisions

- Keep authority in code. Validate actual tool names and arguments, reject extra parameters, and require literal True from approval callbacks.
- Expand through narrow capabilities. Browser, practice app, scratch editor and document folder each have separate rules.
- Resolve targets before approval. Show the exact address, text, target or output rather than approving a vague model intention.
- Observe after actions. Compare actual results with approved values, refuse stale state and avoid blind mutation retries.
- Keep local models that fit the working laptop. The larger offloading experiment did not meet its resource gate under the tested workload.

## Scope of this record

This document explains completed features, design rationale, tests, experiments and future ideas. Performance figures describe individual development runs, not guarantees. Future ideas are proposals, not completed features. Technical terms are included so they can be looked up.

The original Downloads files and C:/dev/agent installation were left unchanged. Earlier chapters describe work on the original development branch and draft pull request 1. That work has since been merged by a collaborator. The October 19 storage handoff records the current primary installation and shared review path.

<!-- PAGE -->
# Browser and network boundaries

## Read only browser

The browser uses Playwright's synchronous API with visible Chromium, JavaScript disabled, and a fresh nonpersistent context for each chat. Downloads are disabled and service workers blocked. There is no saved browser profile or login reuse. The model has no generic typing, form-filling, JavaScript-execution or arbitrary browser-click capability.

Thread affinity means Playwright objects must remain on the thread that created them. A dedicated owner thread receives queued commands and returns replies with timeouts, allowing chat turns to run on different threads. New chat closes the previous browser session.

Request interception gives trusted code each browser request before it can use the network. Routed resources use the application's HTTPX path and return through route.fulfill. The handler never calls route.continue_, which would let Chromium perform its own DNS lookup.

IP pinning connects to the checked IP from safe_ip. The Host header preserves the real hostname, and TLS SNI identifies that hostname during the encrypted handshake. This avoids validating one resolution and then connecting through another unverified lookup.

## Why safe_ip runs on every request

Hostname approval does not approve every address that name might resolve to later. DNS rebinding changes a name from a public address to an unsafe address. Each independent fetch resolves once, rejects the name if any answer is unsafe, and connects to the checked IP for that fetch. It never validates one lookup and connects using a second lookup.

A carefully bounded cache of checked addresses could be another design, but it is not the implemented policy. Rechecking costs DNS work; request and byte budgets bound the page workload.

## Current controls and approvals

Only GET requests qualify. Images, media, fonts, WebSockets and event streams are blocked. The approved page's hostname also bounds frames and subresources. Third-party resources are refused even when approved separately. Redirects are currently refused, so the implementation does not rely on a fulfilled redirect being intercepted again.

The network path rejects unsafe URLs and addresses, disables environmental proxies, refuses compressed/attachment responses, and applies response, request and page budgets. Browser text is bounded to 4,000 characters and marked as untrusted data.

Numbered links resolve to recorded addresses. Search constructs a URL using URL encoding for a named text/search input in a GET form; the browser never types. POST forms are refused because they submit data through a different method. Search text is 1 to 100 printable characters, with no line breaks, @ or runs of seven digits.

These search rules are limited data-exfiltration filters, not complete privacy detection. Data exfiltration means sending private information to another website. Model-written outbound addresses require exact-address consent; site permission alone is insufficient. Search always needs its own approval, including during a short browser plan.

<!-- PAGE -->
# Local models and the offloading experiment

## Routing and memory policy

The tested laptop has an Intel Core Ultra 9 275HX, an RTX 5070 Ti Laptop GPU with about 12 GB VRAM, and about 32 GB system RAM. Allowed local Ollama models are gemma4:e2b and gemma4:12b at the fixed loopback endpoint. A bounded English document-workflow hint prefers 12b; other text uses a tool-free classifier, with malformed output falling back to e2b. Manual choice remains available.

Calls are serialized. Switching unloads the previously managed model first; an unload failure blocks switching. A 60-second keep-alive and Free VRAM button reduce idle use. Two follow-up turns retain a reasoning selection to avoid repeated swapping. The manager does not evict other clients' models.

Selected images/video contact sheets use a fixed vision route with no action tools. Audio transcription is observation data. Model selection never changes permissions or app scope.

## Weight swapping

Arbitrarily dropping apparently irrelevant weights from a dense model is not supported here. Mixture-of-experts models are trained differently: they select experts during inference. A suitable backend may offload experts between storage, RAM and VRAM. That is a separate design from whole-model routing, with its own resource and latency costs.

A separate Strata checkout tested a reduced Coder IQ1_M candidate, not the full general-purpose model shown in the attached video. About 58.4 GB of checkpoint shards were downloaded and verified against pinned sizes and SHA256 values. The main agent's routing was unchanged.

## Criteria and measured result

Before inference, the candidate needed at least 3 GiB available system RAM, at least 10 generated tokens per second on fixed probes, a 20 percentage point improvement over the best measured harder-set baseline, warm response start within 10 seconds, and correct simulated tool arguments. Missing measurements could not count as passing.

The candidate loaded in 48.7 seconds and correctly answered a six-token readiness probe in 6.9 seconds. Available RAM then fell to 2.92 GiB. The watchdog stopped the owned server before the scored comparison completed. Sustained candidate speed, accuracy and tool reliability remain unmeasured. Six tokens do not establish throughput.

Keep the fitting models as the default under the tested desktop workload. This is not proof that the candidate cannot run after a clean boot or with other settings. About 65.7 GB of trial data remain locally for reproducibility; the owned server was stopped and its port released.

The small synthetic baseline tests have limits too. Thinking mode's output budget includes reasoning. A missing final answer within that budget is a failure of the configuration, not proof that a model cannot solve the task. The complete experiment report retains the criteria, prompts, measurements and caveats.

<!-- PAGE -->
# Windows control and scratch Notepad

## Owned practice application

The first desktop adapter controls an application created by this project, with disposable RAM-only state. Windows UI Automation provides semantic text and numbered controls. Code checks process, window and runtime identities. The model cannot choose an app, PID, window handle, coordinates or keyboard shortcut.

A proposed change becomes an exact before/after preview. An opaque one-use token binds approval to the observed state and expires after a fixed interval. Code rechecks state, performs the narrow action, and reads back the result. Practice Save stores its own RAM draft; Clear and one-level Undo remain inside that app.

Windows Job Objects contain owned worker lifecycles and memory use. Stop, F12 and global Ctrl+Alt+F9 terminate owned desktop/media/generation process trees. These controls are not a VM or least-privilege OS sandbox. Browser and Ollama requests can finish after Stop.

## First real application adapter

The Notepad adapter owns one new blank classic Notepad window. Existing editors and modern Notepad tabs are excluded. The installed executable is briefly created suspended under a debugging relationship, checked and assigned to its owned lifecycle, detached and resumed. Unsupported installations fail closed rather than falling back to another app.

The model can start, read and propose text replacement using the current recorded number. Text is bounded to 2,000 characters and UTF-16 code units. No open-file, save, menu, print, arbitrary-click, clipboard or shortcut tool exists.

Every edit needs its own exact approval, even during a browser plan. Code rechecks the target, then compares the complete normalized text after writing. A process-specific menu/dialog event permanently halts that session. Verification, identity or backend failures also require a new scratch session.

## Drafting and recovery

Reads and successful edits report revisions. Successful edits return the full verified text. The sidebar shows observed, awaiting approval, applying/verifying, verified or paused states. Only one Notepad step runs per model response; queued actions wait for its observation.

Denied, malformed or stale operations end the agent turn and revoke pending edit authority. After a person edits the draft, a later request must read it and propose a fresh change. A real-window fixture verified stale refusal and subsequent preservation of human text.

A local-model two-turn draft/revision test passed in 24.01 seconds with separate exact-edit approvals. Human-interference recovery used real-app and deterministic core fixtures; there was no measured model recovery run. UI Automation rechecks are not atomic against simultaneous edits. Stop and New chat discard this unsaved scratch window; personal work belongs in separate editor windows.

<!-- PAGE -->
# Saved documents and recovery copies

## New persistent workspace

Saved Documents connects document Artifacts to one fixed document_workspace folder beside the app. Folder reading needs permission for this chat. Every save presents its own complete before/after text and new filename, with No focused. New chat forgets permission and draft Artifacts; saved files remain.

The model lists numbered documents and reads saved text into an Artifact. It can request an exact Artifact save or a bounded append/unique-excerpt replacement using the latest read. The edit helper resolves revision bookkeeping in code. Every publication still needs exact approval. Paths, filenames, extensions and overwrite flags are not model parameters. Plain text is limited to 8,000 characters.

## Everyday workflow

- Ask for a document Artifact and request saving it as a new Document. Review folder permission and the exact save preview.
- To revise later, list Documents and read the latest saved version. The edit helper can append or replace one exact excerpt; the Artifact workflow remains available for broader rewrites. Inspect the complete preview before approving either path.
- Save new in Artifacts creates a separate document. Documents opens the saved list. Load version accepts 0 for latest or a saved history number.
- To recover, load an older version into Artifacts, optionally edit and Save edit, then select the saved document and Save Artifact here. Review the current before text and chosen after text. Recovery appends another latest version without erasing history.

## Why saving creates a new file

Each save uses a generated UUID/version .txt filename. Earlier files remain as recovery copies. The agent never overwrites or deletes an existing document. Changed file bytes or a changed latest version after preview consume approval and refuse the save. Plans never authorize document writes.

The Windows adapter requires a fixed local drive. It pins directory ancestors during operations, rejects junctions/reparse points and hard-linked files, and opens existing versions with sharing that excludes writers and deletion. Model text never becomes a filesystem path.

New bytes go into an exclusive pending file. Code flushes and reads them back, checks Stop, renames that exact open handle with replacement disabled, and reads the saved bytes back again. One-use approvals expire after 120 seconds and freeze the displayed text even if the Artifact changes during approval.

## Important limits

The bounds are 20 documents, 12 saved versions per document, 100 reads and 20 saves per chat. Files are not encrypted. Same-user programs can edit them later. Generated filenames preserve stable identity and versions; the interface also shows bounded first-line friendly labels.

A crash can leave an ignored pending file. Power-loss durability is not guaranteed. Stop can coincide with publication after its last check. Filesystem transactions now use owned workers with a ten-second budget. If publication is unconfirmed, use Check last save before retrying. See the October 18 update for recovery and remaining OS limits. Existing versions remain.

<!-- PAGE -->
# Artifacts interface and selected media

## Local Studio and editable drafts

The window was redesigned with a shared dark/light palette, Segoe UI, sidebar utilities and a draggable conversation/Artifacts divider. Code has an inert editor, line numbers and simple highlighting. Markdown, HTML, SVG and scripts remain text; they are never executed or fetched as web previews.

Artifacts hold document/code drafts and immutable generated-media snapshots. Current-revision checks prevent stale replacements. Unsaved human editor text survives a newer model revision. Restore appends another version rather than destroying history.

Import and Export are person-controlled. Export writes the exact selected snapshot to a chosen new destination and refuses existing files. New chat clears draft/history memory, while exported files, generated outputs and saved Documents remain on disk. The model cannot operate the export picker or choose an arbitrary write destination.

## Image audio and video understanding

Image attachment has a person-controlled preview. Cropping/redaction change the actual inference pixels, not merely an overlay. Screenshot capture is limited to the owned practice window; it is not a live view of the whole laptop.

Selected WAV files can be transcribed locally with the English tiny speech model. Selected MP4 files are sampled into four timestamped frames/contact sheets, initially bounded to 60 seconds and 64 MB. MP4 audio and events between sampled frames are not analyzed. There is no continuous microphone listening or full video understanding.

Interpretation is tool-free and treated as untrusted observation. It can hallucinate or quote private information. Local processing reduces network disclosure, but does not make every interpretation accurate or suitable to share.

## Experimental generation

Separately approved prompts can produce a local SD-Turbo image or a short experimental ModelScope video. Workers use fixed pipelines/settings and local-only weights. Missing weights cause refusal; runtime inference never downloads them automatically. Outputs use unique filenames and are published only when complete.

One image run produced 512 by 512 pixels in 32.89 seconds. One video run produced 256 by 256 pixels, 16 frames at 8 frames per second, in 37.93 seconds. The video sample had a model-generated watermark-like artifact. These demonstrate a working pipeline, not polished output or broad stability.

## Privacy and lifecycle

New persistent audit events retain metadata instead of complete document/prompt payloads. Old logs are not retroactively cleaned, and chat/tool history can contain text. Job memory controls do not cap VRAM or provide an OS network firewall. Model weights, runtime, identity, audit logs and saved workspace data are excluded from the source package.

<!-- PAGE -->
# Work completed and verification record

## Milestones through saved Documents

1. Built read-only browser tools with interception, URL/DNS policy, pinned fetches and a dedicated Playwright owner thread.
2. Added numbered links, GET-form search, exact outbound-address consent, stale-target refusal and narrow browser plans.
3. Strengthened browser budgets and same-host scope, with redirects and unsafe resource types refused.
4. Added fitting local-model routing/unloading and image observation, followed by practice UI Automation and process controls.
5. Delivered first versions of the ten requested improvements: practice isolation, semantic observation, narrow actions, Stop, exact previews, verification/recovery, capture privacy, routing evaluation, media input and local generation.
6. Added Artifacts, inert code/document views, version editing and person-controlled import/export, then improved the appearance.
7. Added owned classic Notepad, followed by verified revision receipts, visible status, turn pauses and fresh-read recovery.
8. Completed a separate guarded Strata feasibility test and retained fitting models as the default.
9. Added saved Documents, exact approved publication, retained recovery versions and the Documents interface.

## Saved Documents milestone evidence

The workspace update passed 168 offline plain-assert tests in nine suites: 38 browser/search/core, 24 browser network, 10 fetch, 23 model/vision, 20 computer/media, 13 Artifacts, 14 Notepad, 8 Notepad workflow, and 18 saved-document tests. The new suite blocks Internet sockets and uses fake disk, model and approval objects.

Real Windows/Tk document fixtures passed temporary-folder saves, full byte checks, stale refusal, retained versions, no-overwrite publication, hard-link refusal, synthetic reparse-metadata rejection, Stop before publication and pending cleanup. Unicode/astral folder characters were tested. Actual hostile junction creation was not tested.

Real document UI checks covered visible controls, No-default approvals, explicit saves, reopen/recovery, and New chat retaining files while clearing permission. Existing Tk approval and Artifacts fixtures passed after integration. Earlier real browser, practice and Notepad fixtures and their recorded results remain in the repository.

## Local inference evidence

Local gemma4:e2b created a saved synthetic document, read it, revised its Artifact and saved version 2 in 18.58 seconds. Folder permission and two exact saves used a fixture restricted to those synthetic contents in a temporary folder. Both final byte values matched; version 1 remained. Test approval callbacks never enter production UI.

Other single runs include 24.01-second Notepad draft/revision, 15.57-second Notepad start/read/edit and 32.73-second practice workflows. They do not prove general planning reliability, absence of bugs or safe behavior on arbitrary tasks.

<!-- PAGE -->
# Remaining risks and future improvements

## Largest design challenge

Dependable permission control and recovery across more apps remain the main challenge. Models misunderstand tasks, people can misunderstand approvals, and windows/documents can change between observation and action. Additional GPU power does not remove those issues.

These checks operate within normal user-level Python and Windows processes. They are not an OS security boundary against arbitrary native code, malicious same-user programs or every browser background subsystem. Full computer use remains feasible as a direction, with progressively defined capabilities.

## Ten proposed next improvements

1. An editable document catalog and search. Current friendly labels derive from the first nonempty line, with code-controlled filenames.
2. Longer-document support with bounded sections and visible diffs. Test preservation of unrelated paragraphs before increasing limits.
3. Further filesystem testing under abrupt power loss and hostile concurrent changes. Owned workers and uncertain-save checks are now implemented.
4. Broader evaluation on unseen, longer and multi-turn tasks. Independent synthetic cases, repeated seeds and separate task/control scores are now implemented; keep success criteria fixed before comparisons.
5. Another narrow application adapter with a documented action contract. A rich-text editor is a candidate, not a completed feature.
6. Visual observation/OCR where accessibility is missing. Bind any future coordinate action to a fresh image, window identity, preview and verification.
7. Cross-application checkpoints and optional persistent history. Current progress and checkpoints stay in RAM, with fresh reads on Resume.
8. Evaluated media sampling, optional MP4 audio and uncertainty reporting, while keeping observation separate from permission to act.
9. Representative routing/switching benchmarks. Retest optional offloading only under a chosen memory and workload budget, with fixed pass criteria.
10. Broader autonomy in a disposable VM or similarly enforced environment with restricted mounts/network before the everyday desktop.

## Separate capability decisions

Email, messaging, uploads, payments, credentials, arbitrary shell commands, installation and unrestricted deletion are outside this build. Any later addition needs its own capability and approval design. Screenshot support should not silently grant these powers.

The next practical evidence should come from low-impact study workflows using saved Documents. Check whether it preserves edits, asks understandable approvals, reopens files and recovers correctly. Wider app control becomes useful when these foundations work predictably.

<!-- PAGE -->
# Source guide and practical next steps

## Code and evidence

The active checkout is work/computer_use_repo beneath this task workspace. README.md covers setup. DOCUMENTS.md explains saving; DOCUMENT_EDIT.md explains bounded edits. NOTEPAD.md covers native guards. ARTIFACTS.md, MODEL_ROUTING.md, RELIABILITY.md, TOP10_STATUS.md and VALIDATION.md describe components and recorded results.

browser_tool.py uses shared fetch.py/urlcheck.py policy. agent_core.py validates and dispatches tools. chat_window.py owns approvals. artifacts.py and artifact_panel.py own drafts and their interface. workspace_documents.py manages document permission, numbering and proposals; workspace_native.py implements handle-based files; workspace_panel.py provides the saved-document view.

Document tests include test_workspace_documents.py, test_workspace_live.py, test_workspace_io.py, test_workspace_io_live.py and test_document_edit.py. evaluate_reliability.py and test_reliability.py cover independent model tasks and their scoring. Existing tests preserve browser, model, media, practice, Artifacts and Notepad coverage. Plain asserts need Python without -O; native fixtures need Windows and dependencies.

The separate offloading report is outputs/model_offload_trial.md, with JSON decision/resource/cleanup evidence beside it. The experiment remains outside app source and is not an automatic route. Retained model data are large. Previously blocked cache cleanup was not retried through another route.

## Repository and packages

Existing repository: https://github.com/arowsom-oss/local-ai-agent

Existing draft pull request: https://github.com/arowsom-oss/local-ai-agent/pull/1

Branch: codex/browser-risk-tiers-2026-10-16

The prepared launcher uses the isolated working checkout and runtime. The source ZIP excludes weights, environments, generated media, private identity, logs and saved Documents. A SHA256 manifest identifies packaged sources. It is not a standalone installer; another laptop needs dependencies and local models.

## First task to try

Ask: "Create a short document Artifact explaining plant and animal cells, then save it as a new Document." Inspect the folder and complete text before approving. Request one revision and inspect that preview. Load version 1 from Documents and confirm recovery does not erase version 2.

Keep meaningful personal work backed up outside this experimental app. Stop ends owned scratch processes, but saved Documents persist. After an uncertain save result, inspect the folder rather than assuming nothing happened.

This report records implemented behavior, design explanations and measured experiments. It does not certify a security audit or promise all future tasks will succeed. The next useful evidence is a small set of repeatable real workflows with explicit success criteria and recoverable failures.


<!-- PAGE -->
# Reliability update on October 18 2026

## Task progress and checkpoints

The conversation pane now separates proposed model steps from code-reported reads, approvals, verified operations, refusals and deferred actions. Reply ready means the model replied, not that an entire goal was independently verified. A paused task can Resume through a new turn, without replaying old action approvals. Code requires fresh target reads. Stop and New chat ignore late results; checkpoints are RAM-only.

## Responsive documents and uncertain saves

Document filesystem transactions now run in short-lived owned Windows processes with a ten-second transaction budget and a 256 MB Job limit. The UI uses background work and main-thread callbacks, keeping Stop available during manual file operations. Cancellation does not wait for a disk-operation lock. Process startup and termination still depend on Windows behavior; this is not an OS sandbox or a power-loss guarantee.

A timeout near publication is reported as Unconfirmed. New save proposals and Resume are blocked until the person uses Check last save. That bounded read checks the one generated output against its expected hash without rewriting it. It reports Verified, Different content, Not present when checked, or still unconfirmed. Earlier versions remain. Recovery metadata contains no document text or approval token and survives New chat within the running app; renewed folder permission is required. App exit loses that RAM receipt.

## Improvements to the review flow

Document labels now use a bounded first nonempty line, clearly treated as untrusted data. Filenames remain generated by code. Save previews include a text comparison as well as the complete before/after JSON text. A later load does not overwrite newer unsaved editor changes.

## Evidence and remaining model limits

The update passed 197 offline assertions in eleven suites and five Windows/Tk integration suites. Tests include real worker deadlines and cancellation, a UI heartbeat during deliberately blocked work, and an actual published version whose reply was lost and then independently verified without a rewrite. Friendly-title and comparison views were visually inspected.

A separate local gemma4:e2b create/read/revise smoke run passed with the new workers in 25.53 seconds, preserving the earlier version. A new repeatable three-case workflow evaluator failed its first strict creation case in 13.56 seconds: one proposal was refused, no document was saved, and the dependent cases were not attempted. That result was retained. These small runs demonstrate variability, not general reliability.

See FILESYSTEM_WORKERS.md and evaluate_workflows.py for the implementation and reproducible cases. The next useful evidence is more real-task evaluation and careful improvement of model instructions and document usability, while keeping code checks and exact approvals in place.

<!-- PAGE -->
# Measuring document reliability

## Independent cases and honest scores

The next update added evaluate_reliability.py. Each case starts in a new temporary folder with synthetic content and a fresh conversation. Four tasks check actual saved bytes: creation, appending a line, replacing one word, and preserving an existing human addition. Two separate controls check denied saves and a file changed during approval. Failure in one case no longer hides later cases.

The fixture accepts only exact expected folder, target/version and before/after text. Non-document dispatch is blocked. Test approvals never enter the real interface. A model saying "done" cannot earn a pass; file contents and retained versions decide. A control only passes if its intended approval stage was reached and the final refusal/state matches.

## Earlier measured comparison

The previous code's small model passed 1 of 4 tasks and both controls at seed 42. Guidance was clarified about Artifact revisions versus saved document versions. Offered tool schemas were changed to use the trusted dispatch registry. At seeds 42 and 43, the updated small model and the larger model each passed 5 of 8 task attempts. Control results were 4 of 4 for the small model and 3 of 4 for the larger one.

The larger model's failed control stopped before its intended exact-save preview, so the changed-file guard was not exercised in that attempt. No additional saved version was created. Total case times were 42.53 seconds for the one-seed baseline, 83.28 seconds for the updated small model, and 122.04 seconds for the larger model. Warm/cold state and failed tasks make these unsuitable as general speed rankings.

## Interpretation and code checks

For the single matched seed, the small-model task count changed from 1 of 4 to 2 of 4. This sample cannot establish a reliable improvement; schema ordering and descriptions both changed. Both two-seed models still made ordinary editing mistakes. No automatic preference for the larger model was added. An 8/10 general rating is not supported by these fixtures.

At this milestone 206 offline tests across twelve suites passed. Nine new checks covered exact-byte scoring, history, denied/stale operations, unknown tools, setup failures, registry alignment and bounded independent repetitions. These validate code and scoring, not model intelligence. Thirty live attempts, including failures, were retained in the reliability evidence.

Default full-menu evaluation deliberately shows the normal schemas while the fixture still blocks non-document execution. The documents-only option offers only executable fixture tools. Seeds 42 and 43 and temperature 0.2 aid comparison but cannot guarantee identical output. The old dependent evaluator and its failed first case remain in the record. See RELIABILITY.md for exact scope and commands.

<!-- PAGE -->
# Simpler document edits

## Reduce bookkeeping, keep exact approval

The new document_edit(document, find, replacement) tool handles small changes to an existing saved document. After a latest document_read, an empty find means append literal text. A nonempty find must identify one exact excerpt to replace. Trusted code preserves every other character and uses the recorded file identity, saved version and hash. The model no longer supplies Artifact revision counters for this path.

The code creates a separate proposal Artifact and uses the existing complete before/after comparison and exact-save approval. The normal one-use commit then rechecks inventory, saved bytes, Stop and publication, creates a fresh version and reads it back. Browser plans still cannot approve document changes. The Artifact/save workflow remains for new documents and broader rewrites.

## What refuses an edit

Only a successful read of the latest saved document records provenance. Historical reads, cancellation, New chat, commits and manual save observations revoke it. If saved bytes or the latest version changed, another current read is required. If the recorded read Artifact's stored revision changed, the helper refuses so that recorded human or AI draft changes are not silently discarded.

The match is literal and case-sensitive. Missing or multiple matches, including overlapping occurrences, are refused. The helper also refuses invalid controls, an empty final document, no-op edits and text over 8,000 characters. It does not use regular expressions, scripts, fuzzy matching or global replacement. A backslash followed by n is distinct from an actual newline; arguments are never silently decoded or repaired.

The model cannot supply paths, filenames, revision counters, overwrite flags or an approval value. Existing document, Artifact, version and save budgets still apply. Directly calling the tool function returns an approval-required error. Changed or uncertain state does not grant a fallback write path.

## Resume and recovery

A document fresh-read-gate refusal on Resume now ends the turn and defers queued calls, matching the existing denied/failed-save behavior. It cannot automatically read and retry the refused write within the same turn. A new person request can read current state and review a fresh proposal.

An uncertain edit publication is shown as Unconfirmed. Check last save independently checks the expected output hash without rewriting it. Stop and New chat clear edit authority; saved history remains. The guards are still ordinary application code, not an OS sandbox. Stored Artifact checks do not make an uncommitted GUI buffer or simultaneous human activity atomic.

## Verified implementation

The project passed 226 offline tests in thirteen suites. Seventeen new edit tests cover preservation, matching, bounds, latest-read provenance, human changes, limits, actual argument checks, approval during plans, queued fallback refusal, Stop, frozen previews, Resume and uncertain-save recovery. Added evaluator and routing checks accompany the earlier tests.

Three Windows/Tk suites passed again. Worker checks verified append/history, stale-preview refusal and hash reconciliation after a lost publication reply. Existing No-default approvals and progress/Resume passed. See DOCUMENT_EDIT.md and VALIDATION.md.

<!-- PAGE -->
# Model results and improved routing

## A simpler tool helps the larger model

The next evaluation retained the original six cases and added two document tasks: changing only a room number and appending while preserving quotes and a literal backslash. Expectations were fixed before the run. Each model ran two repetitions with the full menu, temperature 0.2 and seeds 42 and 43. No failed case was replaced by a retry.

The small model completed 5 of 12 document attempts and 4 of 4 controls in 108.70 seconds total. On just the original tasks it passed 3 of 8, below its previous 5 of 8. It still mishandled exact append proposals and once created an Artifact without saving. Adding a simpler tool alone did not improve this model's measured task count.

The larger model completed 12 of 12 document attempts, including all four additional-task attempts, in 223.16 seconds total. Its original-task count was 8 of 8, compared with 5 of 8 before the helper. However, only 2 of 4 control cases passed: both whole-text replacement controls were refused before the intended exact preview. The human-edit mutation was never reached and the original files remained. Those controls remain failed, not evidence that the guard was exercised.

One larger-model quoted-append case took 65.07 seconds. Better results in this small sample do not imply instant responses, general correctness or an 8/10 assistant. Deterministic and real-worker tests separately exercised stale-state refusal. Longer documents, multi-turn recovery and broader unseen work remain unmeasured.

## Routing must also work

Updating classifier instructions alone met just 3 of 7 fixed routing expectations: all four document requests still selected the small model. A new bounded code hint now selects the installed larger model when common English document/note/draft nouns occur with create/read/edit/save/change-style verbs in the first 4,000 characters. Other text retains the constrained classifier; selected-image analysis retains its fixed route.

The same seven probes then met all expectations. Four document hints selected the larger model without classifier inference; greetings, simple arithmetic and a general explanation selected the smaller one. This is a heuristic, not intent understanding: explanations or negations may overmatch, and other phrasing or languages may be missed. Manual model choice remains respected. Routing changes no permissions, file guards or approval requirements.

## End-to-end check and evidence

One actual Auto append selected the larger model for all four task model calls, obtained one exact synthetic save approval and retained the earlier saved version in 21.14 seconds. Fixture approvals remain outside production UI. There is no automatic model-switch retry after a refused mutation and no runtime model download.

The source/evidence package retains all 32 cases from this comparison, the Auto smoke, both routing-probe rounds and earlier reliability reports. The running record now includes the previous independent-evaluation milestone as well as this helper, Resume change and routing decision. Source, tests and this report use the existing branch and draft pull request; main and the original installation remain unchanged. This remains a supervised prototype with explicit, recoverable capabilities.

<!-- PAGE -->
# Diagnosing and fixing the stale-edit failure

## What the earlier reports missed

The two failed larger-model stale-edit controls ended before approval. Their old reports recorded Refused but omitted the specific validation cause. The evaluator now retains fixed refusal codes, bounded argument-length/comparison flags and a boolean stating whether the human-edit simulation actually occurred. It does not copy draft text, tokens or arbitrary error messages into diagnostics. A targeted case selector uses the same scenario and success criteria.

Two diagnostic reproductions again failed before approval: find did not occur in the saved text. A further confirmation showed that the model supplied the JSON-quoted document string as find, including its extra delimiter quotes. The replacement matched the expected new text in that confirmation, but exact matching correctly rejected the malformed find. These failed diagnostic runs are retained alongside the earlier results.

## The correction

document_read now ends with a JSON object containing a named text field instead of a bare JSON string. System guidance and the tool description explain that edits use the decoded value, preserving genuine quotes inside it. For example, the field value in {"text":"Hello"} is Hello without additional delimiter quotes. The metadata line and model tool arguments remain unchanged; manual parsers of the result should use its text field.

The backend still uses literal exact matching. It does not strip quotes, decode arbitrary replacement escapes, fuzzy-match text or retry a rejected save. A missing excerpt now has a distinct not-found error rather than sharing the multiple-match message. Genuine quoted document text must still be matched with its actual quote characters. Exact approval, stale-file checks and retained versions remain in force.

## Targeted verification

After this correction, both unchanged stale-edit scenarios passed at seeds 42 and 43. Each reached its exact preview, simulated the human file edit and refused the stale commit; the human text remained and no additional version was created. Their case times were 19.65 and 8.44 seconds. Passing requires the intended stage and final file state, not simply any refusal.

Five new regression checks cover the named read field, genuine versus framing quotes, privacy-preserving diagnostic reasons, the actual preview/mutation/refusal sequence and bounded targeted selection. All 231 offline tests in thirteen suites passed. Three Windows/Tk suites passed again, including real-worker changed-file refusal, version retention and lost-confirmation reconciliation.

## Full-run result and remaining limitation

The subsequent full larger-model run passed 11 of 12 document tasks and all four controls. Both stale-edit scenarios reached the simulated human change and refused its stale commit. One quoted-append proposal at seed 42 still contained unexpected text; exact approval was denied and no new version was saved. Seed 43 passed that case. The full run remains marked failed. This fixes the reproduced stale-edit issue, while preserving the new formatting failure as evidence of remaining model inconsistency. Routing, model weights and dependencies were unchanged.

<!-- PAGE -->
# A measured document-quality target

## Criteria fixed before the broader run

The practical target for a subjective 8/10 supervised document assistant was at least 95% exact task completion, every denial and changed-file control passing, no unexpected saved file state, and a task 95th-percentile time of at most 90 seconds on this laptop. This is a project-specific target for short plain-text document work. It is not a standardized model score or a guarantee of unrestricted computer use.

The qualification set retains the original eight scenarios and adds ten fixed cases before changing the append guidance: Unicode creation, plain-language append, repeated-word context, line deletion, tabs, quoted paths, blank lines/spaces, untrusted document text, denial of an existing-file change and a changed quoted document during approval. Two fixed seeds produce 28 tasks and eight controls. Every case has a fresh temporary workspace and conversation; exact expected bytes and approvals remain unchanged.

## Failures retained and diagnosed

The first broader run completed 24/28 tasks and 8/8 controls, with all file states safe. Its task median was 9.66 seconds and its 95th percentile was 61.90 seconds. Both quoted-append attempts stopped after reading. Both plain-language appends proposed the wrong exact text and were refused. This run failed the declared target.

An earlier diagnostic attempt also stopped after reading. Further diagnostic requests confirmed double JSON encoding of a quoted append and a dropped final period in the plain-language append. Only fixed synthetic fixture text was inspected for that punctuation diagnosis; model reasoning was not copied. One initial diagnostic helper lacked the Windows multiprocessing main guard and produced child setup errors; its parent still made a refused synthetic model attempt. The helper was corrected, and its repeat also failed with the same missing period. That extra attempt is disclosed, with no qualification credit.

<!-- PAGE -->
# Binding exact text in code

System and tool guidance now include a concrete JSON argument example showing one decoded leading line break, the requested period and no additional final newline. Literal matching and exact human approval still enforce what is saved; code never unquotes, repairs or retries a malformed edit. Save previews now show character, line-break and tab counts, final-newline presence and lines ending with spaces/tabs, beside the full exact text. Diagnostic reports retain counts and fixed flags, not draft content or reasoning text.

The targeted example-guidance run passed 3/4 tasks. A failed case returned done_reason=length: 3,472 prompt tokens plus 4,720 generated tokens exhausted the 8,192-token context, without completed content or actions. A direct-generation experiment after document reads passed 21/28 tasks and 8/8 controls. It increased append errors, so it was rejected. Reasoning stays enabled. Responses marked length now explicitly fail before any parsed tool calls execute, revoke saved-document observations and require review/new request; there is no automatic retry.

Restoring reasoning with these examples completed 26/28 tasks and 8/8 controls. Both quoted appends still exhausted the context. This candidate also failed the target; prompt instructions alone were insufficient.

## New bounded append path

For a current person request beginning Append exactly followed by one valid JSON string, code now decodes one literal layer. document_append_requested(document) supplies only a freshly read document number. The first bound-tool candidate completed 26/28 tasks and 8/8 controls; failed cases were holdout_quoted_append seed 42, qual_delete_line seed 43. The raw literal still appeared in the model message. The final candidate retains that value in code and sends the model only target/context instructions. Other document writers are omitted and actual dispatch refuses them for that request, preventing a replacement override.

The binding is one attempt per current turn. Unsupported framing, empty/control/oversized text, extra parameters and missing/used bindings refuse. It cannot bind page/model output, an earlier turn or a wrapped Resume request. A fresh explicit literal request is needed after pausing. Code requires a document_read in the current turn; the backend also checks that it was the latest version. No tool description is trusted to enforce these rules.

The decoded data goes through the existing prepare_edit and exact-save path: latest read, unchanged source and Artifact, full before/after approval, one-use proposal, native file guards, retained versions and read-back. Denial, stale state and uncertainty still halt. This is a narrow alternative to asking the model to copy or escape an exact string, not permission to edit another folder or send data elsewhere. Ordinary document_edit continues to treat model-supplied text literally; it performs no repair.

## Full measurement after the binding change

The final unchanged qualification set passed 28/28 tasks and 8/8 controls. Median task time was 11.69 seconds; 95th percentile was 20.51 seconds. All saved states safe: True. Declared target met: True. The full run's all_passed flag is True. Earlier failed runs remain retained. Normal app text/tool requests now explicitly use the same temperature 0.2 measured by the fixture, instead of an unspecified model default. This does not guarantee deterministic output or confer authority.

<!-- PAGE -->
# What the quality comparison means

## Closest familiar experience

Think of Local Studio as a focused, local ChatGPT-like assistant for small approved tasks. That is a product/use-case analogy, not proof that its intelligence equals a named GPT, Claude or Gemini model. The actual installed engines are Gemma 4 E2B for lighter requests and Gemma 4 12B for routed document work. No model weights were trained or upgraded in this change.

Google describes Gemma 4 as open models for devices including laptops, with reasoning and tool-use capabilities. OpenAI's official model documentation distinguishes focused repeatable tasks from demanding reasoning and workflows across apps. Those descriptions help explain the roles; they do not establish a head-to-head ranking of this specific installation. Local engine settings, the tool code, approval UI and task instructions also affect results.

Google model card: https://ai.google.dev/gemma/docs/core/model_card_4

Official OpenAI model guidance: https://learn.chatgpt.com/docs/models

## Rating and practical limits

The declared target was met, supporting a provisional 8/10 for these supervised short document tasks. This rating does not apply to general intelligence, broad coding, long conversations, image/video quality or full Windows control. The tests use small synthetic files and developer-authored cases, with fixed seeds that do not ensure reproducibility. After diagnosis these are regression cases, not unseen benchmarks. Human review remains necessary.

All 245 offline tests in thirteen suites passed. Three real Windows/Tk suites passed, covering Documents, task progress and file workers. Six new evaluator tests cover exact bytes, privacy, unfinished tasks, coverage, controls, unsafe states and latency gates. A core test proves that parsed calls in a truncated reply never execute. Seven binding tests cover decoding, bounds, payload overrides, omitted literal data, dispatch restrictions, replay, own approval inside a plan, callback mutation, stale state, uncertainty and fresh-read/Resume gates. Comparison checks expose whitespace while retaining full approved text.

The existing branch and draft pull request remain the publication path; main and the original installation are unchanged. No dependency, model, download, mutation retry or broader tool authority was added. Restart Local Studio to import updated instructions and preview formatting.

## Next evidence to collect

Test longer and genuinely new multi-turn tasks with human interruptions and varied wording. Evaluate coding, media and browser tasks separately before assigning their ratings. A matched comparison with a named cloud model would require the same cases and settings; it has not been run, and no private documents were uploaded for this comparison.


<!-- PAGE -->
# Storage and collaboration handoff

## Primary installation confirmed October 19

Alexander identified C:/dev/local-ai-agent on the Acer C: drive as the primary installation. Its clean main checkout was 7b144f1473e2aa09ae32d236942af977608f5085, including the implementation merge (PR 1) and the collaborator's scorecard (PR 2). Earlier statements about an unmerged draft describe previous milestones. This inspection did not modify the primary checkout or merge another change.

Image and video manifests resolve inside its model_cache. All required filename groups were present for SD-Turbo and ModelScope video, using the recorded revisions. This checks paths and presence, not weight hashes or a new generation run. Active image, video and audio caches occupy approximately 2.58, 3.67 and 0.078 GB. The old workspace scan found no duplicate model cache or model-weight file of 256 MiB or larger.

## Cleanup attempted, blocked and recorded

The old development Python environment occupies 4.99 GB and was still used by a running GUI interpreter. Keep it and its existing launchers. Two Python GUI processes were open; neither was closed, and their command lines do not establish both source directories. Reports, source snapshots and recovery evidence were also retained.

The rejected Strata experiment has an ignored virtual environment containing 7,238 files and 731,791,221 bytes (0.732 GB). No process from that environment was found. An explicit path-contained PowerShell removal was rejected by automatic approval review with blocked by policy. No deletion ran, no alternative route was attempted, and no disk space was reclaimed. Other Strata files include source and untracked dependencies and were retained.

The primary cache also holds about 25.61 GB of abandoned Wan downloads, including incomplete files. The current manifests do not reference them. Earlier removal had been blocked; this pass left them untouched. This is a separate cleanup candidate, with other local uses still unverified. It is not the active ModelScope video cache.

## Shared source and local access

LOCAL_SETUP_HANDOFF.md is proposed in draft PR 3 on a new branch based on current main. It records the primary folder, model revisions, protected assets, cleanup failures and collaboration precautions. GitHub shares tracked source and instructions. Weights, environments, personal files, generated media and saved documents remain local and ignored. Each AI session needs its own filesystem access to use them; GitHub access alone is insufficient.

No runtime code, model path or permission changed. No application test suite or model benchmark was rerun. The local cleanup JSON records zero deleted files and zero reclaimed bytes. Preserve the other collaborator's scorecard and use branches/review for subsequent implementation work.


<!-- PAGE -->
# Generated media belongs in Artifacts

## What was reproduced and changed

Alexander reported images and videos appearing as files instead of useful Artifacts. Inspection confirmed that generation writes to this installation's generated folder, not Downloads. No automatic scan of personal Downloads was added. The reproducible UI defect was that a new image/video could enter the Artifact list while an older document or code selection remained visible. The old refresh behavior was reproduced against the new fixture.

New media now reveals the Artifacts pane and becomes its visible selection. Unsaved text remains intact and selected, with a notice naming the new Artifact to choose after saving. Regular timer refreshes do not restart the same preview. Existing immutable snapshots and bounded local decoder workers still apply.

The generation result now names an Artifact only after registration succeeds. Invalid worker output, full stores, outside-folder paths and late Stop return explicit errors. A failed or denied generation blocks further generation requests for that turn, including another media tool; only a new person request can try again. This prevents an automatic retry merely because preview delivery failed. A completed file can remain for recovery.

## Reopening earlier files

Artifacts > More > Open generated image or video reopens an original output from the current app's generated folder. It uses the same fixed-folder, UUID-name, kind, size and memory checks. It starts no generation or download. New chat and restarting still clear RAM Artifacts, but the retained file can be reopened. Other media, including files in Downloads, can use the existing Import a file action. Export remains an explicit person-chosen copy.

## Evidence and delivery

All 255 offline plain-assert checks passed across fourteen suites. Eight new cases cover media delivery, immutable bytes, exact approvals, selection, unsaved text, errors, retry blocking, Stop and recovery. Four real Windows/Tk suites passed: Artifacts, selected-media UI, task progress and saved Documents. The Artifacts fixture exercises actual core dispatch with scripted model/worker results, real PNG/MP4 decoding, playback and recovery after New chat. No new GPU generation benchmark was run.

The primary installation's existing image and video also reopened visibly: one image frame and sixteen playable video frames. Their files were not changed. Development checks caught and corrected a test-helper type assumption and a retry-guard placement error before the final full pass.

Commit e788e62f640912dcef991553deb7b5a8ec2f1db7 is published in draft PR 4, targeting simple-ui. The clean primary checkout was switched to that feature branch after checking it had no collaborator changes. Main and simple-ui were not merged or reset. Recent UI, display scaling and NumPy fixes remain. Existing windows need restarting to load the update. A local launcher points at the primary source and the already installed media-capable runtime.

<!-- PAGE -->
# Private remote chat and media roadmap

## The requested experience

Alexander wants to open his own web address away from home, sign in, chat, and generate or view images and videos on the Acer. The local project still aims toward broader guarded computer use, but the remote interface will exclude computer control. The laptop must remain powered on, awake, connected and running the service. A web page does not move inference into the remote device or make an offline laptop available.

This is a planned next stage, documented in REMOTE_ACCESS_PLAN.md. No account, password, web server, public address, firewall change or remote endpoint was created in this update.

## Separate authority at the server

Remote text chat should use no tools. Explicit image/video requests should enter a separate bounded job API with fixed parameters and exact prompt review. The server must reject desktop, screenshot, browser, shell and arbitrary-file requests in code. Reusing the entire desktop tool loop behind a login would expose more authority than requested; hiding controls in the page is insufficient.

Persist job state and owned media so a reconnect or restart can recover completed work. Check the authenticated owner on every job, cancel, preview and download; accept opaque identifiers rather than filesystem paths. Keep model weights and old local files private unless a migration is explicitly approved. Serialize GPU jobs with local use, retain cancellation/timeouts/output limits, bound the queue and disk use, and do not resubmit uncertain jobs automatically.

## Authentication and connectivity before exposure

Plan a single owner account with username/password support, maintained authentication, secure password storage, MFA and throttled generic login failures. Use HTTPS and expiring, revocable server-managed sessions with protected cookies and CSRF checks. Credentials must stay outside source and logs. These are acceptance requirements, not completed security claims.

A private authenticated network is one option when a permitted client is available on the visiting device. Browser-only access without that client needs a separately authenticated HTTPS gateway. Choose that deployment with Alexander later; do not expose Ollama or a development server directly.

OWASP authentication reference: https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html

OWASP session reference: https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html

Private-network option: https://tailscale.com/docs/features/tailscale-serve

## What must pass before use

Test unauthenticated, logged-out, expired and revoked sessions; cross-session media access; CSRF and malformed requests; attempted desktop/shell dispatch; cancellation, dropped replies, restarts, quotas, GPU contention and a sleeping laptop. Require clear states and no duplicate generation. Start with local fake/offline checks, then authenticated loopback integration and a deployment review, before a second-device trial. Authentication cannot promise perfect security; remote access needs its own validation.

<!-- PAGE -->
# Talking to Local Studio

## The requested experience

Alexander clarified that memory means the Acer's 12 GB VRAM and 32 GB system RAM, rather than SSD space. He wants to speak a message, let the assistant answer in text, and hear that text as speech. This update adds turn-based local voice controls while preserving the chat interface and existing approval boundaries.

Talk starts one explicitly approved default-microphone recording. Finish recording ends it early; sixty seconds is the maximum. Existing Whisper tiny.en transcribes on CPU. A separate review displays the untrusted transcript and can place it in the editable message box. Only pressing Send submits that draft. Recording or transcription never executes spoken words or replaces an existing unsent message.

More > Speak replies for this chat enables bounded automatic playback after a separate consent. The answer still appears in text. Piper's fixed English voice reads the exact raw reply on CPU, up to 2,000 characters and 120 seconds; longer replies remain text only. Stop and New chat revoke this opt-in. More > Read reply aloud approves one exact reply. More > Transcribe WAV into message accepts an existing recording without opening the microphone.

## Data and authority

Microphone capture, speech output and photo-video selection are person-operated UI actions, not model tools. There is no wake word, background listener, voice cloning, automatic Send or remote voice endpoint. Voice bytes stay in RAM by default; the app writes no recording or synthesized WAV file. Windows can still page process memory, so RAM-only does not promise absence from operating-system storage.

Audio is English-only in this first version. Tiny.en can mishear speech; transcript review remains necessary. A working default microphone/speaker and Windows permission are required. The workflow is turn-based, not simultaneous listening and speaking. Stop terminates only owned workers and discards a pending recording. A physical microphone trial still needs the person using the device; no personal speech was captured during development.

## Evidence and corrections

Real Piper synthesized a fixed synthetic sentence in 2.72 seconds, producing 3.04 seconds of audio. Existing Whisper recovered the sentence and number 42 in 5.27 seconds. Sampled child working sets peaked around 156 MiB and 232 MiB. The same pair passed with gemma4:12b resident, the normal 8,192-token context and full tool menu; no tools executed in that check. These are single runs, not hard peaks or guarantees for every conversation.

An initial 768 MiB synthesis Job limit failed, despite low sampled working-set use. Raising that commit ceiling to 1.5 GiB passed. Python 3.12 also exposed a playback error: it has no SND_SYNC constant. Default synchronous mode with SND_MEMORY and SND_NODEFAULT fixed it; an owned worker then played synthetic silence from WAV bytes successfully. Commit ceilings and physical working sets measure different things.

Piper API: https://github.com/OHF-Voice/piper1-gpl/blob/main/docs/API_PYTHON.md

Voice card: https://huggingface.co/rhasspy/piper-voices/blob/main/en/en_US/lessac/medium/MODEL_CARD

<!-- PAGE -->
# Reference photos and the memory budget

## A bounded replacement-video candidate

The earlier ModelScope sample contained a faint stock-watermark-like artifact. The investigation selected the publisher's Diffusers-compatible LTX-Video 0.9.5 2B pipeline for a laptop trial, supporting both text-only and image-to-video. This choice does not promise clean watermarks, perfect subjects or better motion for every prompt. Larger Wan/Hunyuan candidates were considered from their official specifications, not downloaded or benchmarked head to head.

Attach > Photo to video lets the person choose a PNG, JPEG or WebP, inspect normalized pixels, and hide or crop regions before approving a motion prompt. The exact edited immutable bytes condition generation; the model supplies no file path. Padding fits the complete reference into 384x256. The selected profile uses 65 frames at 24 fps and 30 steps, producing about 2.71 seconds of silent video. Prompt encoding caps at 128 tokens and can truncate long descriptions; both approval paths disclose it. Output enters Artifacts with a unique generated-folder backup. ModelScope files remain without automatic fallback.

## Quantization and staged loading

Counts constructed from local configurations on the meta device found 4,762,310,656 T5 encoder parameters, 1,923,385,472 transformer parameters and 1,246,913,522 VAE parameters. T5 FP32 weights alone require about 17.74 GiB. NF4's four-bit weight minimum is 2.22 GiB, before nonquantized layers, scales and overhead. BF16 transformer and VAE weights total about 5.91 GiB. These calculations exclude activations, libraries, allocator caches and Windows overhead.

The quantized encoder runs in its own owned process, returning 4 MiB of finite CPU embedding bytes and 256 mask bytes. That process must exit before the renderer loads. CPU offload moves renderer components as needed. Temporal VAE decoding uses 16-frame tiles with stride 8; spatial tiling's default threshold exceeds this resolution. The manager's lease unloads its Ollama model and excludes chat inference during GPU generation. It cannot unload another application's models. Speech uses CPU.

Video admission requires 8 GiB free system RAM and 9 GiB free VRAM. The outer Job has a 16 GiB commit ceiling including descendants, with a separate 12 GiB encoder ceiling and ten-minute total deadline. A sampled RAM guard stops near a 2 GiB system reserve; an 82 percent PyTorch allocator fraction limits that allocator only. These controls can refuse or stop a job; they cannot prevent every competing-process, driver or memory spike.

## Local assets and installation

Piper's voice file is 63,201,294 bytes; Whisper's approximately 78 MB assets were already installed. The LTX publisher's full FP32 T5 shards make the video download about 25.39 GB on disk. Disk bytes are not simultaneous RAM or VRAM use. New runtime packages are pinned; model loading stays local, uses safetensors for video and accepts no remote model code. No model weights or runtime environment enter GitHub.

The large download needed bounded HTTP-range recovery after transport stalls. Each completed large weight is checked against the publisher's SHA-256 before the local video manifest is created. No old cache or personal file was deleted. Actual GPU qualification and final delivery are recorded in the following chapter.

LTX model card: https://huggingface.co/Lightricks/LTX-Video-0.9.5

Pipeline documentation: https://huggingface.co/docs/diffusers/api/pipelines/ltx_video

Quantization support: https://huggingface.co/docs/bitsandbytes/installation

<!-- PAGE -->
# Video qualification and delivery

## Measured fit, with limits

Synthetic text/reference trials decoded all 65 frames at 384x256 and 24 fps in 95.16/94.30 seconds. Sampled total GPU peaks were 4.67/7.10 GiB; summed child working sets were 7.42/7.51 GiB. System RAM availability stayed above 4.22/4.09 GiB respectively.

A further unpatched production-profile reference run imported chat_window in the parent and each spawned worker, matching application startup. It passed in 97.16 seconds, decoded 65 frames, used about 7.10 GiB sampled total GPU and 7.51 GiB working sets, and retained at least 4.11 GiB available RAM. CPU synthesis, transcription and silent playback also passed with this bootstrap. No personal microphone recording was made.

Figures are sampled single runs under a development workload, not hard maxima. Working-set sums can double-count shared pages; private commit is different and reached about 15.50 GiB in the app-bootstrap video run, close to its 16 GiB ceiling. PyTorch reports each process's allocator; NVML samples total GPU use including other applications. A busier laptop, different driver or larger job can still refuse. The practical strategy is CPU speech alongside chat, and one heavy GPU generation job after unloading managed chat.

## Failures that changed the implementation

Same-process loading failed under both 12 and 16 GiB commit limits, while individual renderer components loaded successfully. Moving the encoder into a nested owned process, requiring its exit and passing only bounded CPU bytes fixed that path. A short cleanup wait initially refused before Windows finished terminating the encoder; an explicit five-second bounded join and exit check now prevent overlap. An image-to-video decode error also exposed a CPU/CUDA generator mismatch; the pipeline now uses a CUDA generator. Failed attempts published no completed output.

The initial 33-frame clips fit but were nearly static. A longer 65-frame profile with temporal decoding showed clearer motion at similar measured cost. Inspected frames 0, 32 and 64 still show soft detail, distortion and a ball leaving the view quickly. No obvious watermark appeared in those inspected frames. This is an experimental capability, not a broad quality comparison or a promise of clean, accurate video.

## Tests, review and using the update

All 283 offline plain-assert checks pass across fifteen suites. Five native Windows/Tk suites pass, covering Artifacts, media selection, progress, saved Documents and voice/reference controls. GUI microphone/inference fixtures use fakes; separate real worker checks cover local synthesis, transcription, silence playback and GPU generation. An overnight suspended GUI fixture exceeded its deadline; the complete awake-desktop rerun passed. Physical microphone and driver compatibility still needs a person-operated trial.

Commit 7b70043a31059419d1e86519a6318e0d597099c3 is published in draft PR 6, stacked on PR 4. It preserves main's merged collaborator UI changes. The clean primary C:/dev/local-ai-agent checkout now uses codex/reference-video-speech-2026-10-19, with every changed source file verified against the tested version. Main was not updated or merged by this operation. Model caches, personal files and old app windows were retained.

Restart with start_media_studio.cmd to use the installed media runtime. Talk records a reviewed message; More enables spoken replies; Attach > Photo to video makes a short clip. Chat retention, reasoning and streaming are unchanged. Remote access remains planned.

Draft review: https://github.com/arowsom-oss/local-ai-agent/pull/6


<!-- PAGE -->
# Auto routing: measured reload fix

## Evidence before changing code

A review identified mismatched context sizes: Auto classified at 2,048 tokens and replied at 8,192. On installed Ollama 0.40.3, observed runner PIDs and API timings confirmed that this reloaded the same model. A 100 percent GPU reading did not exclude loading delays. The launcher C:/dev/agent/start_chat.bat correctly targets C:/dev/local-ai-agent; its checkout follows a feature branch, not main. PRs 1, 2, 3 and 5 are merged; the earlier status omitted PR 3's setup handoff document.

Before runtime edits, the actual app turn loop ran two synthetic greetings on Auto, two on manual gemma4:e2b, and a read-only document explanation on Auto/12b. Tool calls were refused before dispatch; none were returned. Each mode began cold, followed by a warm turn. The second Auto greeting took 19.0002 seconds, including 17.6694 seconds loading. Manual's second greeting took 3.0719 seconds, including 0.0217 seconds loading.

## Change and measured result

The classifier, replies, compaction and media observation now share the existing 8,192-token reply context. Numeric timing diagnostics report loading, prompt evaluation and generation through the existing UI log, with counts and thinking length; they exclude prompt, reply and reasoning text. Diagnostic failures cannot retry or change responses. Normal reply thinking, model retention and approval rules are unchanged.

Repeating the protocol after the fix, the second Auto greeting took 0.7877 seconds, with 0.0620 seconds loading. One runner remained at 8,192 across classification and replies. The cold Auto turn fell from 106.18 to 12.89 seconds, but its baseline had unusually expensive loading and prompt processing. Manual replies also varied. This small A/B demonstrates avoidable reloads, not a guarantee of subsecond answers or a claim that every improvement came from this fix. Cold loads and longer reasoning still take time. PERFORMANCE.md records all five comparisons and caveats.

## Verification and delivery

The new offline regression first failed with four simulated loads instead of one; that failure remains part of the record. After the fix, all 291 offline plain-assert cases across sixteen suites and five native Windows/Tk suites passed. Raw before/after measurements remain preserved separately. The formal scorecard has not been run; its Results table is unchanged.

Commit 3b34f4054502991c3ce818ff151801050641db97 is draft PR 7, stacked on PR 6. The clean primary checkout now uses codex/ollama-context-reuse-2026-10-20, and all seven changed files match the tested source. Main was not merged. Restart with the existing start_media_studio.cmd launcher to use the fix. Open app windows retain their old imported code until restarted.

Draft review: https://github.com/arowsom-oss/local-ai-agent/pull/7


<!-- PAGE -->
# Current handoff for Claude

## Where to read and what is current

This October 20 snapshot supersedes historical branch, model and test-count statements in earlier chapters. The full record is now shared as PROJECT_RECORD.md on codex/ollama-context-reuse-2026-10-20 in https://github.com/arowsom-oss/local-ai-agent. Read that branch, not only main. Its README links the record. The matching local PDF and Markdown remain under this task's outputs folder.

The primary app is C:/dev/local-ai-agent. Verified runtime commit: 3b34f4054502991c3ce818ff151801050641db97. A subsequent documentation-only commit adds this handoff and README link; it changes no runtime. Restart via outputs/start_media_studio.cmd using work/agent_runtime/Scripts/pythonw.exe. Existing app processes retain old modules. The C:/dev/agent launcher points to the primary app; no backup folder was removed.

## GitHub review state checked October 20

Main is 58adaf433d108c7b98703b4c0cd0b0c1331fb595; PRs 1, 2, 3 and 5 are merged. PR 3 added LOCAL_SETUP_HANDOFF.md, whose storage/model inventory is historical. Draft PR 4 targets simple-ui and delivers generated media to Artifacts. Draft PR 6 targets PR 4's branch and adds voice/reference video. Draft PR 7 targets PR 6's branch and adds context reuse, timings and this shared record. PRs 4, 6 and 7 remain unmerged. No new merge was performed. Review bases matter because main alone lacks these features.

## Present capabilities and limits

The app has guarded text browsing/search, exact outbound-address consent, local chat routing, inert editable Artifacts, versioned plain-text Documents, an owned practice app and scratch classic Notepad. General control of arbitrary Windows apps is unfinished. Selected-media analysis is tool-free. Broad shell, uploads, email, credentials and unrestricted file operations are unavailable.

Images use local SD-Turbo. Video now uses LTX-Video 0.9.5 2B, including person-selected reference pixels: 384x256, 65 frames at 24 fps, 30 steps. Legacy ModelScope and abandoned caches remain unused, without automatic fallback. CPU Whisper tiny.en supports reviewed voice messages; CPU Piper speaks replies after consent. Recording never sends a message automatically. Physical microphone compatibility still needs a person-operated trial.

The hardware budget remains 12 GB VRAM and 32 GB RAM. Heavy GPU jobs release managed chat and run serially with resource checks; CPU speech can accompany chat. Video's staged encoder/render workers avoid simultaneous full components, but sampled peaks are not guarantees. VOICE_AND_REFERENCE.md and PERFORMANCE.md contain settings, measurements and caveats. No additional model or dependency was installed for this handoff.

## Access and ownership

Claude can read tracked source and this record through existing repository access. GitHub alone cannot grant access to local weights, identity, logs, Documents, generated media or the Python runtime. Those remain ignored and local. A collaborator needs its own authorized laptop session to inspect them. This update publishes documentation; it does not send a message to Claude or prove Claude has read it. Preserve collaborator changes and inspect the current branch before edits.

<!-- PAGE -->
# Latest evidence and next work

## Auto latency fix

The classifier's 2,048-token context caused same-model reloads before the 8,192-token reply. All app call paths now share 8,192. In the measured second Auto greeting, wall time fell from 19.0002 to 0.7877 seconds and summed loading from 17.6694 to 0.0620 seconds. One runner stayed loaded. Cold/manual/document results varied; this is one short before/after experiment, not a broad speed guarantee. Normal thinking remains enabled. Numeric timing logs exclude prompt, reply and reasoning text.

All 291 offline cases across sixteen suites and five native Windows/Tk suites passed on the verified runtime. No application tests were rerun for this documentation-only change. Earlier failures remain recorded, including the four-load regression, stale-edit controls, quoted-append errors and video memory failures. These checks do not replace the formal scorecard: SCORECARD.md still has no run rows. The earlier 28/28 document qualification and 8/8 controls cover small synthetic tasks and do not establish an overall model rating.

## Watermark check completed October 20

A real local LTX waterfall clip completed in 103.0 seconds. It decoded all 65 frames at 384x256 and 24 fps: 2.7083 seconds, 389,894 bytes. Every frame was inspected using native-resolution contact sheets; no visible watermark, stock logo or text overlay was found. This finding covers that clip only, not invisible markings or future generations. No watermark-removal operation was performed.

Local output: C:/dev/local-ai-agent/generated/6911e3b1110a4bbfa6f67b768c5a139d.mp4. SHA-256: 11194913407d4e1dab2a771b3bb6009f9c7b15282d77ecd082857990afd89aa2. It can be reopened through Artifacts > More > Open generated image or video. work/watermark_video_review/generation.json and all decoded frames/contact sheets retain the evidence locally; the media are not uploaded with this document.

## Evidence map and unresolved work

- Latest runtime/test evidence: outputs/local_studio_context_reuse_BUILD.json, work/context_reuse_offline_final.json and work/context_reuse_native_final.json. Raw measurements: work/context_reuse_baseline_2026-10-20.json and work/context_reuse_fixed_2026-10-20.json. Their baseline commit fields reflect when measurement occurred; the build manifest identifies the fixed source later published verbatim.
- Voice/reference evidence: outputs/local_studio_voice_reference_BUILD.json and VOICE_AND_REFERENCE.md. Peak memory is sampled; Windows/driver activity can still cause refusal. Video quality remains experimental.
- Next validation: score main at an explicitly identified main checkout/commit before considering merges; record every failed scorecard step permanently and use new rows for later attempts. A feature-branch launcher does not test main. Separate regression tests above do not count as scorecard runs.
- Remaining product work: broader unseen/multi-turn tests, a person-operated microphone trial, better video quality and additional narrow app adapters. Full desktop control is incomplete. Private remote text/image/video access remains a roadmap in REMOTE_ACCESS_PLAN.md; no login, web server or remote computer-control endpoint is implemented.
- Storage: old runtimes, model caches, saved files and other collaborators' processes were retained. Previously blocked cleanup was not retried. No disk space was reclaimed by this handoff.

<!-- PAGE -->
# Efficiency review and reproduced fixes

## Current branch and review scope

This October 20 review builds on runtime/documentation baseline f1215c9e7e01522a08988d4d589f8a6c399fbd41. The new branch is codex/efficiency-review-2026-10-20, stacked on draft PR 7. Its PROJECT_RECORD.md is the current shared record; EFFICIENCY_REVIEW.md contains the detailed findings, before/after table and remaining priorities. Main was not merged. The primary C:/dev/local-ai-agent installation is updated after verifying the published source against the tests. Restart with the existing start_media_studio.cmd launcher to import the changes.

The review traced model routing, conversation compaction, Artifacts import/selection/playback, worker cancellation, generation admission, speech, filesystem workers and browser interception. It is a scoped engineering review, not proof that every bug is found or a completed security audit. No tool authority, dependency, model, prompt-approval rule or GPU generation profile was added or loosened.

## Reproduced bugs and changes

An imported image/video was decoded during validation and twice again during selection. Validated frames are now reused. Obsolete previews receive their own cancellation and discard late pixels. Rapid pause/resume cancels the old frame timer. An import finishing after a new human editor change now preserves that text and leaves the imported Artifact available in the list.

Stop is checked after compaction, before reply inference, after a late reply, and after generation waits for its GPU lease/RAM admission. Empty model replies now return an error, and missing display text cannot crash the formatter. Empty, truncated, action-bearing or oversized summaries are refused before replacing history. Tool-call arguments now count toward history estimates and summary input. Empty/truncated media interpretations are refused without saving a partial observation. Failed output is not automatically retried.

## Measurements and verification

The same synthetic native fixture ran against preserved unmodified baseline and fixed sources. For both JPEG and MP4 imports, decoder jobs fell from three to one; maximum concurrent decoders fell from two to one. JPEG first visibility measured 1.2495 to 0.6092 seconds; MP4 measured 1.3627 to 0.8821 seconds. Rapid pause/resume left two timers before and one afterward. New unsaved text and selection cancellation failed on baseline and passed after the fix.

These are short local timing samples, not guarantees or measured peak-RAM savings. All twelve new offline cases failed on baseline and passed afterward. All 303 offline cases across seventeen suites and six native Windows/Tk suites pass. Raw failures and results remain in work/efficiency_baseline_run.json, work/efficiency_ui_baseline.json, work/efficiency_ui_fixed_final.json and work/efficiency_checks_final.json. No Internet, inference, microphone or personal files were used in these checks. SCORECARD.md is unchanged and remains unrun.

## Remaining priorities

Run the fixed scorecard on an identified main checkout before considering merges. Improve context budgeting for system/tool schemas and generation: characters/4 is still approximate, and current-turn batches cannot always compact. Measure mixed real workflows using the existing timing logs. Cancellable model/browser I/O and asynchronous browser shutdown remain unfinished; Stop cannot forcibly interrupt their active synchronous calls. Profile long editor/chat content before adding bounded caches. Full computer control and private remote access remain separate unfinished work. No new whole-chat or GPU-rendering speed claim is made here.

<!-- PAGE -->
# Public checks and student-owned next work

## Scorecard status: prepared for later

The exact merged main revision 58adaf433d108c7b98703b4c0cd0b0c1331fb595 was exported into an isolated scorecard window with separate Documents, generated output and audit paths. It uses the existing local runtime/cache; no model was downloaded. Computer-use initialization failed twice with "failed to write kernel assets: The system cannot find the path specified." No prompt was submitted and no action or approval occurred.

Alexander explicitly chose to run it later. The idle test window was closed to release resources, and outputs/start_scorecard_main.cmd can reopen it. SCORECARD_RUN_GUIDE.md retains all five exact prompts, fresh/continue chat order, source verification, grading and evidence instructions. SCORECARD.md's criteria and empty Results table are unchanged. Setup failure is neither an app pass nor an app fail.

## Eight adversarial pages and reproducible CI

Eight inert local HTML fixtures attempt downloads, settings access, system-role spoofing, skipped consent, forged approval arguments, POST search, plan-scope escalation and synthetic data exfiltration. Their bytes pass through the real pinned route handler using fake HTTPS, then scripted model calls attempt the attack through production dispatch. Each records its page hash, refusal event, approval requests and pass/fail. All eight passed.

These are deterministic code-boundary tests, not evidence that a live model resists injection or that real popups displayed. No browser, Internet connection, settings app, microphone or model ran in them. PROMPT_INJECTION_TESTS.md explains the scope.

The Windows/Python 3.12 workflow runs all eighteen offline suites on every PR and main push. It uses lean pinned dependencies, full action commit pins, a read-only token, per-suite deadlines, a Python socket/DNS tripwire, explicit suite classification and retained failure logs. No Torch, GPU packages, browser download or model weights are needed. All eighteen suites passed locally in both the existing and fresh lean environments, totaling 311 cases.

GitHub-hosted Windows run 39484591531 passed its installation, all offline suites and artifact upload for commit d4d68a51b3380608773323003457d8d496232aa6. That public run is independent of the local assertions. The tripwire is a test aid, not an OS network sandbox. Ten native/GUI suites remain separately classified; the scorecard is not a CI test.

Hosted evidence: https://github.com/arowsom-oss/local-ai-agent/actions/runs/39484591531

## Alexander's authorship and shared handoff

Alexander chose to write THREAT_MODEL.md and the next small fix himself. SECURITY_WORKBOOK.md supplies code line references, asset/attacker/boundary questions, limitations and test pointers. No finished threat model or human-authored commit was invented. The confirmed, deliberately unfixed candidate is Copy last answer using display-cleaned last_answer instead of the preserved raw reply, changing code fences and literal formatting. Alexander can reproduce, fix, test and explain it, then request review.

Draft PR 9 on codex/scorecard-injection-ci-2026-10-20 stacks on PR 8. This update changes tests, CI and documentation, not application runtime. Main is unmerged. The current shared record and workbooks are on that branch; the local PDF matches it. Earlier privacy, resource and unfinished-computer-control limits remain.

<!-- PAGE -->
# Research from a topic without a pasted link

## Missing capability and implementation

The earlier browser_search could only use a numbered GET form on a page already opened. There was no topic-to-source discovery tool. browser_web_search(query) now builds a fixed DuckDuckGo Lite GET URL, navigates through the existing guarded browser and returns untrusted snippets and numbered links immediately. The model can choose a recorded result, open it and read its contents. The opened-source observation includes its full URL for citation. browser_read still accepts no arguments. Prompts and specific refusal guidance explain the sequence and stale-number rules; those instructions grant no authority.

## Code boundaries and approval

Queries allow 1-100 printable characters, must not be blank and refuse @, seven consecutive digits and ! shortcuts before any popup. Strict dispatch rejects model-supplied URLs, providers or approval flags. A new provider needs site approval; every query always needs its separate exact text/provider/full-URL approval, even inside a plan. No remains the default. Pattern checks cannot recognize every secret: the person must review outbound text.

Only the known result wrapper on the exact Lite page is decoded once from a recorded link. No redirect is fetched and no target is trusted by decoding it. Destination syntax, approvals and public DNS/IP pinning still apply. JavaScript, service workers, POST, downloads and redirects remain blocked. Browser threading, response/page budgets and redacted persistent auditing remain. Stop after synchronous search navigation prevents the following automatic read. No new package, model or broad computer capability was added.

## Evidence and failures retained

All 325 offline cases in eighteen suites pass in the lean Windows/Python 3.12 environment; fourteen cases are new. The real headed Chromium fixture passes with fake HTTPS for search, decoded recorded links and pinned source opening. The eight injection fixtures still pass.

A live Lite request returned ten relevant links; the HTML endpoint returned a challenge and is not an automatic fallback. Early e2b research trials used a wrong read argument, answered from snippets, or reused stale numbers and reached the round limit. Their reports were retained. Guidance and source-address observations improved the flow. A later two-fact reply included a detail not independently verified in its excerpt; it is not a fully verified research result. Subsequent one-fact e2b and Auto probes searched, opened/read NASA and cited a page-supported fact without an initial URL. Auto selected e2b and recovered from a refused search-box click.

These public synthetic probes used constrained test approval callbacks, not real human popup decisions; no hidden reasoning or private query was retained. WEB_RESEARCH.md describes evidence, manual checks and limits. Search availability, provider markup, poor source selection, hallucinations and the 4000-character read limit remain. Chromium routing is not an OS sandbox.

## Shared handoff

This branch stacks on codex/scorecard-injection-ci-2026-10-20 and remains unmerged. The normal app needs a restart to load updated Python. The main scorecard remains prepared for later with no new score or invented result. Alexander still owns writing THREAT_MODEL.md and the deliberately unfixed copy-button bug; historical workbook line references are identified as historical. Existing models, ignored identity, caches and saved work are preserved.

<!-- PAGE -->
# Next ten improvements and the first measured change

## October 21 priorities

The app routes work between separate installed local models. It has not fused their weights or implemented expert-weight streaming. Earlier gains removed context-driven reloads and repeated media decoding. IMPROVEMENT_ROADMAP.md separates completed work from the following open priorities.

1. Faster simple replies: exact bare greetings can skip the classifier. Implemented and measured in this update.
2. Context budgeting: account for system text, tool schemas, history, current results and reply space; compare estimates with actual prompt counts.
3. More responsive Stop: cancel active model/browser work without abandoning owner threads or allowing concurrent inference.
4. Source verification: separate snippets from opened/read sources, expose evidence gaps and evaluate factual support.
5. Failure recovery: useful guidance and bounded pauses for wrong arguments or stale targets, preserving exact approvals.
6. Memory diagnostics: show measured RAM/VRAM, active model and unload status; distinguish samples from ceilings and estimates.
7. Fewer repeated reads: profile first; bounded reuse needs target identity, revision/hash and invalidation on changes.
8. Media status: show actual queue/running/encoding/delivery stages without invented progress or parallel heavy jobs.
9. Mixed benchmarks: fixed synthetic chat/research/document/media tasks with latency, failures and resource samples.
10. Human scorecard: run unchanged main criteria when Alexander is ready; retain every result before considering merges.

<!-- PAGE -->

# Faster greetings: implementation and evidence

## Completed: narrow greeting shortcut

A whole ASCII greeting of at most 40 printable characters can skip classification: hi, hello, hey, good morning, good afternoon or good evening, with ordinary surrounding spaces and one optional final punctuation mark. Task suffixes, hidden/control characters, Unicode lookalikes and follow-ups do not match by prefix. Image/document hints and a retained reasoning model still take precedence, avoiding unnecessary model switches.

The real reply inference remains, with the full system/tool menu, think=True, shared 8192 context, installed-model checks and all approval/dispatch gates. Missing models return an error; no canned reply or download was added. No UI, media worker, tool authority or model weights changed.

## Evidence and limits

Before and after, the actual run_turn path used one warm-up and six alternating Auto/manual pairs with fresh message lists and a fixed public hi prompt. All tool actions were refused by a test-only argument gate; none were proposed. Logs retained numeric timings, route labels and reply lengths, excluding answer and hidden-reasoning payloads. Auto median fell from 0.7873 to 0.5053 seconds, a 35.8% reduction in this narrow sample. Manual medians stayed similar at 0.5219 and 0.5112 seconds. All six Auto trials went from two inference calls to one.

This is a short sequential greeting benchmark, not a general speed, quality, cold-load or memory claim. The extra call was reproduced before editing runtime. Five new cases then passed, along with all 330 offline cases in eighteen suites and the injection fixtures. A non-greeting prompt preserves the old classifier/context-reuse regression. Published numeric traces and a reusable benchmark script accompany the roadmap. No native UI change was made or claimed tested anew.

The branch stacks on topic-web-search and remains unmerged. Restart the normal app to load changed Python. The main scorecard stays deferred and unchanged. Alexander still owns his threat-model writing and the deliberately unfixed copy-button task. Context budgeting is the next implementation candidate; the other listed items remain planned.

<!-- PAGE -->
# Separate Edge work profile and personal-tab handoff

## Alexander's chosen scope

Alexander asked for both existing-tab reading and website interactions, then chose a separate Edge work profile for the AI. Clicks and typing are confined to the app-owned work browser. Personal Edge tabs can be explicitly shared for reading or copying an address; they cannot receive model clicks or typing. Personal cookies, passwords and profiles are not imported. The existing stateless read-only browser remains separate.

The app's Edge tab panel starts the dedicated work browser, lists only its tabs for person selection, and offers the optional personal-tab connector. The owned browser uses edge_work_profile/ inside the app folder, which git ignores. Its cookies and site data persist across restarts. Stop, New chat and Disconnect revoke access and close only the owned browser; they do not delete that profile or kill personal Edge.

## Approved operations and state checks

Work tools open exact HTTPS addresses, read page text and regular text-field values, use fresh numbered links/buttons, replace one regular text field and scroll a bounded viewport step. Each operation has its own No-default preview, even inside a plan. Password, file, email and known credential/payment-code fields are excluded. Text is bounded and rejects @ and seven consecutive digits; these patterns do not identify every secret. No model API accepts a PID, profile, selector, coordinates, script, file path or approval ticket.

A fixed DOM helper runs in a private isolated world. Website scripts cannot edit its control map or steal pending tickets. URL/text/control snapshots and one-use, expiring tokens are checked before actions. Numbers continue across documents and distinct sessions receive separate ranges. Covered, hidden, disabled and offscreen controls are not numbered. Reads after a change provide new targets; denied or failed work pauses rather than replaying queued actions.

## Network, profile and file boundaries

The work browser enables page JavaScript while Python still fetches its HTTP traffic: public-IP checks, pinned-IP HTTPX connection, original Host and TLS SNI, no proxies or automatic redirects. Work cookies stay in the work context. GET is allowed; an approved click/type commit grants a five-second same-origin POST window. This is origin/time scoped, not consent bound to each individual POST body. Website effects and server-side completion remain unverified.

Other methods, cross-origin POST, multipart/binary upload bodies, redirects, compressed responses, attachments, WebSockets and service workers are blocked. Request bodies cap at 256 KB, responses at 5 MB/10 seconds, and a page/action budget at 250 requests/20 MB. Downloads are not accepted and file choosers select nothing. HTTP pinning is not an OS network sandbox for Chromium background traffic or every non-HTTP browser feature. Long synchronous calls may finish after Stop, and already-dispatched effects cannot be undone.

<!-- PAGE -->
# Edge setup, evidence and remaining limits

## Using the feature

Restart the normal app, choose Edge tab, then Start work Edge and review its popup. Open a site in that separate window and use Choose a work tab, or ask the AI to open an exact HTTPS address. Ask it to read the work tab, then propose one numbered action. Review each exact preview and read again to check visible results. The separate profile needs no extension and uses the existing installed Edge/Playwright runtime. It is not a VM or an anonymous identity.

For a page already open in personal Edge, one-time manual setup is needed: open edge://extensions, enable Developer mode, choose Load unpacked and select C:/dev/local-ai-agent/edge_extension. In Local Studio choose Share a personal Edge tab (read/handoff), then select the source tab in Edge and click the extension icon. Enter the fresh pairing code and Share selected tab; keep that connector window open. Each read or address handoff still needs app approval. A copied address does not carry its login into the isolated browser or work profile.

The extension uses activeTab/scripting and loopback access, without all-websites, cookie, history, download or debugger permissions. Its local relay accepts a bounded authenticated protocol on 127.0.0.1, with a random RAM-only bearer secret, exact extension Origin/Host checks, one tab, command IDs, expiry and heartbeat. The model never sees the code. This is not remote access from school. EDGE_BROWSER.md has the complete setup and API references.

## Verification and failures retained

All 353 offline cases in nineteen suites pass, including twenty-three new Edge cases for dispatch, approvals, identity/transport, source-only limits, private data patterns, public-IP/Host/SNI fetching, cookies, POST gates and response limits. The eight injection fixtures still pass. The new native suite is classified separately from CI; eleven native suites now exist.

A real headed Microsoft Edge fixture uses only an owned temporary profile and synthetic HTTPS through production HTTPX routing. It verifies two response cookies, private DOM state, text read-back, typing/buttons, snapshot invalidation during approval, stale numbers after navigation, blocked attachments/downloads, file chooser interception, scrolling, different caller threads, tab selection and cleanup. A real Chromium extension fixture verifies authenticated relay pairing, personal-tab reads/address handoff, changed-page refusal and disconnect. A fixture-only host grant substitutes for the human activeTab gesture, so actual extension installation and toolbar permission remain manual checks. A native Tk fixture verifies full exact URL/text previews and Return defaults to No.

Early tests retained failures about user activation, fixture script routing, offscreen-text assumptions, download event timing and a failed-navigation race. The final code preserves a failed tab for review and avoids racing its error navigation with the next approved open. No personal tab/account, Internet site, Ollama inference or human scorecard prompt ran in these fixtures.

## Limits and shared handoff

Redirect/SSO flows, WebSockets, cross-origin forms, large media, iframes, shadow DOM, rich-text/canvas controls and changing SPAs may not work. A button label cannot prove its remote effect. Manual installation, sharing and a real chosen website still need Alexander's review. The branch stacks on efficiency-roadmap and stays unmerged. The main scorecard remains deferred; Alexander retains authorship of the threat model and deliberately unfixed copy-button task. No model weights or personal browser data were published.

<!-- PAGE -->
# First Edge test: voice and interface repairs

## Report and changes (October 21, 2026)

Alexander's first work-profile trial opened Edge, but edge_read returned "Edge timed out; work browser is stopping" after a 28.13-second overall turn. He also reported repeated dictation popups, a lingering Edge setup panel and a model dropdown that did not work. Main was clean at merge 526497f when this repair branch began; no existing working files were overwritten.

Talk now starts its bounded recording directly. The transcript enters an empty message box without another dialog, ready for editing and an explicit Send. It never sends itself or replaces an unsent draft. Stop still discards the result. Spoken-output consent is unchanged. These controls remain person-only; no new microphone tool is offered to the model.

The native model menu opened while idle, but code disabled it throughout recording, media jobs and replies. It now stays selectable. A running turn retains its captured model; a later selection applies to the next message. The label says "Next message model". The Edge setup panel is reused and closes after Start approval, choosing a tab or Disconnect. The optional personal connector window still stays open when that mode is used.

## Timeout handling and evidence

Previously each routed request could block the Playwright owner in DNS and HTTP, competing with its 15-second command timer. A single bounded helper now receives copied request data only and performs public-address checking plus pinned HTTPX. Only the Playwright owner fulfills/aborts routes. An eight-second network window per approved navigation or click/type bounds the wait; reads do not renew it. Failed responses conservatively keep their byte reservation. Redirect, upload, response-size and exact-action approval restrictions remain. Snapshot equality uses the exact bounded serialized state synchronously instead of an asynchronous crypto promise.

All 354 offline cases across 19 suites pass. Native speech/reference tests verify popup-free dictation, unsent-draft/Stop protection and selecting an actual dropdown option during a reply without changing that turn's model. Native Edge/connector/Tk fixtures pass, including a deliberately stalled secondary DNS request: it is aborted while page reading succeeds and the browser stays open.

Two retained offline runs failed because old tests required the removed popups; those expectations were updated. One public example.com open/read returned visible documentation text promptly, but its harness failed an outdated heading expectation; that failure is retained. This was not a live model or person-approval test. The exact cause of Alexander's original timeout remains unconfirmed. Slow pages may load incompletely. Python cannot forcibly cancel Windows DNS: a retired helper must exit before a new work browser can start. Personal Edge remains read/handoff only. No scorecard result or model-quality score is invented.

<!-- PAGE -->
# Popups that close safely

## Alexander's report and scope

After another lingering popup, Alexander asked for every popup in the app to have an obvious way to close it. The inventory covers exact approvals, image/reference previews, ordinary decisions, Edge setup/tab selection/pairing code, Activity/audit, task details, Saved Documents, the optional extension connector, native file/text choosers and dropdown lists. This branch starts from the prior tested UI repair commit 02d48b9. Its core tool permissions, network adapter, model router, scorecard and student-owned copy-button fix are unchanged.

Every custom utility panel now has a reserved footer with Close or Cancel, Escape and a title-bar X. Footer space is allocated before expanding content. Long Edge tab lists scroll and empty lists retain Cancel. Windows monitor work areas bound placement; negative coordinates use absolute Tk geometry syntax. Modal cleanup releases grabs after exceptions and restores an enclosing modal. Closing Documents before its listing returns no longer touches a destroyed view. Repeated panels are reused or replaced.

A real Windows Yes/No fixture remained open after WM_CLOSE. Rather than depending on that OS dialog's X behavior, ordinary decisions now use a small app-owned, scrollable No-default shell. This covers New chat, capture/model checks and discarding an unsaved Artifact edit. No, Escape, Return and X all cancel. Tests verify that chat history and unsaved edits survive, and cancelled capture/check paths do not run. Exact action approvals retain their independent explicit Yes requirement. Image-preview cancellation rejects the image.

The optional extension has an always-accessible Close connector button and Escape handler. They stop polling, revoke sharing and close its owned popup, with a bounded wait if the relay is unavailable. Ordinary browser title-bar closure expires through the existing heartbeat. Closing only the pairing-code display hides the code; it does not revoke an already shared personal tab. Stop and Disconnect remain the controls for that.

## Tests and retained failures

All 363 cases in 20 offline suites pass. Nine affected native suites pass after the final visual changes: Artifacts, Edge/connector, efficiency UI, popups, progress, speech, vision and both Documents suites. Checks include all nine custom popup types, actual Open/Save cancellation, text-prompt cancellation, long/empty content, a short monitor, nested grabs and late results. Model, Artifact and version dropdowns dismiss with Escape without triggering Stop.

The earlier broad native run passed 11/12 suites. Its global stop shortcut registration was unavailable while another process held it; that failure remains recorded. The remaining owned practice UIA and hard-stop cases passed separately. Windows native-menu automation using Tk synthetic events was unreliable, and an icon-getter assertion was platform-specific; those harness attempts remain in local evidence. No other running app was killed to free a shortcut. This is not an exhaustive Windows audit or a guarantee for every monitor/provider.

<!-- PAGE -->
# A calmer interface and original app identity

## Design direction

Alexander also asked for less clutter, more uniform presentation and Apple design inspiration. Apple's Human Interface Guidelines on layout, modality and alerts informed the use of hierarchy, restrained color, whitespace and discoverable dismissal. This remains a native Windows/Tk interface using Segoe UI. It does not copy Apple logos, fonts, platform claims or expensive glass effects.

Light and dark themes now use neutral surfaces with one blue accent. Panels share typography, spacing and a consistent close footer. Only one utility panel stays open at a time; opening another replaces the earlier view. Exact approval dialogs remain separate because their purpose is an explicit decision. Browser approval copy keeps the destination, precise text changes and relevant website effects, while implementation details live in documentation.

Routine tool messages and timing metadata now stay in More > Activity rather than interrupting the conversation. Its This chat tab retains the latest 100 bounded entries in RAM; Saved audit remains separately available. New chat clears the transient activity. Refusals and errors still appear in the conversation. Tool results sent to the model, audit redaction and action approval policy are unchanged. Read-only activity text never becomes executable content.

## Icon and launch behavior

An original logo was created with the built-in image generation tool: three rounded blue ribbons around a central negative space on a charcoal app tile. Only format/size conversion followed generation. The project bundles a transparent 256-pixel PNG and an ICO with nine sizes from 16 to 256 pixels. The exact prompt and provenance are in assets/README.md; the original generated source is retained locally. The app sets its Windows process identity and real window icon, including popup inheritance.

The Local Studio shortcut uses the app's existing pythonw runtime and bundled ICO. It launches the primary source folder without a console. Python source-file associations and registry settings are unchanged; double-clicking a .py file can still show Python's icon. The shortcut installer refuses to overwrite an unrelated existing shortcut. No model weights or Python dependencies were added.

## Evidence and handoff

Native checks verify the actual Windows icon handle and explicit application identity, Activity routing and replacement of an earlier utility panel. Light/dark main-window, browser-panel and Activity previews were rendered and visually inspected using synthetic chat and Artifact content. They are not model outputs or a claim of macOS-native widgets. UI_DESIGN.md contains the popup inventory, close semantics, Apple references and the retained test limitations. A fresh app restart is required to load these changes. The human main scorecard is still deferred; no score or model-quality result is invented.

<!-- PAGE -->
# Future website creation and visual previews

## Alexander's request - October 22, 2026

Alexander reported that a website request received a refusal and no Artifacts sidebar appeared. He asked to record website creation as future work and wants code to become something he can see. The exact exchange and tool trace have not been captured; this is not a reproduced panel bug or a scored model failure.

The current app can create code Artifacts, including website source, but HTML and scripts stay inert text. The Artifacts pane opens when a stored Artifact arrives. A plain chat answer or refusal does not create one. The main sidebar also has an Artifacts button; More > Draft from last answer can preserve a response as text. There is no HTML renderer in this version.

## Proposed first step: Code / Preview

Add a person-controlled visual preview beside source code for a single-page HTML/CSS Artifact. Render the selected revision in a bounded, isolated offline renderer and show the result in the pane. An initial screenshot preview is a possible design, not an implemented feature. Scripts, all external resource loads, navigation, forms, popups, downloads and filesystem access must be denied. Generated source must not gain a Python bridge or personal Edge profile. Renderer isolation and interception need real Windows evidence before these limits can be claimed.

Preserve source editing, unsaved drafts, exact revisions, history, Stop/New chat cleanup and explicit saving approvals. Test visible layout with an actual native fixture and hostile offline pages for scripts, CSS resource loads, file URLs, frames, forms, navigation and oversized content. A model smoke request must actually create the Artifact and display it before the feature is called complete. This work does not run or change the deferred main scorecard.

## Later scope and handoff

Interactive JavaScript, multi-file projects and website export can follow verified static previews. Public hosting needs a separate destination/credential policy and explicit publishing approval. Writing code, rendering a local preview and publishing a website are separate capabilities. General Python or shell execution is not part of this request.

WEBSITE_PREVIEW_PLAN.md contains the proposed acceptance checks and current limitations; IMPROVEMENT_ROADMAP.md links this future item. This is a documentation-only update with no new renderer, dependencies or execution authority. Earlier tests remain historical. Alexander retains authorship of the threat model and his small copy-button fix.

<!-- PAGE -->
# Visual website Artifacts: Preview first

## Implemented behavior - October 22, 2026

Alexander asked for a visible button rather than a hover-only control, with the result shown first and a way to switch to code. HTML/CSS code Artifacts now open their visual Preview automatically. Explicit Preview and Code buttons sit above the content. A new HTML Artifact selects itself unless an unsaved editor buffer needs preserving. Documents keep Text; images and videos keep their existing previews. Python, standalone JavaScript/CSS, SVG and other code stay source-only with a clear unsupported-preview message. This is not an all-language code runner.

The preview is a scrollable picture of an 800 by 1000 pixel browser viewport, fitted to the pane width. It shows HTML/CSS layout, colors and controls, but those controls are pictures. The person can switch to Code, edit the source, and press Preview without saving. The preview identifies an unsaved draft or selected historical revision. Save edit retains the existing version checks. Source, history and explicit non-overwriting .txt export stay available. Publishing is not implemented.

## Rendering boundary and limits

A bounded HTML parser retains display elements/styles and removes scripts, frames, embeds, metadata navigation and URL-bearing attributes. A fresh headless Chromium instance renders only a fixed synthetic document fulfilled by code. Every other route aborts. Independent controls disable page JavaScript, downloads, service workers, permissions and network use; a response-header Content Security Policy restricts scripts, resources, forms and navigation. Browser background-network flags and a failed proxy add defense in depth. No personal profile, Python bridge, arbitrary evaluation or model-provided command is used.

Only immutable PNG pixels reach Tk. Source remains limited to 32,000 characters and 2,500 parsed start tags. A Windows Job Object bounds the owned worker/browser tree to 1,536 MB committed memory; receive has a 20-second deadline, with at most five seconds waiting for a previous preview to stop. One render runs at a time. Stop, Code, selection changes and New chat cancel work; serials reject late pixels. These are application/browser controls and an owned process-tree bound, not a proven OS network sandbox or a claim that Chromium has no vulnerabilities. External images/fonts and interactive JavaScript do not work in this first preview.

## Evidence, failure and handoff

All 369 cases in 21 offline suites pass under the socket/DNS tripwire. Actual Windows fixtures verify expected HTML/CSS pixels, visible buttons, unsaved text, history, supported/unsupported selection, stale-result rejection, Stop and New chat. A hostile document also bypassed the HTML reducer in a test of the independent browser policy; scripts did not change its background and its local canary server received no requests. Existing Artifact image/video, efficiency and popup native suites pass. A synthetic preview screenshot was visually inspected.

The first full-runtime native attempt returned the generic worker failure; its exact cause was not established. Direct renderer and bounded-worker probes passed, followed by successful lean-runtime and full-runtime native runs. This failure is retained, not called a fixed root cause. One actual gemma4:e2b smoke request used the normal core with non-Artifact actions refused: it called create_artifact, produced one code Artifact and opened Preview in 16.72 seconds including a cold model load. This single example does not establish general website quality. The main scorecard remains deferred. Restart the Local Studio shortcut to load the feature; the draft PR is not merged.

<!-- PAGE -->
# Private access from school: plan update

## Requested experience - October 22, 2026

Alexander asked to add a private website connected to his laptop AI to the plan. He wants to open an address from school, sign in, and use chat, image/video generation and his Artifacts while the Acer does the work. The remote-access plan now states this explicitly. It remains a proposal: no server, tunnel, account or firewall change has been created.

The browser-only option should use a reviewed HTTPS gateway with one provisioned owner and no public signup. Password/passkey support, MFA, expiring sessions and sign-out should work on a shared browser. The address is only a link, not proof of identity. Every chat/job/media request must check the owner, including preview, cancellation and download. An emailed one-time PIN alone is not automatically MFA. A gateway identity token must be validated rather than trusting a caller-supplied email header.

## Connectivity and capability boundary

Cloudflare Tunnel with Access is a browser-only option to evaluate; Tailscale Serve is an alternative for devices allowed to use its private-network client. No provider is selected. Do not expose Ollama, a development server or the desktop app directly. Inference stays local, but a gateway transports traffic and may terminate HTTPS; this is not a claim of end-to-end secrecy from that provider. School policy may still prevent access.

The remote MVP offers text chat, explicit image/video requests, job state and owned media only. It has no computer control, screen capture, browser automation, shell or arbitrary-file browsing. The server must enforce that boundary independently of model output. A mobile-friendly gallery can reconnect to a job after a connection drop without generating a duplicate. The laptop must remain awake, online and running; the page must say offline when it is unavailable.

Saved owner-bound chats/jobs/media and one shared local/remote GPU manager are prerequisites. A separate Python process cannot copy the desktop lock and assume it coordinates GPU use. Deployment needs authenticated loopback integration, owner/session/CSRF/media tests and a reviewed tunnel configuration before a second device is connected. Remote document imports or website previews need their own bounded adapters; the current desktop tool dispatcher is not reused remotely.

REMOTE_ACCESS_PLAN.md contains the expanded requirements and primary connectivity references. This notes update does not implement the portal, change installed models or run the deferred human main scorecard.

<!-- PAGE -->
# Assistant features and useful model candidates

## Product priorities

Alexander also asked what would make the app more useful like ChatGPT or Claude. The proposal focuses on saved searchable chats and Projects, Q&A over selected PDFs/notes with source pages, streamed visible replies and honest timing/Stop controls, opt-in inspectable memory, better code editing and static previews, source-backed study tools, and research with opened/read citations. These improve the product experience; they do not claim the local model matches a hosted frontier model's reasoning quality. PRODUCT_FEATURE_PLAN.md records scope, acceptance checks and suggested order.

Saved chats and context/cancellation reliability should come before the remote portal. Selected-document retrieval follows. Retrieved files and remembered facts never become tool authority; old approvals are not restored with a saved chat. Streaming must validate a complete tool call before dispatch and must not display hidden reasoning. The existing static Preview / Code feature is delivered; multi-file and interactive execution remain future work.

## Model research, checked October 22

Primary Ollama pages list qwen3-embedding:0.6b at 639 MB, qwen3.5:9b-q4_K_M at 6.6 GB, qwen3.5:4b-q4_K_M at 3.3 GB and glm-ocr:q8_0 at 1.8 GB. These are rounded download sizes, not measured RAM/VRAM. The embedding model produces vectors for searching approved documents; it does not answer chats. Qwen3.5 is a multimodal/tool-capable candidate for an A/B against Gemma on coding, reasoning and selected images. The 4b version is a smaller alternative, not an additional required resident model. GLM-OCR is optional for scanned text, tables and formulas if current extraction proves insufficient.

For the 12 GB VRAM/32 GB RAM laptop, test one heavy GPU job at a time with the existing 8192-token context. Runtime workspace, context cache, image tokens and Windows use require additional headroom beyond weight size. Installation alone does not consume all models' VRAM at once. No new candidate has been downloaded, integrated, benchmarked or proven better than the current Gemma models. No new memory or latency figure is claimed.

Keep Gemma as the default while comparing fixed synthetic task success, tool/schema refusals, cold/warm timing, sampled memory and model/media handoff. Verify installed Ollama/backend/client compatibility and exact tags/digests. Embedding/OCR work must join the same lifecycle policy rather than bypass it. Source links and rollout gates are in PRODUCT_FEATURE_PLAN.md. This is research and documentation only; no runtime file, model allowlist, scorecard result, permission or student-owned fix changed.

<!-- PAGE -->
# Saved chats and Projects: first delivered stage

## Behavior - October 22, 2026

Alexander agreed to start the assistant feature plan. The first milestone adds Chats & Projects to the sidebar. A person can explicitly save a new copy, update the opened saved chat, search titles, reopen, export a transcript and delete a saved copy. Projects group chats and hold bounded reference notes. New chat in Project starts with those notes. There is no automatic conversation saving on every turn or exit.

The saved snapshot contains raw visible user/assistant text and every retained Artifact version, including immutable images/videos. Tool-call objects, tool results, hidden reasoning, system messages, approval decisions and browser sessions are not saved. An unsaved Artifact editor buffer must first use Save edit; chat saving refuses rather than silently dropping it. Updating checks the saved version and commits transactionally. List selection affects Open/Export/Delete; it does not retarget the independently opened conversation's Update button.

## Local persistence and controls

The fixed SQLite database is chat_library/library.sqlite3 beside the app, excluded from git. It is unencrypted local data under ordinary Windows file permissions, not an authenticated or encrypted vault. A title never becomes a file path. Stored input is schema-validated and SQL uses parameters. Chats are limited to 400 messages/1 MB transcript, 100 stored conversations, 20 Projects, 2000-character notes and the existing Artifact budgets. Encoded snapshots are limited to 96 MB and total retained payload to 256 MB, with an additional database page limit. Temporary journals and process memory are separate.

New chat clears RAM but keeps saved copies. Delete saved has a No-default prompt and removes only the selected stored version; open drafts and generated/exported originals remain. Removing a Project moves its chats to Unfiled. Deletion is not secure erasure and SQLite/backups may retain bytes. Export transcript uses a person-selected new .txt path and refuses overwrite; Artifacts retain their own export controls.

Database jobs run off Tk. Main chat actions wait while one is active. Close/Escape/X and a fixed footer/status remain accessible, with scrollable content for short windows. A late Open result cannot replace a chat after the library closes or Stop intervenes. An already committed Save/Delete/Export is not rolled back by Close or Stop. No model can invoke library operations, and no cloud service, model download or remote listener is added. SAVED_CHATS.md documents the limits and retry behavior.

<!-- PAGE -->
# Safe reopening and saved-chat evidence

## Fresh session, historical data

Snapshot validation completes before the active conversation is cleared. Reopening revokes/closes existing automation sessions, clears website/workspace permission, voice/media attachments, pending plans and task checkpoints, and assigns fresh Artifact IDs. If the browser cannot close, the old chat stays in place. Full saved text is displayed, but only a marked untrusted tail of at most 4000 serialized characters plus up to 2000 characters of Project notes is supplied as model context. Older details may be omitted. This is not unlimited memory, PDF retrieval or an executable replay of old roles/tools.

The person must send a new request. Restored and Project sessions use the existing core fresh-read gate before target-dependent changes. No model inference, tool action or spoken reply starts just because a saved conversation opens. Old numbers and claimed permissions in archived text remain stale. Project notes are reference data, not authorization.

## Tests, failures and limits

All 378 cases in 22 offline suites pass. Nine library cases cover a real fresh Python process reading stored text/history, immutable media, malformed/extra schemas, budgets, literal title search, stale updates/deletion, concurrent Library instances and corrupt/linked paths. Both new popup constructors and No-default prompts join the inventory. Ten affected native suites pass, including actual Tk library workflows, existing Artifact media/static previews, efficiency, popups, speech, vision, progress and both Documents suites. The library fixture also passes in the full app runtime. A synthetic library screenshot was visually inspected and short-window access checked.

Initial offline harness mistakes used a stat fake missing st_mode and the wrong core menu attribute; their logs remain. Native tests found two actual defects: reopening incorrectly requested a paused-task progress checkpoint, and Project removal left the list filtered by the deleted Project. Repairs separate core fresh-read enforcement from UI checkpoint resume and resolve a removed filter to Unfiled/all. Visual QA also found white controls and clipped Save content; themed entries/lists, a scrollable body and fixed status/footer were rechecked. These are retained failures, not erased or counted as initial passes.

One actual local gemma4:e2b smoke reopened a temporary synthetic saved conversation and correctly answered its stored fruit, with zero tool calls. It saved the continued four-message conversation as version 2 and took 12.47 seconds including cold model loading. This is not a broad memory/quality claim or a scorecard run. Main scoring remains deferred and Alexander still owns the threat model and small copy fix. Next work remains selected-document Q&A, context/cancellation improvements and measured model comparisons; the private portal is not deployed. Restart the Local Studio shortcut for this feature.

<!-- PAGE -->
# Weekly ZIP storage for unused saved work

## Delivered behavior - October 22, 2026

Alexander requested automatic ZIP storage after about a week unused. This first version covers the app-owned saved-chat library, including every embedded Artifact version and immutable image/video snapshot. It does not scan personal folders or Downloads, delete original generated PNG/MP4 files, compress model weights or externally ZIP the live database. ZIP compression saves disk space, not steady RAM/VRAM, and is neither encryption nor a backup. AUTO_ARCHIVE.md is the shared implementation and usage handoff.

Restart the app and open Chats & Projects. Auto ZIP saved chats unused for 7 days is enabled by default, with an off switch and Check unused chats now. The Storage column shows Plain or ZIP. The app checks five seconds after startup and hourly while open, skipping busy/stopped periods. There is no OS scheduled task after exit. Checks do not create a library or save an unsaved chat. A pass processes at most three eligible snapshots; tiny or poorly compressing candidates have a 24-hour retry backoff.

Opening or exporting records last use; save/update also restarts the clock. Listing titles does not. Both last use and update must be seven days old, and the currently opened saved chat is excluded. Existing databases get seven days of grace on first migration because historical last-open times are unknown. Opening an archived snapshot expands it only in memory and preserves ZIP storage; updating writes a new plain snapshot. Existing fresh-session validation, permission reset and stale-target rules still apply.

## Preservation and actual savings

Each ZIP has exactly one chat.json member inside SQLite; nothing extracts member paths to disk. Source-schema validation and byte-for-byte verified ZIP round trip finish before one transaction replaces the batch. The logical saved version and update time stay unchanged. A snapshot must save at least 4096 bytes and 5% or it stays plain. Corrupt, invalid or oversized ZIPs refuse before applying a restored conversation. Existing expanded Artifact limits remain; the 256 MB retained-library quota counts stored bytes and expanded encoded snapshots remain capped at 96 MB each.

The report distinguishes compressed-payload savings from actual database bytes reclaimed. SQLite compacts only after the ZIP transaction commits, with a temporary-space check, progress deadline and cancellation. If compaction cannot finish, committed ZIP data remains readable and pending compaction may retry later. Cancellation before ZIP commit rolls back the batch. Already committed storage changes remain after Stop or Close. Python never deletes or replaces the live database file itself. Ordinary SQLite transactions are not a promise against every crash or disk failure.

<!-- PAGE -->
# ZIP storage evidence and next stage

## Tests and retained failures

All 388 cases across 23 offline suites pass, including ten archive cases using temporary databases and injected clocks. Coverage includes exact bytes/history/media, fresh-process ZIP readback, last-use/current-chat exclusions, migration grace, toggle validation, batch/backoff bounds, cancellation rollback and failed verification. ZIP path/member/method/type/CRC and expansion-bound refusals are tested without extracting files. Deferred compaction preserves readable ZIP data and a later check reclaims its pages. Scheduler tests cover idempotent startup, absent databases, busy/Stop skips and captured active IDs. No archive capability is exposed as a model tool.

Three affected native suites pass: Library/Projects, popup behavior and Artifacts. Actual Tk controls persist the toggle, check inactivity, show ZIP badges, skip the current saved chat, export and reopen exact archived text/Artifacts, and update a ZIP snapshot to plain storage. The library fixture passes in both lean and full app runtimes. Its short-window fixture and owned synthetic screenshot were checked, including accessible fixed Close/status and themed storage controls.

One repetitive synthetic code/history snapshot saved 249399 payload bytes and reclaimed 249856 database bytes after compaction. The native repeated-notes example reclaimed 20480 database bytes. These synthetic measurements do not predict typical photo/video savings; PNG and MP4 originals are already compressed and untouched. No personal library or generated originals were archived during development. A real seven-day soak has not elapsed; tests inject old timestamps and exercise the same eligibility path.

The corrupted-deflate test initially raised uncaught zlib.error; decoding now normalizes it to a safe ValueError refusal. A migration fixture initially left its own SQLite connection open, preventing temporary-folder cleanup on Windows; it now closes and commits explicitly. The native fixture initially hid an unfiled example behind its Project filter; selecting All / Unfiled corrected the harness. The initial white checkbox appearance was themed and visually rechecked. Original logs remain; failures are not rewritten as initial passes. Prior milestone counts and model measurements remain historical. Human main scoring is still deferred.

## Recommended next work

Selected PDF and notes Q&A with page citations is the next product stage. Start with person-selected files, bounded parsing, source/page labels and answers that admit missing evidence. Treat document instructions as untrusted reference data and keep tool approvals separate. Use installed models first; add an embedding model only if a small retrieval benchmark demonstrates a useful improvement. The private school portal and broader Windows controls remain planned work, with no new model download or remote listener introduced here. Alexander still owns the threat-model writing and the small Copy last answer fix.
