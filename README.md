# Local Studio: local AI, Artifacts and practice computer use

Python 3.12 on Windows. Ollama runs locally; Python decides which tools can run.
This is a working first version of the ten improvements in TOP10_STATUS.md.
Desktop control is limited to an owned practice app and a separately approved,
owned classic Notepad scratch window. It cannot attach to your existing windows,
accounts, files or messages.
The original Downloads files and C:/dev/agent installation were left unchanged.

## Window and appearance

The native Windows window now uses a shared dark/light theme, Segoe UI type,
a navigation sidebar and balanced conversation/Artifacts panes. The default is
dark; Light appearance in the sidebar switches both panes together. Utilities
are grouped in the sidebar; attachment controls sit beside the message area.
The model picker and reading-size controls sit in the header. Stop stays beside
Send, with the existing F12/global shortcut and approval behavior.

Artifacts use readable document typography, heading emphasis, a code line gutter,
simple keyword/string/comment colors and horizontal scrolling when needed. These
are display tags on inert text, not code execution or a complete language parser.
Version, restore, edit and export actions remain available. The pane divider is
draggable; a shorter window hides its decorative subtitle to preserve editor room.
The default window is 1440x900 and minimum is 1100x680. No new dependencies are
required. Theme/zoom preferences are in-memory rather than saved across launches.

## Try it

In the prepared workspace, use the supplied `outputs/start_local_studio.cmd`.
The isolated runtime and downloaded model assets live under `work/` and are not
included in the source ZIP. Close older agent windows first to avoid hotkey conflicts.

For a new installation, extract the complete source package into a new folder:

```text
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-computer.txt
.venv\Scripts\python.exe -m playwright install chromium
.venv\Scripts\python.exe setup_media.py all
.venv\Scripts\python.exe chat_window.py
```

Ollama must already be running locally with `gemma4:e2b` and `gemma4:12b` installed.
The optional setup step downloads several GB of audio/image/video weights from
fixed upstream repositories; review their model cards and terms before installing.
Runtime inference refuses missing weights and never downloads them itself.
The full package includes existing helper modules; do not overwrite a private
identity.py or custom website settings when integrating into an older project.
Sandbox reads and the audit log now live beside agent_core.py.

Suggested first prompt: "Open the practice app, read it, and put HELLO in its draft."
Approve each exact preview only if it matches your intention. Save draft stores
text in RAM, Clear clears the draft, and Undo restores one previous state.
Closing the app discards its state. This practice app is not a VM or an OS sandbox.

## Local Artifacts panel

A split panel beside chat now holds documents, code, images and short videos.
Ask "Create a study guide artifact about cells" or "Create a Python code artifact
that prints 42, without running it." The model can create/read/revise bounded
chat-local drafts; exact revision matching prevents stale edits from replacing
newer versions. These RAM-only draft tools have no filesystem or execution API.

Edit text directly, Save edit to create a version, or inspect and Restore older
versions. Unsaved human edits stay in the editor if a newer model revision arrives.
From answer copies the raw last answer, preserving code fences. Import is a
person-run picker; imported text drafts can be read by the local AI. Generated
images/videos automatically become immutable media snapshots in the panel.

Export asks you to choose a new file and exports the exact selected version:
documents as .md, code as .txt, images as .png and videos as .mp4. Existing files
are never overwritten. New chat clears in-memory artifacts, including their
history; already exported and previously generated files remain on disk.

Markdown, HTML, SVG and scripts are displayed as text; URLs are never fetched or
made into executable previews. Native image and silent video previews use bounded,
stoppable decoder processes. This version does not run generated apps or render
arbitrary web code. See ARTIFACTS.md for workflow, limits and tests.

## Scratch Notepad: first real-app integration

Choose Notepad in the sidebar or ask "Open scratch Notepad and draft a paragraph."
Code opens only a separate, empty classic Notepad with no file argument; modern
Notepad tabs and existing editor windows are excluded. The model gets start,
read and exact text replacement tools, with at most 2,000 characters. Every edit
needs a separate No-default preview and a state recheck/read-back verification.
There is no save, open-file, menu, arbitrary-window, clipboard or keyboard tool.

