# Efficiency and correctness review (2026-10-20)

All 303 offline plain-assert cases across 17 suites and six native Windows/Tk
suites pass. Twelve new cases failed on preserved f1215c9 baseline source,
then passed with the fixes. The native fixture independently reproduced
three decoder jobs per import, lost unsaved text, duplicate playback timers
and missing selection cancellation; the updated run uses one decoder per
import and passes these checks. EFFICIENCY_REVIEW.md records the scope,
timings and limitations. No new GPU inference benchmark or formal scorecard
run was performed; SCORECARD.md remains unchanged. Earlier results below
retain their milestone-specific scope.

# Generated-media Artifacts update (2026-10-19)

Based on `simple-ui` commit c3a82ae, preserving the collaborator's chat-first
layout, display-scaling changes and NumPy pin. The primary folder remains
`C:\dev\local-ai-agent`; model files and existing generated outputs are retained.

All 255 offline plain-assert checks passed across 14 suites, including eight
new generated-media cases. Four real Windows/Tk suites passed: Artifacts,
selected-media UI, task progress and saved Documents. The Artifacts fixture
uses scripted model/generation responses through actual core dispatch and real
PNG/MP4 decoding, selection and playback. No GPU inference is implied.

An additional native check reopened the primary installation's existing PNG
and MP4 through the new recovery action: the image displayed one frame, the
video decoded 16 frames and played, and both opened visibly in Artifacts.
No generation, download or source-file mutation was involved in that check.
The original refresh logic was also reproduced leaving new media unselected
when a document was already selected; the new regression covers that behavior.

The remote interface remains a documented roadmap in REMOTE_ACCESS_PLAN.md.
No authentication, web server, remote endpoint or remote-control capability is
implemented or tested by this change. Earlier validation below describes its
own milestone and is not replaced by this update.

# One popup per address, 2026-10-19 review

- Before: a brand-new site asked twice, new_site then outbound_request, both showing
  the same full URL, and an approved plan's open step asked again. Two popups per
  action trains you to click Yes without reading.
- Now: a popup that already showed the EXACT URL and got Yes covers it. That means the
  new_site popup, which now says Yes also sends this address, and a plan's open step.
  The audit log records outbound_covered.
- Plan open steps are refused before the plan popup if they have ? or #, are over
  300 characters, or fail the outbound URL check. Data can't hide in step 4 of 5.
- Still asked separately: other addresses on an approved site, fetch_page during a
  plan, off-plan opens even after Yes on plan_changed, searches and desktop actions.
- All offline suites pass on Linux. All seven Windows-only live suites passed on the
  laptop from C:\dev\local-ai-agent: workspace IO, workspace, desktop, Notepad,
  browser, vision UI and artifact UI.

# Current bound-text and document quality update

245 offline tests in thirteen suites and three real Windows/Tk suites passed.
The final fixed qualification run completed 28/28 exact tasks
and 8/8 controls, with all saved states safe.
Median task time 11.69 s; p95 20.51 s.
Declared supervised-document target met: True; all_passed: True.
Failed final cases: none.

Request-bound text is parsed in code, omitted from the model's current message,
and passed through the existing exact approval and guarded save path. Both the
offered menu and actual dispatch disallow ordinary replacement writers during
that literal append request. Current-turn reads, single use and no replay are
enforced. Provider length responses refuse before dispatch and revoke document
observations. Normal text/tool sampling matches the measured temperature 0.2.

Earlier failed configurations are retained in RELIABILITY.md, including the
rejected direct-generation experiment. This is a narrow workflow measurement,
not a general intelligence/security guarantee. Source publication uses the
existing branch/draft PR; no new dependencies or broader authority were added.

# Current stale-edit quote fix and diagnostic coverage

231 offline tests passed in thirteen suites, including five new checks for the
named text field, real versus framing quotes, diagnostic privacy, actual simulated
human edits and bounded targeted selection. Three Windows/Tk suites passed again.

