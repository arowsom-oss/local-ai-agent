# Document task reliability — 18 October 2026

This assistant remains a supervised prototype. Passing code tests is not a model
intelligence score. This evaluation does not justify an 8/10 general rating.

## Earlier changes before document_edit

Instructions and the document_save description now explicitly distinguish an
Artifact revision from a saved document version. Editing requires revising the
complete Artifact text first, waiting for that result, then saving its new
revision against the saved version actually read. Guidance explains exact-text
requests and prohibits retrying a denied/uncertain save. Code still enforces
approval, stale-state refusal, bounded workers and retained versions.

The offered tool list now comes from the trusted dispatch registry. Previously
the loop had a separate hardcoded schema list: restricting a fixture's dispatcher
left irrelevant tools visible. The model cannot change the registry or grant
permissions. At that milestone no documents-only UI mode or routing change was added.

## Independent evaluator

Run separately from production UI with the existing prepared runtime:

```text
python -B evaluate_reliability.py --model gemma4:e2b --repeats 2 --output NEW.json
python -B evaluate_reliability.py --model gemma4:12b --repeats 2 --output OTHER.json
```

Only installed allowed models are used. No downloads or Internet access are
requested. Each case has a fresh temporary workspace and conversation. The
fixture dispatcher permits only outline/Artifact/Document tools. Approvals accept
only the fixed synthetic folder, target/version and exact before/after text.
Other requests are denied; these callbacks never enter production UI. The CLI
requires a new output filename and refuses overwrite.

Four task cases check actual file bytes and retained versions: create a document,
append a line, replace one word, preserve an existing human addition while
appending. Two separate control cases check denied-save/no-file and a human edit
during approval. A control case only passes if its intended approval stage is
reached and the refusal/file state matches. Failure before that stage cannot get
credit for exercising the guard. Model claims of completion never earn credit.

Independent cases continue after failure. Repetitions are bounded to 1–3 with
seeds 42–44, temperature 0.2, the existing seven-round limit and local client
timeout. Seeds do not guarantee identical output across runs/runtime versions.
There is no strict whole-suite wall-clock deadline. Reports store tool names,
counts and statuses, not document contents or approval tokens.

Default --menu full deliberately shows the normal app schemas while fixture
dispatch still blocks non-document execution: choosing among distracting tools
is tested without allowing app/network access. --menu documents instead uses
only executable fixture tools, now that schema and dispatch registries match.

## Retained results, including failures

| Configuration | Seeds | Exact document tasks | Control cases | Total case time |
| --- | --- | --- | --- | --- |
| Previous prompt/schema code, e2b | 42 | 1/4 | 2/2 | 42.53 s |
| Updated code, e2b, full menu | 42, 43 | 5/8 | 4/4 | 83.28 s |
| Updated code, 12b, full menu | 42, 43 | 5/8 | 3/4 | 122.04 s |

The baseline used the previous hardcoded full menu and predates the explicit
tool_menu report field. For the single matched seed (42), small-model results
changed from 1/4 to 2/4 tasks. This is too small to establish a reliable gain;
schema ordering and prompt/schema descriptions both changed.

The updated small model passed creation and word replacement at both seeds;
append failed at both; preservation passed only at seed 43. The larger model
passed creation/replacement at both seeds, append only at seed 42, preservation
at neither. Its failed stale-approval case stopped before an exact save preview,
so it did not exercise the human-edit guard. That failure produced no extra saved
version or verified overwrite. It is still counted as a failed control case.

These measurements do not support preferring the larger model for every document
job. Timings include different cold/warm states and failures; quicker failure is
not better work. The earlier dependent evaluator's failed first case and separate
successful two-turn smoke run remain retained, not replaced by these results.

## Validation and next work

All 206 offline tests across twelve suites passed. Nine new evaluator tests use
a scripted model/fake worker interface, block network sockets, and check exact
bytes, retained history, wrong revisions before approval, denial/staleness,
unknown-tool dispatch refusal, setup failure reporting, schema/registry alignment,
independent cases and bounded repetitions. Existing approval, Stop, resume and
uncertain-save tests also passed. This is not a new security audit.

At that milestone the next step was a simpler edit tool with unchanged approval,
stale-state and recovery checks. That step is implemented below. Longer/multi-turn
tasks and broader unseen documents remain future work.

## Current bounded edit and routing update

document_edit(document, find, replacement) uses the last successful latest read
to supply identity/version/hash in code. Empty find appends literal text;
otherwise find must occur once, including an overlapping-match check. All other
text is retained by code. A separate proposal Artifact feeds the existing exact
approval/one-use commit path. Missing/stale reads, stored Artifact changes,
ambiguous/no-op/oversize edits, uncertain saves and extra parameters refuse.
After a commit or cancellation another latest read is required. See DOCUMENT_EDIT.md.