A process-specific menu/dialog guard permanently halts automation if scope might
have changed. Stop, New chat and exiting Local Studio discard this owned scratch
window. The opening popup explains that; keep personal work in other windows.
The installed classic executable is launched with a brief suspended/debug-creation
handshake, detached before execution, and bounded by Windows Jobs. No OS settings,
registry values or app aliases are changed. Unsupported installations fail closed
without connecting to the packaged app. See NOTEPAD.md for API details and limits.

## Desktop actions and Stop

Windows UI Automation reads semantic controls rather than guessed pixel locations.
`desktop_start` opens only the owned practice window after approval; `desktop_read`
returns current numbered controls. `desktop_type(element, text)` and
`desktop_click(element)` resolve a recorded target before showing a separate
No-default dialog with exact before/after draft and saved values. Plans never
cover desktop changes. No tool accepts an app name, PID, HWND, path or coordinates.

Approval is bound to a one-use, short-lived token inside trusted code. Code
rechecks the owned process, window, control identity and state before acting,
then reads the result again. It never retries a mutation automatically. A failed
post-action check halts further changes until a fresh approved practice session.
Reads invalidate old numbers; restarts do not reuse them. Sessions allow at most
1,000 reads and 100 actions. Drafts are limited to 500 characters.

Stop, F12 in the chat window, or the temporary global Ctrl+Alt+F9 shortcut terminate
owned desktop/media/generation worker trees through Windows Job Objects. The
hotkey listener runs separately from Tk's approval loop. If Windows refuses the
shortcut registration, the window reports that and the other Stop controls remain.
Job Objects impose worker RAM bounds and kill descendants; they are not a
privilege, network or GPU-memory sandbox. Stop does not forcibly cancel an
in-flight browser or Ollama call; those may finish, with no new action allowed.
New chat also closes the browser, practice environment and owned workers.

## Images, clips and generation

Attach image opens a person-run file picker for single-frame PNG/JPEG/WebP, up to
10 MB and 20 megapixels. Images become metadata-free RGB PNG, at most 1536 pixels
per side and 8 MB encoded. Screenshot captures only the owned practice window,
after consent. There is no arbitrary desktop capture or background monitoring.
The image preview supports drag-to-hide, crop and reset. Approval sends the
edited pixels, not an overlay. No is the default; Enter, Escape and closing deny.
Send consumes an approved observation once; Clear discards it.

Attach clip accepts a person-selected WAV or MP4, at most 64 MB and 60 seconds.
WAV must be 16-bit PCM, mono/stereo, 8-48 kHz; local English Whisper transcription
gets its own review. MP4 provides up to four timestamped frame samples in an
editable contact sheet. Events between samples and MP4 audio are not analyzed.
Known duration, one video stream, 4K bounds, decode count, worker RAM and elapsed
time are checked. There is no microphone capture, stream URL or model-selected path.

Image/media interpretation is tool-free and rejects returned tool requests.
Only interpretation text is kept in chat, never image bytes or source paths.
Text can still contain private information. This is not secure erasure from OS
or Ollama memory, and pasted interpretation is still untrusted data.

`generate_image(prompt)` and `generate_video(prompt)` always require their own
exact-prompt approval, even during a plan. Code fixes the backend and output:

| Output | Local backend | Fixed bounds |
| --- | --- | --- |
| Image | stabilityai/sd-turbo | 512x512 PNG, 2 steps, 180-second timeout |
| Experimental video | ali-vilab/text-to-video-ms-1.7b | 256x256 MP4, 16 frames at 8 fps, 12 steps, 600-second timeout |

Prompts have 1-500 printable characters. Workers require CUDA, load local
safetensors with offline options, and release this app's Ollama model first.
The video model uses CPU offload. Completed files get unique names in generated/
and cannot overwrite existing files. Output is capped at 20 MB. Killing a worker
can leave a partial .part file. Generated content is not automatically uploaded
or opened. Quality is limited, especially for short videos; no content-filter or
correctness guarantee is claimed. Upstream model terms still apply.

## Model routing

Auto uses the small model to classify general versus reasoning work, validates
its JSON, and maps to the fixed two-model allowlist. Classifiers have no tools.
After selecting the reasoning model, two follow-up turns keep it loaded instead
of repeatedly swapping to the classifier. Manual selection remains available.
Image/video interpretation uses the small vision model; WAV transcription uses
a separate local CPU model. Routing never grants permissions.