Three diagnostic failures were retained before changing behavior: the confirmation
proved that JSON quote delimiters had been included in find. A named read text
field plus clear guidance fixes the representation confusion; literal matching,
approval and file-state guards remain. Both targeted stale tests and both stale
tests in the full run reached the human-edit simulation and passed with the
saved_text_changed_after_preview reason, retaining only the human-edited version.

Full extended 12b run: 11/12 document tasks, 4/4 controls. The quoted append at
seed 42 still proposed unexpected text and was denied, saving no new version;
it remains a failure. Seed 43 passed. This is not an all-passing live suite or a
general quality guarantee. See RELIABILITY.md for old/new scores and limits.

# Earlier bounded edits and routing

226 offline tests passed in thirteen suites. 17 new edit checks cover literal
preservation, exact/ambiguous matching, bounds, read provenance, stored draft
changes, cancellation/reset, one-use exact approvals during plans, queued fallback
refusal, Stop, fresh Resume and uncertain publication. An added evaluator test
checks the new tool/extra cases; two routing tests check code hints and limits.
Real Windows worker recovery/edit, Windows/Tk Documents and Tk progress/Resume
suites passed again, using only owned temporary data.

Current full-menu live cases at seeds 42/43: e2b 5/12 document tasks, 4/4 controls;
12b 12/12 tasks, 2/4 controls. The two failed larger-model controls stopped before
the intended preview and did not exercise the human-change guard or create a new
version. Original-only task counts were 3/8 and 8/8; the smaller model's prior
5/8 result was not improved by the helper. All failed attempts remain retained.
Classifier-only routing expectations were 3/7; the bounded code hint then met 7/7,
with four hints requiring no inference. A real Auto append used 12b, approved exact
text and retained version 1 in 21.14 seconds. See RELIABILITY.md for latency,
false-positive/negative routing, fixture scope and limitations.

# Earlier independent document reliability checks

206 offline tests passed across twelve suites. Nine new cases fake model/workers,
block network sockets and verify evaluator byte checks, version retention,
refusal before preview for wrong revisions, denial and changed-file controls,
unknown tool refusal, fixture setup failure reporting, schema registry alignment,
independent cases and bounded repetitions. Existing guard tests remain passing.

Actual local inference: previous code e2b seed 42 passed 1/4 document tasks and
2/2 control cases. Updated code, seeds 42/43, passed 5/8 document tasks with both
e2b and 12b; controls were 4/4 and 3/4 respectively. The larger model's failed
control case did not reach the intended approval stage; no extra saved version
was created. All failed attempts were retained. See RELIABILITY.md for timings,
the deliberate full-schema distraction check, scope and comparison limitations.
This is progress toward measuring consistency, not proof of an 8/10 assistant.

# Earlier filesystem workers and recovery

197 offline assertions passed across eleven suites, including 12 new I/O-worker
cases with sockets blocked. Five real Windows/Tk suites passed after integration:
the new file-worker/receipt/responsiveness fixture, plus task progress, approvals,
Artifacts and Documents. Owned real workers were terminated on deadline and Stop;
an actual published version with a lost reply was independently hash-checked
without rewriting. The UI heartbeat continued during blocked work and Stop was
enabled. Friendly titles and diff previews were visually inspected. A separate
local gemma4:e2b worker-backed create/read/revise smoke passed in 25.53 seconds.
The standalone strict three-case evaluator failed its first creation case in
13.56 seconds with one approval refusal and no saved file; dependent cases were
not attempted. Results were retained. No broad reliability claim is made.
See FILESYSTEM_WORKERS.md for budgets, uncertainty gates and remaining OS limits.

# Earlier task progress and checkpoints

