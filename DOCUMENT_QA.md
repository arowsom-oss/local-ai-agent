# Sources Q&A: selected documents with inspectable citations

October 23, 2026. First local document-Q&A stage, separate from the agent's tools.

## Use it

1. Restart Local Studio and choose **Sources Q&A** in the sidebar.
2. **Add source** selects one local PDF, TXT or Markdown file. All files currently
   listed are in scope; selection of a list row only targets Remove selected.
   Notes must be UTF-8. Imported content is an immutable in-memory snapshot.
3. Ask a specific question in this window, then **Ask selected sources**. This
   uses the main Model dropdown. Auto directly uses installed gemma4:e2b with
   no classifier; manual selection uses the other allowed installed model.
4. Inspect answer references such as [C1] with the citation dropdown. The viewer
   shows the retrieved excerpt, full extracted page/text and snapshot SHA-256.
   PDF numbers are physical one-based pages, not printed page labels. TXT/MD
   notes are explicitly unpaginated, with no invented PDF page number.
5. **Keep answer in Artifacts** makes a new document Artifact with answer, quotes
   and snapshot references. It preserves an existing unsaved Artifact draft.
   Save that Artifact with Chats & Projects/Documents if you want persistence.

Sources stay in this chat's RAM across closing/reopening the window. **Remove
selected**, **Forget sources**, New chat and saved-chat replacement forget them;
original files are unchanged. Closing cancels pending work and discards late
results. Source files/collections and the Q&A window's questions are not saved
automatically in chat snapshots. Explicitly keeping an answer as an Artifact
can retain its quoted content/name/hash when you later save the chat.

## Retrieval and citation checks

Deterministic keyword retrieval splits extracted pages into overlapping
1000-character chunks with an 850-character stride. Term rarity/frequency ranks
matches. It selects at most four excerpts within a 6000-byte system/user prompt
budget; a bare summary request chooses early pages. Summary coverage is partial,
and keyword matching can miss synonyms, semantic relevance or details elsewhere.
No matching excerpt returns a fixed insufficient-evidence message with no model
request. Lack of a retrieved match does not prove absence from the whole file.

One structured local-model request returns at most five claims, each with a
code-issued citation ID and a supporting quote of 12–400 characters. Code rejects
unknown IDs, malformed/extra schema, tool output, missing quotes and quotes that
do not occur in that exact normalized excerpt. Filename/page attribution is
generated from the immutable source mapping, never a model-supplied path or URL.
Whitespace is normalized for matching, with a non-whitespace length check.
The display does not render HTML, run code, open links or launch the original PDF.

These are **provenance checks, not proof of factual entailment**. The model can
misinterpret a real quote, and PDF extraction can lose reading order, table
structure, figures or meaningful formatting. Review the original document when
layout matters. The text viewer is extracted text, not a pixel-perfect PDF
viewer. Image-only scans refuse with an OCR explanation; mixed files warn about
pages with no extracted text. OCR, embeddings and semantic/full-document search
are not implemented by this stage.

## Enforced bounds and authority

- Five selected sources, 500000 extracted characters total; 8 MB per input file.
- PDF: 1–100 physical pages, at most 20000 extracted characters per page and
  200000 per file. Over-limit documents refuse instead of silently dropping pages.
  TXT/MD: at most 200000 characters. Input UTF-8 errors refuse. Unsupported
  control characters are removed from extracted reference data.
- A fresh Windows Job-bound worker handles file reads/PDF extraction, with a
  768 MB process/job memory cap and a 20-second receive deadline. It is an owned
  resource/lifetime bound, **not an OS permissions sandbox** against a parser
  exploit or malicious code running as the same Windows user.
- Only explicit local regular-file selections; UNC/network drives, relative
  paths, ADS names, unsupported suffixes, links/junctions/cloud placeholders and
  changed-during-read sources refuse. No folder scan, embedded attachment
  extraction, PDF-script execution, automatic URI following or original writes.
- pypdf==6.19.0 is pinned in both runtime and CI requirements; this lightweight
  parser version was already available in the full app runtime and was added to
  the lean test environment. No new model weights/downloads, OCR or GPU model
  residency are added.
- Calls reuse model_router's fixed loopback client, serialized GPU lifecycle,
  installed-model allowlist and 8192-token context. tools=[] and think=False;
  output is capped at 1000 generated tokens. The normal agent dispatch/approval
  machinery is never entered, so a document cannot request an action through
  this Q&A path. Prompts describe untrusted data, but authority is absent in code.
- Stop/Close discard late results; parsing workers are killable. An already
  running Ollama request may finish or reach the existing 180-second client
  timeout. Busy remains until that call returns, with no automatic retry or
  interpretation of a cancelled answer. This is not immediate inference cancellation.

## Evidence

404 plain-assert cases across 24 offline suites pass with Python socket/DNS
operations blocked by the runner. Fifteen Q&A cases cover real PDF extraction,
physical/blank pages, encrypted/scanned/oversized/malformed inputs, immutable
reads, parser result/lifetime bounds, collection budgets, quote/ID forgery,
abstention, keyword/Unicode prompt budgets, cancellation and no tool authority.
An active-content PDF fixture includes JavaScript and an attachment; only text
is read. Eight small synthetic keyword questions retrieve the expected top page;
this is not a semantic-retrieval benchmark or a general quality score.

Five affected native suites pass: Sources Q&A, saved chats/Projects, popups,
Artifacts and efficiency UI. The actual parser worker imports a three-page PDF;
actual Tk controls inspect page 2, warn about an empty page, retain a snapshot
after the original changes, keep an Artifact without losing a dirty draft,
discard late Stop/Close results, forget sources and reset on New chat. New
window checks pass in lean and full runtimes. Close/Escape/X and a scrollable
short-window layout were checked, and the owned synthetic screenshot was viewed.

Actual gemma4:e2b answered three synthetic PDF questions with correct page/quote
mapping, including an excerpt containing malicious action instructions. No Q&A
action tools existed. An unrelated fourth question abstained without inference.
The corrected run took 10.919 seconds for the first answer including 9.260 seconds
of model loading, then 0.550 and 0.541 seconds warm. The earlier run took 23.411
seconds first including 21.264 seconds of loading; it remains historical evidence.
These tiny answers are not promises for long documents, 12b, general robustness
or daily latency. No personal source files were used in development.

The real-model smoke exposed a timing-label bug: any structured output had been
called a classifier phase. model_router now uses that phase only for the actual
router schema; other structured answers log model. A regression test covers it.
Two retained harness failures involved a fake stat missing st_mode and an Escape
event sent before focusing its window; both were corrected and rerun. Their
original logs remain. The human main scorecard stays deferred, and the student's
threat-model writing/Copy last answer fix remain untouched.

## Next

Run the prepared human scorecard and review draft branches before merging.
For document Q&A, expand a fixed retrieval/answer test set before deciding if a
small embedding or OCR model earns its extra complexity. Persistent owner-bound
source storage, scanned-page OCR, streaming/immediate cancellation and the
private school portal remain separate work, not delivered by this change.

Primary parser references (behavior checked alongside the pinned local version):
- https://pypdf.readthedocs.io/en/stable/user/extract-text.html
- https://pypdf.readthedocs.io/en/stable/modules/PdfReader.html
