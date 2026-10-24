"""The large model is pickable by hand only. Auto routing must never return it."""
from types import SimpleNamespace as NS
from unittest.mock import patch

import model_router as router


def classifier_reply(task):
    return NS(message=NS(content='{"task": "%s"}' % task, tool_calls=None))


def reset():
    router._active = None
    router._reasoning_hold = 0


def test_large_model_is_allowed_and_selectable():
    assert router.LARGE_MODEL in router.ALLOWED_MODELS
    assert router.LARGE_MODEL in router.MODEL_CHOICES


def test_auto_never_returns_large_model():
    prompts = ("hi", "Explain photosynthesis", "Debug this deadlock", "Save a document called notes")
    for task in ("general", "reasoning"):
        for prompt in prompts:
            reset()
            with patch.object(router, "chat", return_value=classifier_reply(task)):
                chosen = router.choose_model(prompt)
            assert chosen in (router.FAST_MODEL, router.REASONING_MODEL), (task, prompt, chosen)


def test_auto_ignores_a_classifier_that_names_the_large_model():
    reset()
    with patch.object(router, "chat", return_value=classifier_reply(router.LARGE_MODEL)):
        assert router.choose_model("Explain photosynthesis") == router.FAST_MODEL


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
    print("PASS test_large_model_manual.py")