185 offline assertions passed in ten suites, including 17 new task-progress cases
with sockets blocked. A real Tk/fake-backend workflow passed denial, pause, a
simulated human change, Resume, fresh observation and exact approval, verified
result display, visible Resume controls, Stop and New chat. Existing real Tk
approval/Artifacts and Windows/Documents fixtures passed after integration.
Compact and detail views were visually inspected. A final local gemma4:e2b
exact-text recovery fixture passed in 22.03 seconds after three guarded failed
attempts. Earlier failures involved saved-version/revision confusion, unwanted
metadata in the draft and the old response bound. No unapproved document update
occurred. The final fixture read the synthetic human change before its new exact
approval and retained the earlier saved version. This is not evidence of general
open-ended recovery reliability. The loop now permits at most seven responses
for an outline and fresh observation, without automatic background continuation.
See TASK_PROGRESS.md for trusted outcome events and fresh-read gates. Checkpoints
are RAM-only; model final text cannot forge verified counts or pause/failure states.

# Earlier saved Documents workspace

168 offline plain-assert tests passed across nine suites, including 18 new
workspace tests with sockets blocked. New native Windows and Tk fixtures passed
within temporary folders: exact saved versions, stale file refusal, retained
history, no-overwrite publication, real hard-link refusal, synthetic reparse
metadata refusal, Stop before publication, pending cleanup, Unicode paths,
No-default approvals, save/load/recovery controls and New chat permission reset
while saved files remain. Existing browser/core/media/Artifacts/Notepad offline
tests and the real Tk approval/artifact suites also passed after integration.
Actual gemma4:e2b created and revised two exact synthetic saved documents in
18.58 seconds with folder approval and two exact save approvals. Test callbacks
were confined to those contents and a temporary folder; they are not installed
in production UI. See DOCUMENTS.md for limitations, including publication races
with Stop, pending files after crashes, filesystem call deadlines and no claim
of an OS sandbox or power-loss durability. The fixed workspace is excluded from
Git and source archives. Existing scratch Notepad still has no Save command.

# Earlier Notepad adapter

142 offline plain-assert tests passed: the prior 128 plus 14 Notepad cases.
Real owned classic Notepad tests passed exact UIA read/edit, two caller threads,
replay/stale/human-edit refusal, fresh numbering, permanent menu-event halt and
owned worker/app cleanup. Both Notepad Tk approval dialogs passed No-default,
Enter/Escape refusal and explicit Yes. Actual local Ollama completed the exact
synthetic start/read/approved edit in 15.57 seconds. No document-save operation
was invoked by the agent or these fixtures. See NOTEPAD.md for the suspended
classic-launch handshake, tested API behavior and remaining scope limitations.
The initial ordinary launch restored the modern app's prior tabs; they were not
edited/closed. Production never falls back to that packaged app. Original source
installation, Windows app aliases and registry/security settings were not changed.

# Current window redesign

128 offline plain-assert tests passed again. Real Tk approval and artifact suites
passed with the redesigned layout, including the existing No-default modal and
emergency-stop behavior. The artifact fixture additionally checked visible code
line numbers and shared editor/chat colors across dark/light theme changes.
Actual own-window screenshots were inspected in dark and light at 1440x900,
with document/code content, and in the compact 1100x680 window. Core tool, browser,
network, permission, generation and model-routing code were unchanged in this
visual update. No new dependency or model download was needed. This does not
establish every Windows DPI/font/display configuration; small panes still scroll.

# Current Artifacts addition

128 offline plain-assert tests passed: the prior 115 plus 13 artifact tests.
All prior native Windows, Tk and Chromium fixture suites passed again. A new
real Tk/codec fixture also passed edit/history/restore, stale human-edit retention,
inert HTML, chosen-path export, image/video decoding, playback, Stop and import
normalization. See ARTIFACTS.md for exact scope and limits. Actual local Ollama also created an inert print(42) code artifact in 15.66 seconds.
No model code was run
and no artifact export was chosen by the model.

# Validation of the practice and media build