Resume document-read-gate refusals now end the turn and defer remaining actions,
matching the existing policy for denied/failed document execution. No automatic
retry, fallback write tool, approval bypass or relaxed file guard was introduced.

The evaluator keeps all six earlier cases and --extended adds two new tasks:
change a room number while preserving notes, and append while preserving quotes
and a literal backslash. Cases/expected bytes were fixed before the run. Neither
failed cases nor earlier reports were replaced. The full normal schema menu,
temperature 0.2 and seeds 42/43 were used again.

| Current code | Original tasks | Additional tasks | Total tasks | Controls | Time |
| --- | --- | --- | --- | --- | --- |
| e2b | 3/8 | 2/4 | 5/12 | 4/4 | 108.70 s |
| 12b | 8/8 | 4/4 | 12/12 | 2/4 | 223.16 s |

The small model still mishandled append proposals and once created an Artifact
without saving. Exact fixture approval refused nonmatching text. Both larger-model
control failures were whole-text replacement requests refused before an exact
preview. The human-edit mutation was never reached; each case retained only its
original version. These cases remain failures and do not verify that guard.
Real-worker and deterministic tests separately exercised the changed-file guard.

The larger model succeeded on these twelve document attempts, but that is a small
sample, including only two additional tasks, not a general reliability score.
One quoted-append task took 65.07 s; measured gains have a latency cost. These
changes worsened the small model's original-case count from 5/8 to 3/8, so the
helper alone is not a small-model quality improvement.

Classifier guidance alone selected e2b for all four document routing probes and
met just 3/7 expectations (the three general prompts). A bounded code hint now
selects 12b for common English document/note/draft plus action wording. Other text
retains the constrained classifier, vision retains its fixed route, manual
selection remains respected, and model selection grants no permissions. Hints
can overmatch explanations/negations or miss phrasing/languages; their purpose is
model choice, not intent enforcement. The fixed probes then met 7/7 expectations:
four document hints without classifier inference and three general classifications.

An actual Auto append selected 12b for all four task model calls, obtained the
exact expected preview and retained the original saved version in 21.14 s.
This is one additional synthetic end-to-end run, not a broad Auto benchmark.

All 226 offline tests across thirteen suites passed: 17 new edit tests, an added
evaluator oracle test and two routing-hint tests accompany existing checks.
Three real Windows/Tk suites passed again, including the new worker-backed edit,
stale-preview refusal and lost-publication-reply reconciliation. The running
project record was updated with both reliability rounds, code changes and limits.
The private build/evidence package retains all 32 new evaluation cases, the Auto
smoke and both route-probe reports. No new dependency was added.

## Stale-edit quote diagnosis and fix

The earlier records omitted the specific refusal reason. New fixed diagnostic
codes and bounded argument-comparison flags reproduced two pre-approval failures:
find was absent from the current saved text. A separate confirmation proved the
model used json.dumps(before), including the delimiter quotes, rather than the
actual document text. That run had find_is_json_quoted_fixture=true and never
simulated the human edit. All three diagnostic failures remain retained.

document_read now ends with {"text":...}, replacing a bare JSON string. The core
prompt and tool description distinguish the decoded field value from wrapper
syntax while preserving genuine document quotes. Tool arguments and metadata
line are unchanged. Literal matching is unchanged; it neither strips quotes nor
repairs model input. A missing find now has its own not-found error. Manual
parsers of document_read results should read the object's text field.

The evaluator saves fixed refusal reasons and human_edit_simulated, without
copying document text, arbitrary error messages or tokens. --case selects distinct
named cases with unchanged pass criteria; a targeted pass is not a whole-suite
pass. New tests prove quoted-find refusal, true quote preservation, diagnostic
privacy and the actual approval/mutation/refusal sequence.

At the same seeds 42/43, both targeted stale controls passed (19.65/8.44 s), and
both stale controls also passed within a subsequent full extended run. Each
preview matched exactly, the fixture then changed the file, and commit refused
with saved_text_changed_after_preview. The human edit remained the only version.

The full larger-model run passed 11/12 document tasks and 4/4 controls. One
quoted-append case at seed 42 proposed unexpected text: its correct before text
was retained, exact approval was denied and no new version was created. Seed 43
passed that case. Its exact content mismatch remains a model formatting failure;
the full report's all_passed is false. Before this change that sample scored
12/12 tasks and 2/4 controls. Do not hide the new task failure or treat a small
sample as a general improvement guarantee. No weaker approval or retry was added.

231 offline tests across thirteen suites passed, including five new regression
tests. Three Windows/Tk suites passed again. Earlier reports remain unchanged;
the running project record includes diagnosis, targeted/full results and this
remaining limitation. Routing, model weights and dependencies are unchanged.

