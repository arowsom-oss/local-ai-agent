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