Windows, Python 3.12.10, Playwright 1.64.0, HTTPX 0.28.1, Ollama package 0.6.3,
Pillow 12.3.0. An isolated development venv adds the versions pinned in
requirements-computer.txt. PyTorch 2.11.0+cu128 recognized the RTX 5070 Ti Laptop GPU.
No server configuration, security settings, original Downloads files or
C:/dev/agent source files were changed.

## Automated checks

The October 20 context-reuse update passes 291 offline assertions across
sixteen suites and five native Windows/Tk suites. A regression first reproduced
four loads for two Auto classify/reply pairs; it now requires one shared runner.
Real before/after app-loop measurements put the second Auto hi at 19.0002 vs
0.7877 seconds, with summed load time 17.6694 vs 0.0620 seconds and stable 8192
context/runner afterward. This is one short sample; cold loads and token counts
vary. PERFORMANCE.md retains the full timing table and limitations. The formal
SCORECARD.md run remains separate and unperformed.

- 115 offline plain-assert tests: 38 browser/search/core, 24 browser network,
  10 direct fetch, 23 model/vision and 20 new computer/media cases.
- New cases cover exact desktop approval during plans, denial/stale previews,
  unknown app/PID/coordinate/boolean arguments, callback mutation, hidden tokens,
  Stop during approval, direct facade refusal, generation prompt approval,
  local/safetensors loading and exclusive completed output, missing weights,
  redacted persistent audit, actual pixel edits, malformed crops, tool-free audio,
  clip size/duration/protocol/frame bounds and two-follow-up routing retention.
- Real Windows fixture: a blocked worker can be killed without waiting for its
  request lock. Global hotkey registration and its owned-thread message path
  passed without injecting keyboard input into other applications.
- Real native UIA fixture: read, type, RAM save, undo, replay/stale-number refusal,
  human edit after preview, multiline text, owned-window capture, and termination
  of both worker and practice app passed. No real application was controlled.
- Real Tk fixture: controls visible, No focused, Enter/Escape deny, explicit Use
  approves; edited payload contains black pixels; Clear removes it. An emergency
  event during the modal preview closes it and revokes the staged image.
- Real visible Chromium against fake HTTPX: offline route fulfillment, fixed DOM
  extraction with page JS disabled, form/password/hidden exclusion, encoding,
  POST/name refusal, stale references, redirect refusal, distinct caller threads,
  same-host CSS/frames, third-party refusal and shared request-budget reset passed.

## Live local inference and codecs

- Actual Ollama auto workflow started/read only the owned practice app and
  proposed SYNTHETIC TEST for the draft. A test callback allowed only those
  synthetic actions. UIA confirmed draft=SYNTHETIC TEST, saved=empty. 32.73 s.
  Test-only approval callbacks are not installed in the production UI.
- Actual CUDA SD-Turbo produced a 512x512 PNG in 32.89 s. The generated sample was
  viewed. Actual experimental video pipeline produced a 256x256 MP4, 16 frames
  at 8 fps, in 37.93 s. These are single runs, not latency/quality guarantees.
- PyAV sampled a synthetic three-second MP4 at 0, 0.75, 1.50 and 2.25 seconds.
  Local Whisper transcribed a synthetic 4.64-second English WAV as
  "This is a local audio test. The number is 42."
- Fixed synthetic text evaluation: 7/8 exact matches; the small model failed
  strict one-word classification output. Model checks do not establish broad
  reasoning ability, safe planning or routing accuracy.
- Runtime snapshots used: audio 0d3d19a32d3338f10357c0889762bd8d64bbdeba;
  image b261bac6fd2cf515557d5d0707481eafa0485ec2;
  video 8227dddca75a8561bf858d604cc5dae52b954d01. Manifests record local snapshots.

## Voice and reference-photo update (October 20, 2026)

All 283 offline plain-assert checks pass across fifteen suites, including 28
new voice/reference cases. Five native Windows/Tk suites pass: Artifacts,
selected-media UI, progress, saved Documents, and voice/reference controls.
The new GUI fixture uses fake microphone/inference and actual media codecs;
it verifies transcript review without auto-Send, opt-in spoken replies, Stop,
New chat and photo-video Artifact delivery. No personal microphone was recorded.
An overnight suspended fixture exceeded its wall-clock deadline; rerunning the
complete native set on the awake desktop passed. The interrupted run is not
counted as a passing test.

