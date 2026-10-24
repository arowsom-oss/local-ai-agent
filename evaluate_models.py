"""Person-run synthetic benchmark: no private prompts or agent tools."""
from pathlib import Path
import json
import time
from model_router import chat, release_models, FAST_MODEL, REASONING_MODEL, _get_client

TASKS = (
    ("addition", "Reply with only the number: 17 + 25.", "42"),
    ("multiply", "Reply with only the number: 8 multiplied by 7.", "56"),
    ("two-step", "Reply with only the number: start with 10, add 5, then multiply by 2.", "30"),
    ("classify", 'Reply with only general or reasoning: debugging a multi-threaded deadlock.', "reasoning"),
)


def evaluate(stop_event=None):
    results = []
    try:
        for model in (FAST_MODEL, REASONING_MODEL):  # The hand-chosen large model is never benchmarked unasked.
            for ident, prompt, expected in TASKS:
                if stop_event is not None and stop_event.is_set():
                    return "Model check stopped; the current server request may finish separately."
                started = time.perf_counter()
                response = chat(model=model, messages=[{"role": "user", "content": prompt}],
                    tools=[], think=False, options={"num_ctx": 2048, "num_predict": 48, "temperature": 0})
                seconds = round(time.perf_counter() - started, 3)
                answer = (response.message.content or "").strip()
                memory = None
                try:
                    memory = sum(m.size_vram for m in _get_client().ps().models if m.model == model)
                except Exception:
                    pass
                results.append({"model": model, "task": ident, "seconds": seconds,
                    "correct": answer == expected, "answer": answer[:200], "server_vram_bytes": memory})
        path = Path(__file__).resolve().parent / "benchmark_results.json"
        path.write_text(json.dumps({"tasks": "fixed synthetic tasks; not broad model-quality proof", "results": results}, indent=2), encoding="utf-8")
        return f"Model check: {sum(r['correct'] for r in results)}/{len(results)} exact matches. Report: {path}"
    finally:
        release_models()


if __name__ == "__main__":
    print(evaluate())
