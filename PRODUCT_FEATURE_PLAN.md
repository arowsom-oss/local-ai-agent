# Product features and model candidates

October 22, 2026. Research and proposals, not implementation or download.
The current chat models are gemma4:e2b and gemma4:12b; they remain unchanged.
The comparison is about useful app capabilities, not claiming the local system
matches the reasoning quality or service scale of ChatGPT or Claude.

## Recommended product work

1. Saved chats and Projects: explicitly persist conversations and selected
   Artifacts, with titles, search, reopen, export and deletion controls. A
   project's instructions are person-authored; retrieved text stays untrusted.
   Restoring a chat must never restore old action approvals or stale browser IDs.
   This creates the storage foundation for later desktop/web continuity.
2. Document Q&A with citations: bounded, person-selected PDF/text imports, page
   references and retrieval over an approved collection. Start with plain text
   extraction; use OCR for scanned pages. Embeddings select relevant passages;
   the chat model answers from those passages, marks gaps and cites exact source
   IDs/pages. Never treat a retrieved document as authority or scan the whole PC.
   Correct source lookup and retrieval evaluation matter more than adding models.
3. Faster-feeling chat and honest controls: streamed visible text, prompt/load/
   generation indicators, token counts, active-model status and working Stop.
   Streaming must buffer and validate complete tool arguments before dispatch;
   partial JSON or interrupted output cannot become an action. Do not display
   private reasoning. Measure remaining Auto model switches and 60s idle reloads
   before changing retention or competing with the media memory policy.
4. Opt-in memory: show proposed preferences/facts and let Alexander approve,
   inspect, edit or forget them. Do not silently mine private chats, store secrets
   or confuse a saved memory with permission to act. Keep memory separate from
   source documents, tool results and person-controlled project instructions.
5. A better coding workspace: targeted, reviewable edits, responsive static
   HTML/CSS previews, multiple source files and explicit export. Existing static
   Preview / Code is delivered; interactive JavaScript, arbitrary execution,
   package installation and deployment need separate runtime/approval designs.
6. Study tools: turn selected notes into flashcards, quizzes, practice questions
   and a study schedule, showing the supporting pages. Check answers against
   sources and let the person correct them. This can use existing chat models;
   it does not require a new large model or automatic access to school accounts.
7. Research you can inspect: distinguish search snippets from opened/read
   sources, show citations and unsupported claims, keep a short source list and
   support human review. Existing web research is available; it is not a broad
   factual-accuracy guarantee. No model self-rating counts as verification.
8. Private web/mobile portal: one owner's login plus MFA, chat, explicit media
   requests and owned Artifacts, with a shared bounded GPU queue. No remote
   computer use. REMOTE_ACCESS_PLAN.md records the expanded school-access plan.

Suggested order: saved chats/Projects and context/cancellation reliability,
then selected-document Q&A, then a small model comparison. The private portal
depends on persistent owner-bound records, shared GPU scheduling and tested auth.
The human main scorecard remains deferred at Alexander's request; do not invent
results or use these proposals as a reason to merge unreviewed work.

## Open-weight model shortlist

Exact Ollama tags checked against primary model pages on October 22, 2026.
The listed sizes are rounded model downloads, NOT guaranteed runtime VRAM/RAM.
No candidate has been downloaded, benchmarked or added to the code allowlist.

- qwen3-embedding:0.6b: 639 MB, Q8_0. First specialist to consider for semantic
  search over approved notes, PDF passages and project text. This produces
  vectors; it is not a chat model. Compare against simple keyword search first.
  Batch or CPU indexing may avoid GPU residency conflicts, but throughput and
  retrieval quality still need measurement. Use the explicit 0.6b tag; do not
  assume the latest alias selects the smallest embedding model.
- qwen3.5:9b-q4_K_M: 6.6 GB. Multimodal/tool-capable candidate to compare against
  Gemma on coding, website Artifacts, reasoning and selected-image tasks. A
  plausible single-model test on 12 GB VRAM, not a promised fit or upgrade.
  Start with the existing 8192-token context and the same approval policies;
  account for visual input, context cache, runtime workspace and Windows use.
- qwen3.5:4b-q4_K_M: 3.3 GB. Smaller alternative if latency or measured memory
  headroom makes 9b unsuitable. Compare against e2b rather than assuming a new
  model is faster or more reliable. It covers similar roles, so both Qwen sizes
  need not become permanently active models.
- glm-ocr:q8_0: 1.8 GB. Optional specialist for scanned document text, tables and
  formulas. Try only if existing vision/plain PDF extraction fails useful test
  cases. OCR can misread numbers or hallucinate text; retain original pages and
  page coordinates for review. It is not the general chatbot or tool executor.

This laptop has 12 GB VRAM and 32 GB system RAM. Keep one heavy GPU workload at
a time and release it before image/video generation. Do not add all model sizes
together as if every installed model occupies VRAM. Conversely, downloading a
6.6 GB file does not establish that its inference uses only 6.6 GB. Neither CPU
fallback nor very large advertised context windows are assumed to be fast.

## Admission before integration

- Record exact tag/digest, quantization, license, installed Ollama/backend and
  client compatibility. Verify tools, images and think controls on this version.
  No silent dependency upgrade, remote model fallback or mutation retry.
- Use fixed synthetic coding, document, image and tool-schema tasks with the
  current Gemma baseline. Keep cold load, prompt processing, generation rate,
  full-turn latency, failures and sampled system/GPU memory separately.
- Require no degradation of code-enforced refusals, strict tool arguments,
  exact approvals and Stop semantics. Judge task success and cited answers,
  not model-family marketing charts or only tokens per second.
- Measure idle expiry, switching and media handoff too. Adding an embedding/OCR
  path must integrate with the lifecycle manager rather than bypass its queue
  or create untracked resident GPU models. Offline tests stay offline; real
  model downloads and benchmarks are separate, explicit development work.
- Keep Gemma and the current default until a candidate shows useful improvement
  for a defined role with enough measured memory headroom. Roll back a failed
  trial without deleting the person's weights, saved chats or generated media.

## Primary sources

- [Qwen3 embedding 0.6b](https://ollama.com/library/qwen3-embedding:0.6b)
- [Qwen3.5 9b Q4_K_M](https://ollama.com/library/qwen3.5:9b-q4_K_M)
- [Qwen3.5 4b Q4_K_M](https://ollama.com/library/qwen3.5:4b-q4_K_M)
- [Official Qwen3.5 9B model card](https://huggingface.co/Qwen/Qwen3.5-9B)
- [GLM-OCR Q8_0](https://ollama.com/library/glm-ocr:q8_0)
