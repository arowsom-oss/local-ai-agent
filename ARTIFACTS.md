# Artifacts: first local version

The right-hand panel is a workspace for a document, source code, image or video.
The draggable divider changes its share of the window. It adds no cloud API or
model dependency. A document is displayed as editable plain text, including any
Markdown markers. Code remains inert. Supported single-page HTML/CSS now opens a static visual
Preview first, with explicit Preview / Code buttons. Other code stays in source
view. There is no general run button, external URL handling or Python bridge.
Page JavaScript is disabled; the preview returns local pixels, not an interactive
webview. WEBSITE_PREVIEW_PLAN.md documents the renderer and its limits.

## Try it

1. Start the updated window with the supplied workspace launcher.
2. Ask: "Create a document artifact called Biology notes about cells."
3. Select it in Artifacts. Edit the text and choose Save edit to retain a version.
4. Select a previous Version to inspect it; Restore makes a new revision from it.
5. Choose Export and select a new filename. No file is written just by creating,
   revising, viewing or restoring a text artifact.

New creates a blank document. From answer copies the last raw response into a
document, retaining Markdown/code fences. Import lets the person choose local
UTF-8 text/code or a supported image/MP4. Imported text becomes available to the
local model through artifact tools; media is previewed only, without automatically
sending its pixels to the model. Imported images are normalized to PNG.

The model receives four strictly validated tools: create_artifact(title, kind,
content), list_artifacts(), read_artifact(artifact), and revise_artifact(artifact,
revision, content). Only document/code can be created through these tools; they
accept no filesystem path, URL, destination or executable artifact kind.
Read/list output is marked as untrusted data. Draft creation is a bounded RAM
operation; it does not approve any other tool or bypass existing action popups.
The normal chat/tool history can include draft text; the persistent audit contains
only redacted metadata. Drafts are shared with the local AI, not a secrets vault.

Every generated image/video is registered from its fixed local generated-output
location, with an expected unique filename. Bytes are captured once so later
file changes cannot silently alter the preview or export. Preview failure or a
full artifact store does not delete a successfully generated file. An existing
local generated file can also be imported through the person's picker.

## Version and export behavior

Each update names the current revision. If another model turn or the person has
changed it, a stale update is refused. Unsaved editor text is not replaced when
an external revision arrives; copy that text before explicitly choosing Reload.
Historical versions are read-only; Restore appends a new version. A newly selected
artifact asks before discarding unsaved edits.

Export freezes the selected artifact/version before opening the picker. A later
model revision cannot change those chosen bytes. Code exports are .txt, documents
.md, image snapshots .png, video snapshots .mp4. Code is not saved as an executable
extension. Existing destination files are refused even if the picker offers to
replace one. A write failure can leave an incomplete destination file; the UI
reports failure, and does not overwrite or clean up another file.

Artifacts/history live only in this process for the chat. New chat clears them;
IDs are never reused. Stop pauses playback, kills owned decoder workers and
discards stale decoder replies; text drafts remain. No background playback or
external media application is opened. After Stop, start a fresh turn/New chat
before requesting another decoder preview. Ordinary OS/process memory is not a
secure-erasure boundary. Exports/generated files persist until the person removes
them, and this feature does not add a model file-delete tool.

## Fixed limits

- 20 artifacts per chat; 12 versions per text artifact; 32,000 text characters
  per version, with control codes refused except tabs/newlines.
- 64 MB total retained artifact payload, counting every historical version.
- Media input/snapshot at most 20 MB. Imported image decoding retains the existing
  10 MB, 20-megapixel, single-frame PNG/JPEG/WebP rules; prepared image exports
  contain normalized PNG bytes, without source metadata.
- Silent MP4 preview: one video stream, known duration up to 10 seconds, at most
  120 decoded frames and 1,048,576 pixels per frame. Timestamps must be ordered;
  retained decoded PNG frames total at most 12 MB. Video audio is not played.
- Image/video decoding: 512 MB Windows Job memory bound, 15-second worker timeout,
  local byte streams only, MP4 protocol allowlist pipe/data. Missing codecs or
  malformed media fail closed; no download or fallback web viewer is started.

## Verification

