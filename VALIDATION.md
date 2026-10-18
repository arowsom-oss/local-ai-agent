# Current independent document reliability checks

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
is limited to English 16-bit PCM, without a microphone. Video generation uses an
older experimental pipeline and is low-resolution; no broad stability or output
quality claim is made. Interpretation may hallucinate or quote private information.
New persistent audit entries omit payloads; old logs and visible chat are separate.
Weights and the development runtime are excluded from the distributable source.
A blocked cleanup left an unused partial video-model cache on this machine.

Visual inspection of a generated video frame found a watermark-like artifact
produced by the model. The sample is a pipeline demonstration, not a clean or
publication-ready clip; nothing was removed or retouched.
