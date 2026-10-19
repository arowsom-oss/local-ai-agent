# Local setup and collaboration handoff

Observed on Alexander's Acer laptop on 2026-10-19. This is a storage and setup
inventory, not a new inference or quality test. Recheck running processes and
Git status before changing anything; another collaborator may have newer work.

## Primary installation

Use `C:\dev\local-ai-agent` as the primary app checkout. Its origin is
`https://github.com/arowsom-oss/local-ai-agent.git`. At inspection, its clean
`main` checkout was `7b144f1473e2aa09ae32d236942af977608f5085`, including the
merged implementation PR #1 and scorecard PR #2. Preserve the scorecard's fixed
pass criteria and record failures honestly. The older development branch is
historical; do not copy it over newer main files.

Keep implementation work in branches based on current main. Fetch before
starting, inspect existing changes, and use a PR rather than editing or resetting
the primary installation's main branch. Do not overwrite `identity.py`, website
approvals, generated outputs, saved documents or another collaborator's changes.
The separate `C:\dev\agent` installation also remains outside this cleanup.

## Local models

`media_assets.py` resolves its cache beside its own source file. For this
installation the root is `C:\dev\local-ai-agent\model_cache`.

| Kind | Manifest | Approved repository | Snapshot revision |
| --- | --- | --- | --- |
| Image | `image.json` | `stabilityai/sd-turbo` | `b261bac6fd2cf515557d5d0707481eafa0485ec2` |
| Video | `video.json` | `ali-vilab/text-to-video-ms-1.7b` | `8227dddca75a8561bf858d604cc5dae52b954d01` |
| Audio | `audio.json` | `Systran/faster-whisper-tiny.en` | Read the local manifest |

Image and video manifests resolved within that cache. All file groups required
by the current `SPECS` patterns were present. This checks paths and file presence;
it does not verify weight hashes, perform inference or establish model quality.
Generation still requires a compatible Python environment, CUDA and approval.

The image cache occupied about 2.58 GB, video 3.67 GB and audio 0.078 GB (decimal
file sizes). Keep these active assets. Do not run setup again simply because a
different checkout cannot find them: a checkout has its own relative cache root.
Do not copy gigabytes of weights into a branch or add an unreviewed model-chosen
path option. Inspect paths first and propose any storage configuration separately.

Ollama's text/vision models use its separate storage and fixed local endpoint.
This inspection did not relocate or remove Ollama models.

## Older workspace and cleanup status

The earlier Codex workspace is under
`%USERPROFILE%\Documents\Codex\2026-10-15\i-m-a-high-school-student`.

| Location | Observed size | Decision |
| --- | --- | --- |
| `work\agent_runtime` | 4.99 GB | Keep: a running Python app used this interpreter; old launchers also reference it. |
| `work\strata_trial\.venv` | 0.732 GB, 7,238 files | Disposable environment from the completed, rejected experiment; removal was blocked by automatic policy review. It is still present. |
| Other Strata source, engine and unpacked dependencies | About 0.685 GB | Keep: includes source and untracked files; not treated as disposable without further review. |
| Source snapshots, ZIPs, reports and test evidence | Small relative to environments | Keep the development and recovery record. |

The old workspace had no model cache or model-weight files of 256 MiB or larger
in this scan. Its large files were runtime DLLs and test dependencies. Two Python
GUI processes were open; neither was closed. Their command lines alone do not
prove the source directory of each app. Do not delete the old runtime while it
may be in use, or delete the whole workspace to save a few GB.

The primary model cache also contains the abandoned
`hub\models--Wan-AI--Wan2.1-T2V-1.3B-Diffusers` directory, about 25.61 GB including
incomplete downloads. The current image/video/audio manifests do not reference
it. Earlier removal was blocked; no deletion was retried or performed. Treat it
as a separate cleanup candidate requiring review of any other local tools that
might use it. Do not confuse this directory with the active ModelScope video
snapshot above. No storage was reclaimed in this pass.

## Access for both collaborators

GitHub shares tracked source, documentation and review history. `.gitignore`
excludes model weights, local identity, environments, generated media, saved
documents and audit data. A successful clone therefore does not include them.
Both collaborators can use these local assets only if their sessions have access
to this laptop's filesystem. Repository access alone cannot establish that.

Check the primary checkout and local manifests independently in each local
session. Avoid running setup/download or changing paths until the existing
cache is inspected. Do not upload weights, personal files, credentials or logs
to make a remote session work. Share failures and setup findings in a reviewed
documentation change; do not silently replace the other collaborator's work.

This handoff changes no runtime code, permissions or model configuration. No
application test suite or generation benchmark was rerun for this documentation
and storage inspection.