The manager serializes calls, unloads its previous model before switching, uses
a 60-second idle request and exposes Free VRAM. Other Ollama clients are outside
its control. All Ollama calls use 127.0.0.1:11434, with proxies, host overrides and
redirects disabled. Model check runs fixed synthetic tasks with no tools and
writes benchmark_results.json. See MODEL_ROUTING.md for measurements and limits.

## Existing browser boundary

- Visible Chromium, fresh context each chat, JavaScript disabled, downloads off,
  service workers blocked and context offline.
- Every routed request is GET and fetched by HTTPX at the checked IP, retaining
  the real hostname in Host and TLS SNI. No route.continue_ or Chromium DNS fallback.
  safe_ip runs for every fetched request so a changed DNS answer is rechecked;
  the subsequent connection uses that checked IP rather than resolving again.
- Scripts, images, fonts, media, WebSockets and EventSource are blocked. Each
  frame/resource must use the exact opened hostname; approved third parties and
  sibling subdomains are still refused before DNS. No resource approval popups.
- Per explicit open: 100 intercepted attempts and 10,000,000 streamed body bytes.
  Blocked requests count; failed responses do not refund bytes. Reads and page
  navigation do not renew the budget. Per response: 5,000,000 bytes. Compressed
  responses, attachments and redirects are refused. HTTPX has 10-second operation
  timeouts plus elapsed checks, not a forcibly interruptible overall deadline.
- Raw browser_open/fetch_page URLs require separate exact-URL approval, including
  on an approved site or during a plan. A new website needs additional site
  approval. Approval requires literal True; exceptions deny.
- browser_click resolves a recorded link, never model-provided coordinates.
  browser_search accepts only a recorded named GET box and 1-100 printable
  characters, no @, line breaks or run of seven digits. Code builds the URL.
  Search always has its own popup; plans only cover open/click steps.
- browser_read returns at most 4,000 characters with untrusted-data framing,
  numbered controls and blocked/budget counters. Numbers become stale after a
  read/navigation. A dedicated thread owns all Playwright objects; caller threads
  use queues and timeouts. Failed navigation disposes of the context.
- fetch_page uses the same pinned, bounded, no-proxy HTTPX approach and returns
  at most 2,000 text characters. Redirects are not passed to Chromium.

Some sites need JavaScript, redirects, hidden fields, POST, authentication or
cross-host resources and will not work. GET can have side effects on badly
designed endpoints. Same-host resources can carry site-chosen paths/queries;
this is destination containment, not complete data-flow control. Browser routing
and offline emulation do not establish OS-wide background-network isolation.

## Privacy and permissions

New audit entries record event/tool/risk and redacted argument/result metadata;
no prompt, search text, URL, draft value, transcript or output text is persisted
there. Older logs are not retroactively cleaned. Chat may display tool arguments
and retain interpretation text. Logs, generated files, caches, sandbox files and
identity.py are excluded from Git. The model has no shell, downloads, arbitrary
app control, file write/delete, credentials, uploads or permission-granting tool.
All actual tool arguments are validated; extra parameters and boolean element
numbers are rejected. A model schema or model promise is never the gate.

## Tests and remaining limits

Run plain-assert tests without Python -O:

```text
python -B test_browser_search.py
python -B test_browser_network.py
python -B test_fetch_page.py
python -B test_model_vision.py
python -B test_computer_features.py
python -B test_artifacts.py
python -B test_notepad.py
python -B test_desktop_live.py
python -B test_vision_ui.py
python -B test_browser_live.py
python -B test_artifact_ui.py
python -B test_notepad_live.py
```

The first seven contain 142 offline tests with fakes. The last five use real
Windows UIA/Tk/Chromium with synthetic data or mocked HTTPX and no Internet.
See VALIDATION.md and TOP10_STATUS.md for what actually passed. Tests do not
prove freedom from vulnerabilities. Wider app integration, OS/VM isolation,
atomic protection against concurrent human edits, broad routing evaluation,
full video/audio understanding and high-quality video generation remain future work.

The generated video smoke sample contains a watermark-like artifact produced by
the model. It demonstrates that the pipeline runs, not publication-ready quality.