13 offline plain-assert artifact tests cover real core dispatch, strict tool
arguments, inert kinds, stale/conflicting edits, concurrent callers, memory/count/
history limits, immutable snapshots, reset IDs, untrusted-data labels, hidden media
bytes, generated path constraints, exact-version exports, cancellation/Stop,
non-overwrite and protocol/duration checks. With the previous suites: 128 offline
tests passed.

A real Windows/Tk fixture passed split-panel visibility, editing/version restore,
preservation of unsaved edits across a model change, inert script text, chosen-path
export, actual PNG and 16-frame MP4 decoding/playback, Stop and JPEG-to-PNG import.
Those fixtures use synthetic data and no Internet or model inference. They are
regression checks, not proof of OS isolation, decoder safety or no remaining bugs.

Actual local Ollama smoke check also passed: gemma4:e2b called create_artifact
with code content print(42), then confirmed creation. The draft remained inert;
no code was executed. This single run took 15.66 seconds and does not establish
that every model request will choose the right artifact tool or produce good text.

## Updated native editor appearance

Artifacts shares the main window's dark/light palette. Documents use proportional
text with emphasized Markdown heading lines; source characters remain unchanged.
Code uses a monospace line gutter and simple display-only keyword/string/comment
colors. The heuristic colors do not establish syntax correctness or a language
parser. Horizontal scrolling appears when a source line exceeds the view width.
A shorter pane omits its decorative subtitle; editor controls and safety behavior
remain. Appearance changes do not grant execution or external network access.

## Generated media delivery and recovery

The core reports generation success only after registering the returned file as
an immutable media Artifact. The generated file must still pass the fixed-folder,
UUID filename, kind and size checks; the model cannot choose its path. An invalid
worker result or registration failure returns Error with recovery instructions.
Further generation requests in that turn refuse before another popup or worker;
the person must send a new request. A completed file may remain after Stop or a
registration failure; neither case claims that an Artifact was delivered.

When a new media Artifact arrives, the pane opens and selects it even if another
Artifact was selected. An unsaved text buffer stays selected and intact instead,
with a notice naming the new Artifact in the list. Repeated refreshes do not
restart a preview. Existing isolated decoding, Stop and playback limits apply.

Artifacts > More > Open generated image or video opens a person-controlled picker
in this installation's generated folder. It reuses the same strict path and
memory checks and snapshots the file without inference, downloading or deleting
it. This makes earlier generated files available after New chat or a restart;
it does not restore the old chat or automatically populate every previous file.
Media in Downloads or other folders can use the existing Import a file picker.
Export remains the explicit way to save a selected copy elsewhere.

Eight additional offline tests cover both real core generation dispatch paths,
immutable bytes, exact approvals, full stores and retry blocking, malformed or
outside-folder results, Stop, automatic selection, preserved unsaved text and
reopening/cancellation. The native Tk fixture now uses scripted model/worker
results through actual core registration and verifies PNG/MP4 auto-selection,
decoding, playback and reopening a retained video after New chat. The GPU models
are not invoked by these regression tests.


## Static HTML/CSS Preview / Code

Create or import a code Artifact beginning with HTML markup, optionally wrapped
in an html Markdown fence. The panel opens and shows Preview first. Choose Code
to edit, then Preview to render the current buffer without saving. Unsaved text
and historical versions keep their identity. New HTML Artifacts select themselves
unless an unsaved draft needs preserving. Draft from last answer recognizes a
whole HTML answer; prose mixed with code remains a document.

The scrollable preview shows the first 800 x 1000 CSS pixels, fitted to the pane
width. It is a picture: links, forms and buttons do not act. Scripts, external
assets/fonts, frames and navigation are disabled. CSS-only/JavaScript-only code,
Python and SVG currently remain source-only. This does not publish a website or
install packages. Unsupported content and failed rendering keep the source.

Rendering uses the already installed Playwright Chromium in a fresh context,
with no browser/model downloads or new dependencies. A stopped/failed renderer
has no external-viewer fallback. The owned worker/tree is limited to 1536 MB
committed memory and a 20-second receive deadline; queued cancellation waits at
most five seconds. Stop/New chat and selection changes discard stale previews.
The browser restrictions are not OS-level network isolation; see the renderer
policy and retained first-run failure in WEBSITE_PREVIEW_PLAN.md.
