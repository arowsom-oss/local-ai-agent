# Saved Documents workspace

Local Studio can now create and revise plain-text documents in its fixed
`document_workspace` folder beside the application. This is a filesystem tool,
not a Notepad Save command, Word automation or general file access.

## Try it

Ask: "Create a document Artifact containing a short study guide about cells,
then save it as a new Document." Approve workspace access for this chat, then
inspect the exact save preview. The preview names the fixed folder, new generated
filename and complete before/after text. No starts focused; Enter, Escape and
closing the dialog deny. A browser plan never authorizes a save.

To revise: "List my Documents, read the latest study guide, add a section about
mitochondria and save a new version." Code requires a fresh read of the latest
saved version. document_edit provides a literal append or unique-excerpt replacement
without model-supplied revision counters. The Artifact/save path instead needs the
exact current Artifact revision and positive saved version. The model cannot
supply a filename, path, extension, URL, overwrite option or executable output type.

The Documents sidebar lists saved documents and their latest version numbers.
Select a document and Load version; version 0 means latest. The contents become a
new document Artifact. To recover, load an older saved version, optionally edit it
and Save edit in Artifacts, then select the document and Save Artifact here. That
operation previews the current saved text and appends the chosen draft as a new
latest version. Save new in the Artifacts panel creates a separate document.

See DOCUMENT_EDIT.md for examples, ambiguity checks and read provenance.
document_read returns the text value in a final JSON object: {"text":...}.
Treat the wrapper syntax as encoding, rather than as extra document characters.

## Approval and storage

- A person grants folder reading for this chat; New chat forgets that permission
  and all recorded document numbers. Numbers are not reused in the running process.
- Each save freezes exact text from a current document Artifact, creates an opaque
  one-use 120-second proposal, and always asks for its own approval.
- A rejected, stale, malformed or failed document request ends the current agent
  turn, including queued actions. A fresh person request is needed to try again.
- Text is UTF-8, at most 8,000 printable characters plus tabs/newlines. Code/media
  Artifacts are refused; a .txt file is never executed.
- Filenames are generated UUIDs and version numbers, such as
  `doc-<32 hex digits>-v001.txt`. Current and recovery versions are ordinary files
  that a person can inspect. No existing document is overwritten or deleted.
- There are at most 20 documents, 12 saved versions per document, 100 reads and
  20 saves per chat. The native layer caps each file at 128,000 bytes and directory
  enumeration at 300 entries. Missing history versions cause refusal, not repair.
- Folder reads and text may enter local model/chat memory. Persistent audit stores
  metadata rather than payloads. Saved files persist after Stop, New chat and exit;
  they are not encrypted. The workspace folder is excluded from Git/source ZIPs.

## Filesystem checks

The Windows adapter requires a fixed local drive, pins every directory ancestor
against rename/removal while operating, opens with OPEN_REPARSE_POINT, rejects
junctions/symlinks/unexpected types, and requires files to have exactly one hard
link. It opens existing versions with sharing that excludes writers and deletion
while comparing bytes. A changed inventory or current file after preview consumes
approval and refuses the save. All model references resolve through numbered
records; model text is never interpreted as a filesystem path.

New bytes are written to an exclusive generated pending file, flushed and read
back fully. Code checks Stop, then renames that exact open handle to the new
version with replacement disabled and reads it back again. Failed unpublished
pending files are marked for deletion by handle. A crash or cleanup failure can
leave an ignored pending file; it counts toward the entry limit. Review such
files manually rather than letting the agent delete them.

This retains recovery copies instead of modifying documents in place. It does
not guarantee durability across power loss, prevent another same-user process
from editing files later, or provide an OS sandbox. A Stop arriving after the
final prepublication check can coincide with a completed save. Filesystem work now
uses owned workers with a ten-second transaction budget and an asynchronous UI.
An uncertain publication blocks new saves until Check last save reconciles the
expected output. The old versions remain. Never assume an Error means no new file
exists. See FILESYSTEM_WORKERS.md for recovery, cancellation and OS limitations.

## Validation

18 offline plain-assert tests use fake disk/model/approval objects and prohibit
Internet sockets. They cover permission denial, separate save approvals during
plans, path/URL/boolean argument refusal, stale text/inventory, frozen approvals,
replay/expiry/cancel/Stop, historical reads, document/history/read/save limits,
bad UTF-8, direct-facade refusal and two caller threads consuming one token.

The real Windows fixture used only a new temporary folder, including Unicode and
astral characters in its path. It passed byte-exact saves, stale refusal,
version retention, no-overwrite publication, real hard-link refusal, a synthetic
reparse-metadata guard, Stop before publication and pending-file cleanup. Actual
junction creation and hostile concurrent-process stress were not tested.

The real Tk fixture passed visible Documents/save controls, No-default previews,
explicit approval, save/load, a new version from the selected Artifact and New
chat retaining files while forgetting permission. Local gemma4:e2b created and
revised two exact synthetic saved versions in 18.58 seconds. The fixture allowed
only those exact synthetic contents in a temporary folder. Such callbacks are
never installed in production UI. One successful run is not a reliability guarantee.
