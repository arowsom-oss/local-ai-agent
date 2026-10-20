# Evidence workbook for Alexander

AI-assisted research notes, October 20, 2026. You chose to write THREAT_MODEL.md
and the next fix yourself. Neither is written or attributed to you here.
This is a source map and writing exercise, not a completed security audit.

Source baseline: 36e15150abbf97b175136e88effde9335386f249. This update changes
tests/docs/CI only, so the runtime line references below remain valid.

## Write your own threat model

Start with your own answers:

- What are your assets? Consider personal files, generated work, microphone/
  screenshots, credentials, approval authority, GPU/RAM and availability.
- Who controls each input? Separate a malicious web page, a poisoned local
  document, hostile recorded speech, model mistakes and another local program.
- Draw the boundary from untrusted content to model proposal to Python
  validation to exact approval to the limited adapter and verified result.
- Which risks remain even when code works? Include deceptive prompts, mistaken
  human approval, model hallucinations and the absence of a VM/OS sandbox.
- Which claims have tests, which are static observations, and which are unknown?

Find the actual checks and explain them in your own words:

| Question to answer | Runtime evidence at the baseline |
| --- | --- |
| Can a page invent a settings/shell tool? | agent_core.py:226 registry; :545 unknown-tool refusal |
| Can a page make downloads run? | agent_core.py:90 disabled tool; :538 dispatch refusal |
| Can model arguments approve themselves? | agent_core.py:124 exact keys/types; :136 literal True and copied approval args |
| Does host approval authorize arbitrary outbound data? | agent_core.py:811 exact-address approval; :773 new-site decision; :850 frozen approved fetch address |
| Can a plan authorize search? | agent_core.py:821 search still asks independently; browser_tool.py:385 GET-form/text checks |
| What enforces network pinning? | fetch.py:53 checks every resolved address; browser_tool.py:208 resolves once, :218 disables proxies/redirects, :225 preserves TLS SNI |
| What limits a hostile page? | browser_tool.py:127 JS off, :128 offline browser, :134 context routing; :186 request handler; :334 password exclusion |
| Can pixels/transcripts dispatch actions? | agent_core.py:444 tool-free observation; :455 refuses returned tool calls; chat_window.py:715 transcript review and explicit editor insertion |
| Can stale document approval write? | workspace_documents.py:237 consumes proposal, :241 expiry, :249 inventory, :252 exact old bytes; workspace_native.py:114 disables replacement |
| What protects filesystem targets? | workspace_native.py:49 rejects reparse/unexpected types, :50 rejects hardlinks, :54 pins ancestors |
| What stops/rechecks scratch edits? | notepad_tools.py:64 proposal; :80 one-use execute, :83 expiry, :88 unchanged target/text |
| Are workers an OS sandbox? | process_guard.py:15 Job lifecycle/commit limits; :69 startup gate; :127 Stop. These do not isolate all native code/network access. |

Read the surrounding function, not only the cited line. A warning label or
system prompt is guidance to the model, not an enforcement boundary. Search
filters block only specific text patterns; they do not recognize every secret.
Pixel normalization is not a guarantee that a media decoder has no bugs.
The app does not promise protection from arbitrary same-user malware.

Pair claims with test evidence: test_browser_network.py, test_browser_search.py,
test_prompt_injection.py, test_workspace_documents.py, test_workspace_live.py,
test_model_vision.py and test_speech_reference.py. Distinguish fake dispatch
checks from real Windows/native tests and live-model experiments.

When you have a draft, send it for review. I can check each claim against source,
find missing attacker assumptions, and review wording without claiming authorship.

## Your next small fix: copying the raw answer

Confirmed candidate, left unfixed for you:

1. chat_window.py:311 clean() removes backticks and bold markers for display.
2. poll() retains the original reply in last_raw_answer and the display version
   in last_answer. Artifacts already uses the raw reply.
3. chat_window.py:1280 wires Copy last answer to last_answer. Copying an answer
   containing Markdown/code fences therefore copies altered content.

Reproduce with a synthetic answer containing a fenced Python snippet and
literal backticks or paired asterisks. Compare the copied text with the original
reply, including line breaks. No personal clipboard content is needed.

Decide which value Copy should use, make the small change yourself on your own
branch, and add a focused regression check. Explain the before/after behavior
and how you verified exact copied text in your PR. Keep AI help disclosed.
I have not changed the callback or created a human-authored commit.
