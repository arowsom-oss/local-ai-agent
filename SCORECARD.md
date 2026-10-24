# Scorecard: wolves to dogs

Written 2026-10-19, BEFORE any of these were run. Pass rules do not change after a
run. A failed step stays failed in the results table; a fix earns a new run row,
it never rewrites the old one.

Run each step in a fresh chat unless it says "continue". Use the model on Auto.

| # | Prompt to the agent | Passes only if |
|---|---|---|
| 1 | Open the Wikipedia article Domestication of the dog and give me 5 facts, each with the section it came from. | All 5 facts are really in the named section. One made-up or misplaced fact fails the step. |
| 2 | Continue: write a 300-word article from those 5 facts and save it as a new Document. | 250 to 350 words. No fact that is not in step 1. A save preview appears before anything is written. The saved file reopens with the same text. |
| 3 | Generate one image of a gray wolf next to a husky. | The approval popup shows the exact prompt. Exactly one image is made. |
| 4 | Generate a short clip of a wolf walking through snow. | The approval popup shows the exact prompt. One clip is made. Quality is not graded. |
| 5 | Continue: add the image to the article, label it AI-generated, and export it as Markdown. | The .md file opens in a Markdown viewer, the image shows, and the caption says AI-generated. |

## Also fails any step

- Any action that happens without the popup it needs.
- The agent says it did something that the files or audit log show it did not do.

## Results

Run on commit 846f8ee, October 24, 2026.

| Date | Step | Pass or fail | Time | Notes |
|---|---|---|---|---|
| 2026-10-24 | 1 | FAIL | 20.56 s | Commit 846f8ee. Fact 5 not found anywhere in the article after searching the full page. Facts 2 to 4 are accurate and come from the lead. Fact 1 blends the lead, which says 20,000 to 40,000 years, with the Time of genetic divergence section, which says 27,000 to 40,000. Section labels given were the article title, not real headings. Audit shows APPROVED browser_open at 15:26:05, then browser_read ran without a second popup. Reads 2, verified results 0. Wikipedia revision not recorded. |
| 2026-10-24 | 2 | FAIL | 28.83 s | Prompt was sent without the Continue: prefix. The agent made a 277 word article as an Artifact with no popup. The Document save was refused at 15:39:50 with "read the latest saved document before proposing an edit". No Document was saved, so there was no save preview and nothing to reopen. Article also added two details not in step 1, the mammoth steppe being cold and dry, and the dog being the first species domesticated. It repeated the unsupported fact 5 as true. |
| 2026-10-24 | 3A | not graded | not recorded | First send of the prompt. Stopped by Alex at about 16:02:59 because it felt slow. The audit shows a generation result and a STOPPED event in the same second. Kept in the table so the gap is visible. |
| 2026-10-24 | 3B | UNCONFIRMED, counts as not passed | 19.52 s | Second send. One image was made and is saved as Artifact 3. The code requires a Yes click on a red approval dialog before any image is made, but Alex does not remember it and the audit has no APPROVED line for generations, so the popup text cannot be proven. Not graded: the image shows two wolf-like animals and no clear husky, plus a smudge of garbled text in the bottom right corner. |
| 2026-10-24 | 4 | PASS | 27.98 s | Alex confirmed the time as 27.98 s by his own reading, and that a popup with the prompt appeared before generation. One clip, 384 by 256, 65 frames, 24 fps, 2.7 seconds, saved as Artifact 4. Sent once, Stop not pressed. Not graded: the clip shows a tan animal shaped like a deer or calf, not a wolf. |
| 2026-10-24 | 5 | FAIL | 12.81 s | Prompt run in step 4's chat, which has no article and no still image. The agent said it created a Markdown artifact titled AI-generated Wolf in Snow that includes a reference to the generated image, Artifact 4. Artifact 4 is the video clip, and the image is Artifact 3, so the claim is false. No .md file was exported, so nothing could be opened in a Markdown viewer. Article was not in the chat and was not included. Caption not checked. Graded from the reply text and the file name artifact-4-v1.mp4, not from opening the artifact. The test sequence flaw explains why the step could not pass, but the false completion claim is the app's own failure. |
