# Document task reliability — 18 October 2026

This assistant remains a supervised prototype. Passing code tests is not a model
intelligence score. This evaluation does not justify an 8/10 general rating.

## Changes

Instructions and the document_save description now explicitly distinguish an
Artifact revision from a saved document version. Editing requires revising the
complete Artifact text first, waiting for that result, then saving its new
revision against the saved version actually read. Guidance explains exact-text
requests and prohibits retrying a denied/uncertain save. Code still enforces
approval, stale-state refusal, bounded workers and retained versions.

The offered tool list now comes from the trusted dispatch registry. Previously
the loop had a separate hardcoded schema list: restricting a fixture's dispatcher
left irrelevant tools visible. The model cannot change the registry or grant
permissions. No documents-only UI mode was added; routing/defaults are unchanged.

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

Next: simplify how a model requests document edits, then test unseen documents
and longer/multi-turn tasks. Any simpler tool must retain exact preview approval,
stale-state checks and version recovery. Never weaken checks to improve the score
or automatically retry a refusal. These small fixtures are not general benchmarks.
