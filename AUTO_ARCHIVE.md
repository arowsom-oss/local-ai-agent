# Automatic weekly ZIP storage

October 22, 2026. Local saved-chat snapshots only; no model-callable file tool.

## Use it

Restart Local Studio. In **Chats & Projects**, **Auto ZIP saved chats unused for
7 days** is on by default. Uncheck it to disable checks; existing ZIP chats still
open normally. **Check unused chats now** runs the same bounded check immediately
when enabled. The Storage column shows Plain or ZIP. Open and Export transcript
work with either format; updating an opened ZIP chat writes its new plain snapshot.

While this app is open, a check runs five seconds after startup and hourly after
that. It skips a busy/stopped app and never creates a library just by starting.
There is no Windows scheduled task or work after app exit. A missed busy interval
waits until the next check; a manual check is available. Each pass processes at
most three eligible snapshots, with up to eight candidates inspected. Tiny or
poorly compressing snapshots are retried no sooner than 24 hours later.

## What unused means

A snapshot must have been neither opened/exported nor saved/updated for at least
seven days. The current opened saved chat is excluded. Merely listing/searching
titles does not count as opening. A new library records last use immediately.
An older library gets seven days of grace on first migration because its real
historical last-open times were never recorded. Project edits do not mark every
contained chat as opened. Unstored in-memory chats are never saved automatically.

## Scope and data preservation

The ZIP contains the exact saved transcript and every embedded Artifact version
and image/video snapshot. It is a single chat.json member stored inside the
library database, not a standalone .zip file or an archive of the live database.
Python never extracts names to disk. Source schema validation, ZIP CRC and
byte-for-byte round-trip verification finish before a transactional replacement.
The saved version/update time does not change just because storage compresses.
Open expands only in memory, retaining ZIP storage, and reuses all existing
fresh-session permission/target reset rules. Bad archives refuse without applying
a partial conversation. ZIP is compression, not encryption or a backup.

Compression replaces a snapshot only if it saves at least 4096 bytes AND 5%.
SQLite compaction after the committed replacement reclaims disk pages; the report
distinguishes payload savings from actual database bytes reclaimed. If temporary
disk space is insufficient, or compaction is interrupted/unavailable, the committed
ZIP remains readable and compaction can retry at the next enabled idle check.
Compaction has a ten-second progress deadline and requires conservative temporary
space. Compression checks cancellation between bounded chunks with a 20-second
per-snapshot deadline. Stop or new activity before compression commit rolls back
the batch. A ZIP already committed before Stop stays saved; it is not undone by
closing the utility. This uses ordinary SQLite guarantees, not a power-loss promise.

No Downloads/personal-folder scan, original generated file deletion, model-weight
compression, automatic removal of backups, cloud upload or OS scheduler is added.
Original PNG/MP4 files and generated folders remain; those formats are already
compressed and additional ZIP savings can be small. This saves disk, not steady
RAM/VRAM. Existing Artifact/per-chat expanded limits remain; the 256 MB library
quota counts stored compressed/plain bytes. A ZIP expands to at most 96 MB of
encoded snapshot and then passes the same transcript/media/version validation.
Fixed one-member format, method, size, UTF-8 and CRC are validated before restore.

## Evidence and next project step

388 cases across 23 offline suites pass, including ten new archive cases. They
cover exact byte/history/media preservation, a fresh Python process reopening ZIP,
recent/open/current exclusions, no new model tool authority, malformed
ZIP names/members/methods/CRC/types/expansion bounds, failed verification, batch
cancellation rollback, setting validation, tiny-item backoff, batch limits,
migration grace, deferred compaction and app scheduler guards. All use temporary
libraries and injected clocks, with no model or network request.

Three affected native suites pass: Library/Projects, popups and Artifacts. Actual
Tk controls toggle persistence, check inactivity, show ZIP badges, skip the current
saved chat, export/reopen exact text/Artifacts and update ZIP back to plain storage.
Library checks pass in lean and full app runtimes. The owned synthetic screenshot
was visually checked; the scrollable view and fixed Close/status remain accessible.

One repetitive synthetic code/history snapshot saved 249399 payload bytes and
reclaimed 249856 actual database bytes. A separate native repeated-notes sample
reclaimed 20480 database bytes. These are synthetic examples, not typical media
compression estimates. No personal library was compressed during development.
Tests advance an injected clock; a real week-long soak has not elapsed.

Retained failures: the corrupt-deflate test exposed an uncaught zlib.error, now
normalized to a safe refusal; a legacy migration fixture forgot to close its own
SQLite connection on Windows; and a native fixture left an unfiled example hidden
behind its selected Project filter. The latter two were harness fixes. All original
failure logs remain. No human main scorecard result is claimed.

Next: selected PDF/notes Q&A with page citations, bounded imports and explicit
source selection using installed models first. Do not download another model
until a small retrieval benchmark establishes a benefit. The private school portal
and broader Windows control remain separate planned work. Alexander still owns
the threat-model writing and small Copy last answer fix.
