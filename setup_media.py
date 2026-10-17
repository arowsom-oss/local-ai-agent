"""Person-run installer. Never imported or exposed as an agent tool."""
from pathlib import Path
import argparse
import json
from media_assets import ROOT, SPECS


def install(kind):
    from huggingface_hub import HfApi, snapshot_download
    repo, patterns = SPECS[kind]
    revision = HfApi().model_info(repo).sha
    ROOT.mkdir(exist_ok=True)
    print(f"Downloading {kind}: {repo} at {revision}", flush=True)
    path = Path(snapshot_download(repo, revision=revision, cache_dir=ROOT / "hub",
                                  allow_patterns=patterns + ["README.md", "LICENSE*"], max_workers=2)).resolve()
    manifest = {"repo": repo, "revision": revision, "path": str(path.relative_to(ROOT.resolve()))}
    (ROOT / (kind + ".json")).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"{kind} installed; runtime inference will use local files only.", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=[*SPECS, "all"])
    args = parser.parse_args()
    for kind in SPECS if args.kind == "all" else [args.kind]:
        install(kind)
