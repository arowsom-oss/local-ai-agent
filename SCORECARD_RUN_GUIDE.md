# Scorecard run prepared, not yet executed

October 20: the Windows computer-use JS runtime failed initialization twice
with "failed to write kernel assets: The system cannot find the path specified."
No scorecard prompt was submitted and no scorecard action/approval was taken.
Alexander chose to run it later. SCORECARD.md's rules and empty Results table
remain unchanged. A setup blocker is not an app pass or an app fail.

## Which code

The isolated local test source is an exact export of merged main
58adaf433d108c7b98703b4c0cd0b0c1331fb595, not the feature branch used by the
normal launcher. The prepared local launcher opens "SCORECARD MAIN 58adaf4".
It uses the already installed media runtime and model cache without copying or
downloading weights. Documents, generated files and audit data go into a
separate scorecard_main_run_01 folder under the local task's work directory.
Main's legacy video pipeline remains the pipeline under test.

The observation helper records prompts, replies, popup requests/decisions,
timings and test outputs without reasoning text. Use only the five public,
synthetic prompts below in that test window. Raw artifacts stay local.

## Exact prompts and chat sequence

1. Fresh chat, Auto:
   Open the Wikipedia article Domestication of the dog and give me 5 facts, each with the section it came from.
2. Same chat:
   Continue: write a 300-word article from those 5 facts and save it as a new Document.
3. New chat, Auto:
   Generate one image of a gray wolf next to a husky.
4. New chat, Auto:
   Generate a short clip of a wolf walking through snow.
5. Continue step 4's chat:
   Continue: add the image to the article, label it AI-generated, and export it as Markdown.

Review the actual exact-address, generation and save previews. Do not approve
unrelated requests to make a test pass. Do not add hints, retry a failed prompt,
restore old Artifacts manually, or change source/model settings during a run.
Record failures as they occur. If continuation steps lack previous outputs,
record that rather than inventing or silently supplying missing state.

## Grade against the existing rules

- Step 1: independently check every fact and its named article section. Record
  the Wikipedia revision/source used. Model citations alone do not earn a pass.
- Step 2: 250-350 words, using only the prior five facts; a save preview must
  precede the actual write, and saved bytes must reopen unchanged.
- Steps 3/4: exact prompt displayed, exactly one output. Video quality is not
  graded. A model claim without a completed file does not count.
- Step 5: actually open the exported Markdown in a viewer; verify the image
  renders and the caption says AI-generated. Source text alone is insufficient.
- Every step fails for a missing required popup or a false completion claim.

Add real outcomes, wall times, revision and evidence paths as new rows in
SCORECARD.md. Keep every failed row forever; fixes earn a new run row.
This guide intentionally awards no score. Send the completed output/evidence
for review; do not upload private conversation or audit history.
