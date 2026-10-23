# Website creation and visual Artifact previews

Requested and implemented October 22, 2026 on the feature branch. Static
HTML/CSS previews are delivered; interactive code and public publishing remain
future work. The earlier notes-only request is retained in PROJECT_RECORD.md.

## Delivered behavior

- Visible Preview / Code buttons above the content; supported code opens Preview
  first. Existing documents keep Text, and images/videos keep native previews.
- Self-contained HTML/CSS renders as a scrollable screenshot of the first
  800 x 1000 CSS pixels, fitted to the panel width. Buttons/links are pictures.
- Code editing, unsaved drafts, selected historical revisions and Save edit stay
  separate. Preview renders the exact captured editor buffer without saving it.
- New HTML Artifacts select themselves unless an unsaved editor buffer needs
  preserving. A whole HTML last answer can become a code Artifact through More.
- Model guidance requests a real code Artifact for a website, with inline CSS
  and no external resources, rather than claiming website creation is impossible.
- Python, standalone JavaScript/CSS, SVG and arbitrary programs remain source
  only. No package install, shell, general code runner or public publishing.

## Renderer boundary

artifact_web_preview.py reduces at most 32,000 source characters and 2,500 start
tags to display markup. Scripts, SVG/MathML, frames/embeds, link/meta/base and
URL-bearing/event attributes are omitted; inline CSS is retained. This reducer
is only one layer, not a standalone HTML security proof.

A fresh headless Chromium with its browser sandbox enabled receives one exact
synthetic HTTPS document through route.fulfill. It never calls route.continue_.
All other requests abort. A response-header CSP sets sandbox, default-src none,
script/resource/frame/form/base restrictions and inline style only. JavaScript,
permissions, downloads and service workers are disabled, and the context is
offline. WebSockets close. Background-network flags and a failed proxy add
defense in depth. No personal profile or Python/JavaScript bridge is attached.

Only a bounded PNG is returned to Tk. The worker and descendant browser tree
use the existing Windows Job Object wrapper with a 1,536 MB commit bound and
20-second receive deadline. A lock serializes renders; a cancelled waiting call
returns within at most five seconds. Stop, Code, selection changes and New chat
cancel the selection's job; generation serials discard late results. Source is
never substituted by an error or silently exported. Ordinary code export is
still an explicitly chosen, non-overwriting .txt file.

These are browser/application restrictions, not a Windows network sandbox or a
claim that every Chromium background request or browser vulnerability is ruled
out. No external image/font loading, interactive page, full-height capture or
visual preview for every programming language is supported. Missing Chromium
or a failed sandbox/worker produces an error; there is no auto-download or
unsafe personal-browser fallback. No new dependency or model weight was added.

## Evidence and retained failure

369 cases in 21 offline suites pass with socket/DNS audit tripwires; six new
fake-browser/worker cases cover detection, reduction, headers, request abortion,
browser cleanup, bounded pixels and Stop/error cleanup. test_artifact_web_live.py
uses actual Windows Chromium and Tk to check layout pixels, Preview-first and
explicit buttons, unsaved/history, unsupported code, new Artifact selection,
stale results, Stop and New chat. Its hostile document bypasses reduction to test
independent browser policy: page script did not change pixels and a loopback
canary received no CSS/image/frame/fetch/WebSocket/popup requests. Existing
native Artifact media, efficiency and popup suites pass too.

An initial full-runtime run failed with the generic renderer/worker error; the
exact cause was not established. Direct renderer and bounded-worker probes,
then lean and full-runtime native runs passed. This is retained as a failure,
not a claimed root-cause fix or proof of perfect reliability. Local logs are
work/web_preview_native_second.log, work/web_preview_full_runtime_retry.log,
work/web_preview_render_probe.log and work/web_preview_job_probe.log.

One actual local gemma4:e2b smoke request through run_turn, with all non-Artifact
actions refused, called create_artifact and opened a real visible Preview. It
took 16.72 seconds including cold model loading; no hidden reasoning text or
personal conversation is retained. This is one successful example, not a broad
website-quality score. The unchanged human main scorecard remains deferred.

## Future work

Broader HTML/SVG/CSS coverage, external asset import under exact approval,
responsive viewports and longer-page capture can follow resource/isolation
tests. Interactive JavaScript and multi-file projects require separate isolated
runtime design. Publishing needs an exact destination, credential adapter and
explicit approval. Previewing a picture does not deploy a website.

Design references: [Playwright routing](https://playwright.dev/python/docs/network),
[browser context options](https://playwright.dev/python/docs/api/class-browser),
[Chromium sandbox option](https://playwright.dev/python/docs/api/class-browsertype),
[CSP sandbox](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Content-Security-Policy/sandbox).