## Measured short-document quality target and bound literal text

Before broadening the run, the project-specific target was fixed at >=95% exact
task completion, all controls passing, safe saved states for every case and a
task p95 <=90 seconds on this laptop. --qualification --repeats 2 runs the same
eight historical scenarios plus ten fixed broader cases: 28 tasks and 8 controls.
Only complete coverage at seeds 42/43 with the normal request-aware full tool
menu can meet the target. --case, --menu documents or one-seed runs cannot.
This is a subjective 8/10 supervised document-workflow target, not a general
model intelligence score or a standardized benchmark. Fixtures and expected
bytes were fixed before the changes; after diagnosis they are regression cases.

| Configuration | Exact tasks | Controls | Median task time | Task p95 | Target met |
| --- | --- | --- | --- | --- | --- |
| Broader initial guidance | 24/28 | 8/8 | 9.66 s | 61.90 s | False |
| Rejected direct drafting | 21/28 | 8/8 | 12.02 s | 58.17 s | False |
| Reasoning plus examples | 26/28 | 8/8 | 9.79 s | 64.11 s | False |
| Binding with raw model message | 26/28 | 8/8 | 10.62 s | 32.00 s | False |
| Binding with projected model message | 28/28 | 8/8 | 11.69 s | 20.51 s | True |

All five runs retained safe saved-file states. Every earlier failure is retained.
The final all_passed flag is True; final failed cases: none.
The new cases include Unicode, repeated context, deletion, tabs, quoted paths,
blank lines/spaces, untrusted document text, denial of an existing-file save and
a changed quoted document during approval. Actual file bytes/history determine
scores; a refusal only earns control credit at the intended stage.

Diagnostics confirmed double encoding of an appended JSON string, omission of
a requested period and context exhaustion. One failure used 3472 prompt tokens
plus 4720 generated tokens, reaching the 8192-token context before an action.
Counts, fixed comparison flags, requested thinking mode and known completion
reasons are retained without copying draft or reasoning text. The punctuation
trace inspected only a fixed synthetic fixture, not production documents.

The app now fixes normal text/tool temperature at the evaluated 0.2, keeps
reasoning enabled and explicitly fails done_reason=length responses before any
of their parsed calls execute. That refusal revokes saved-document observations
and requires review/new request; it never retries. The faster-generation
experiment was rejected after its task success regressed. Prompt examples alone
did not reach the target. Save comparisons now expose character/newline/tab
counts and final-newline/trailing-whitespace facts beside the complete JSON text.

document_append_requested(document) is a narrower alternative for a person
request beginning Append exactly followed by one JSON string. Code decodes one
literal layer from that current request, holds it in RAM, and gives the model
only the preserved target/context instructions. It offers this tool instead of
ordinary document_edit/document_save writers, and actual dispatch also refuses
those writers for that request. The model supplies only a document number.
An actual latest read in this turn, one binding attempt and the same full exact
approval are mandatory. The same prepare_edit/native publish/read-back guards,
quotas, retained versions and uncertainty recovery apply. No page/model output,
earlier turn, extra argument or wrapped Resume can supply/replay this binding.
Unsupported syntax retains the ordinary reviewed workflow; arbitrary model text
is never silently decoded or repaired. See DOCUMENT_EDIT.md for limits.

245 offline tests across thirteen suites passed. Seven new binding checks cover
data framing, control/size bounds, exact preservation, omitted model payload,
actual argument/dispatch restrictions, own approval during plans, callback
mutation, single use, replay refusal, current reads, stale state and uncertainty.
Six evaluator tests and the incomplete-response dispatch test also passed.
Three real Windows/Tk suites passed again: Documents, task progress and file
workers with Stop, fresh Resume, retained history and lost-confirmation recovery.

For a familiar comparison, this is a focused local ChatGPT-like application.
Its actual engines remain Gemma 4 E2B and Gemma 4 12B. Official Google model
documentation describes their local reasoning/tool-use roles; official OpenAI
model guidance distinguishes focused tasks from demanding workflows. There is
no matched GPT/Claude/Gemini benchmark for this installation, so no named-model
intelligence equivalence is claimed. Sources: https://ai.google.dev/gemma/docs/core/model_card_4
and https://learn.chatgpt.com/docs/models .

The declared target was met, supporting a provisional 8/10 for these short supervised document tasks.
The rating does not cover general intelligence, long multi-turn work, coding,
media quality or full Windows control. Two fixed seeds and developer-authored
synthetic cases are a small sample; hardware/cache state can change results.
No model weights, dependency, broader filesystem/network authority or mutation
retry were added. Restart the existing launcher to import the changes.