Real CPU Piper synthesized a fixed English sentence in 2.72 seconds (3.04 seconds
of audio); existing CPU Whisper tiny.en recovered its words and number 42 in
5.27 seconds. Sampled child working sets peaked at 163,332,096 and 243,515,392
bytes. These are single-run samples, not memory ceilings. The same pair passed
with gemma4:12b resident, an 8,192-token context and the normal tool menu; the
synthetic run executed no tools. A separate owned Windows worker played 0.1
seconds of synthetic silence from WAV bytes without saving a file.

Development caught two real runtime failures: a 768 MiB synthesis Job ceiling
was too small, so synthesis now uses 1.5 GiB; Python 3.12 has no SND_SYNC flag,
so playback now uses default synchronous mode with SND_MEMORY and SND_NODEFAULT.
The repaired paths passed real worker checks. Physical microphone/device-driver
compatibility still requires a person-operated trial.

See VOICE_AND_REFERENCE.md for the LTX candidate, fixed model revisions,
component calculations, resource guards and video qualification status. Keep
the earlier ModelScope result below as historical evidence, not a measurement
of the replacement backend. No broad model-quality claim follows from these
small tests.

The chosen 65-frame LTX profile passed real text/reference-video trials at
384x256, 24 fps and 30 steps. Both outputs decoded completely. Sampled NVML GPU
usage peaked at 4.67/7.10 GiB; summed child working sets were 7.42/7.51 GiB.
System RAM availability stayed above approximately 4 GiB in these trials.
Earlier same-process loading, encoder-exit timing and CPU/CUDA-generator failures
are preserved in development reports. Final code requires the encoder process
to exit, uses bounded CPU-byte handoff and a CUDA generator. An earlier short
profile was nearly static; the longer temporally decoded clips showed motion,
soft detail and distortion. The inspected frames do not establish general
watermark absence, accurate motion or publication-ready quality.

## Limits and unverified claims

The Notepad workflow update passed all 150 offline assertions across eight test
suites and all five existing real Windows/Tk/Chromium fixture suites. New checks
cover per-response observation barriers, immediate turn termination on refusal,
token revocation and recovery preserving a human edit. Actual gemma4:e2b drafted
and revised the scratch document in two turns in 24.01 seconds; each exact edit
had its own fixture approval and successful read-back. Fixture approval callbacks
are never installed in the production UI. This is a single model run; recovery
after human interference was verified by real-app and deterministic core tests.

This is not a new exhaustive security audit, a VM, a least-privilege OS sandbox
or a proof of no remaining bugs. UIA state rechecks are not atomic against a
simultaneous human edit. Desktop mutations are confined to a RAM-only app to
limit the impact of that uncertainty. Job RAM limits do not cap VRAM. Stop kills
owned process workers but does not forcibly cancel browser/Ollama requests.
Browser background egress has not been proven isolated at the OS layer. Browser
redirects remain refused; service-worker blocking/offline routing are application
settings, not a guarantee about every Chromium background subsystem.

MP4 analysis samples frames, omits its audio and can miss brief events. WAV support
is limited to English 16-bit PCM. The person-operated Talk control adds a bounded
microphone recording; it never auto-sends. Video generation remains experimental
and low-resolution; no broad stability or output quality claim is made.
Interpretation may hallucinate or quote private information.
New persistent audit entries omit payloads; old logs and visible chat are separate.
Weights and the development runtime are excluded from the distributable source.
A blocked cleanup left an unused partial video-model cache on this machine.

Visual inspection of a generated video frame found a watermark-like artifact
produced by the model. The sample is a pipeline demonstration, not a clean or
publication-ready clip; nothing was removed or retouched.
