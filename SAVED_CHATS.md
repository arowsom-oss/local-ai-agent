# Saved chats and Projects: first local version

October 22, 2026. Person-controlled persistence, not a model tool or remote service.

## Use it

1. Restart Local Studio and open **Chats & Projects** in the main sidebar.
2. Optionally create a Project with a name and reference notes. Select it in the
   dropdown to filter saved chats and choose where the current chat will be saved.
   All / Unfiled lists all chats and saves without a Project.
3. Name the current conversation and choose **Save new copy**. This is explicit;
   chats are not automatically saved on each turn or on app exit. First use of
   the library creates its empty local database, not a copy of the current chat.
4. **Update opened chat** replaces that saved snapshot only when its saved
   version still matches. The opened target is named above the title field.
   Selecting another list row targets Open/Export/Delete, not Update. Editing
   the title field and updating the opened chat also renames that saved copy.
5. Search titles literally, choose a saved conversation and **Open selected**.
   No is the default for replacing the current in-memory conversation. Save
   current work first; the picker never auto-saves or overwrites another chat.

Project notes are bounded reference text, not special tool authority. **New chat
in Project** starts a fresh chat with those notes. Edited notes apply when a
saved chat is reopened or a new chat starts in that Project. They are not injected
into an already running turn. The local library has no multi-user account model.

## What gets saved

- Raw visible user/assistant text, preserving Markdown/code characters. No
  executable assistant message objects, tool-call protocol, tool results, system
  prompt, hidden reasoning, runtime log or attached-image analysis payload.
- All current chat Artifacts, including every retained text/code version and
  immutable image/video snapshots. Photos/videos count toward the same Artifact
  budgets. The unsaved editor buffer must first use Artifact **Save edit**;
  otherwise chat saving refuses rather than silently leaving that edit out.
- A title, Project reference, numeric saved version and local update time. A
  new copy receives a new database ID. Updating is transactional and detects a
  stale version, including a change made through another Library instance.

Saved data is in chat_library/library.sqlite3 beside this installation, ignored
by git. It is local **unencrypted** data with ordinary OS file permissions, not
a password-protected vault or a promise that another local process cannot read
it. Do not save secrets assuming the app encrypts them. No model/cloud upload is
added. New chat clears the active conversation, not saved copies.

## Reopening is a fresh action session

All snapshot data is revalidated before replacing active work. A temporary Store
checks kinds, sizes and every Artifact version. Restoration closes/revokes the
current browser, Edge, scratch/practice and owned worker sessions, clears website
and workspace grants, voice/image state, task checkpoints and pending approvals,
and creates fresh Artifact IDs. A browser-close failure leaves the old chat in
place. Nothing in the archive can restore a browser target, plan or approval.

The full saved transcript is displayed, but the model receives only a clearly
marked untrusted archive tail of at most 4000 serialized characters plus at most
2000 characters of Project notes. This can omit older details and can begin
mid-entry; it is not semantic retrieval or unlimited memory. User/assistant roles
are not replayed as an old executable protocol. Old numbers in text stay stale;
the person must send a new request. Restored/Project sessions pass the existing
code-enforced fresh-read gate to the core on subsequent turns. No model request,
tool action, voice playback or background continuation starts just by opening.

## Delete, export and lifecycle

**Export transcript** freezes a saved snapshot after the person's picker and
writes a new .txt file, preserving original text formatting. An existing file is
refused. This exports conversation text, not all Artifact bytes; individual
Artifacts retain their existing export controls. An I/O failure can leave a
partial new export, which is reported; another file is never cleaned up silently.

**Delete saved** has a No-default confirmation and checks the selected saved
version. It deletes only that stored copy/snapshots. Current open work, exported
files and generated-folder originals remain. Removing a Project keeps its chats
as Unfiled. Database deletion is logical, not secure erasure; freed SQLite pages,
backups, memory or disk recovery may retain bytes. No recursive file deletion
tool, automatic cleanup job or model delete capability is added.

Database work runs off Tk with short lock timeouts and transactional commits;
chat actions wait while a library operation is active. Closing a utility while
a read finishes discards the result. Stop prevents applying a pending Open.
A person-requested Save/Delete/Export may already have committed when Stop or
Close occurs; it is not rolled back or repeated automatically. Completion
releases busy state even after the window closes. Save metadata is settled on
the UI thread without reopening a closed view. Close/Escape/X are available;
scrollable content and a fixed status/footer keep controls reachable in a short
window. This is not crash-proof secure storage or a cloud sync feature.

## Bounds and failures

- 100 saved chats; 20 Projects; 80-character printable titles and 2000-character
  Project notes. Search is case-insensitive literal title search, at most 100
  characters, not full-text/vector search.
- 400 user/assistant messages and 1 MB of UTF-8 JSON transcript per saved chat.
  Oversized content refuses without silently truncating a saved transcript.
- Existing Artifact limits: 20 per chat, 12 text versions, 32,000 characters per
  version, 20 MB per media item and 64 MB retained raw payload across versions.
  The encoded chat snapshot has a 96 MB ceiling; total retained library payload
  is capped at 256 MB and SQLite has an additional page-count limit. Temporary
  transaction journals and ordinary process memory are not the same budget.
- Fixed database filenames; titles never become paths. SQLite parameters, strict
  payload schemas, no link/reparse paths and fresh Artifact IDs are enforced.
  A corrupt, oversized, linked, locked or malformed store produces an error.
  These checks do not defeat a hostile process that can rewrite this app's code
  or race its filesystem access as the same Windows user.

## Evidence and next stage

378 cases across 22 offline suites pass, including nine new library cases for
fresh-process readback, history/media, strict schemas, quotas, stale writes,
literal search, Project removal, concurrent Library instances and linked/corrupt
paths. Model functions cannot call save/load/delete through the core tool menu.
The popup inventory now includes both library windows and their No-default prompts.

Ten affected native suites pass. Actual Tk tests cover save/update, notes,
filtering, exact export/non-overwrite, unsaved-buffer refusal, fresh IDs and
permission reset, no replay, the core fresh-read flag, late/Stop results, closing
while a save commits, Project removal/start and New chat. The library fixture
also passed in the full app runtime. The owned synthetic screenshot was visually
reviewed; a short-window fixture reaches Save with Close/status still available.

Early harness failures used an incomplete stat fake and the wrong core menu
attribute. Native tests then found actual bugs: a restored chat incorrectly
used paused-task progress resume, and a removed Project left a stale list filter.
Both have regression coverage and pass after repair. The early white controls
and clipped layout were corrected and rechecked. All failures remain local logs.

One actual gemma4:e2b recall from a temporary saved synthetic conversation
answered the stored fruit correctly, made no tool calls and saved the continued
four-message conversation as version 2. It took 12.47 seconds including a cold
model load. This is one smoke example, not a general memory/quality score. The
human main scorecard remains deferred. No new model, embedding index, PDF Q&A,
remote portal or automatic persistent memory is implemented by this milestone.
