# Website creation and visual Artifact previews

Requested by Alexander on October 22, 2026. Future work, not implemented.

## What happened and what exists

Alexander asked the local agent to build a website. It replied that it could not,
and the Artifacts sidebar did not appear. This is a person-reported observation;
the exact prompt, reply, model and tool trace have not been captured or reproduced.
Do not classify it as a confirmed panel failure or a completed website test.

Current code can create bounded document/code Artifacts. HTML, CSS, SVG and
JavaScript stay inert source text. ArtifactPanel.refresh opens the pane when a
new stored Artifact arrives; ordinary answer text does not automatically become
an Artifact. The person can also select Artifacts in the main sidebar and use
More > Draft from last answer. There is currently no HTML renderer or run button.

## First deliverable: Code / Preview

Add a person-controlled Preview tab beside Code in Artifacts for a single-page
HTML/CSS draft. A supported draft should be stored as a real Artifact and the
panel should open. The local agent should explain the difference between writing
website source, showing a local preview, and publishing a public website.

The first preview should be static, offline and created from the exact selected
Artifact revision. Start with scripts disabled and all external resources and
navigation denied, including CSS URLs/imports, images, fonts, frames, forms,
redirects and popups. No host filesystem access, uploads, downloads, personal
browser profile, Python bridge or arbitrary code execution. Escape model source
when showing it in the editor; never concatenate it into a trusted host script.
These are acceptance requirements, not claims of an existing renderer boundary.

Choose the renderer after verifying its Windows sandbox, network interception,
file access and lifecycle behavior with hostile fixtures. For an initial version,
an isolated browser-rendered screenshot can provide a visual preview inside Tk
without granting page interactions. Document CSS/layout limitations honestly.
Do not simply open generated HTML in the person's normal Edge session.

Preserve bounded source/history, explicit selected revision, unsaved edits,
Stop/New chat cleanup and the separate approvals for saving or publishing.
Show clear errors for unsupported content; never report a preview as delivered
unless actual rendering completed. Make the pane discoverable even if generation
fails or the model writes code in the chat instead of calling create_artifact.

## Later website capabilities

After the static preview is verified, consider interactive JavaScript in a
separately isolated runtime, multi-file projects and explicit website export.
Publishing/hosting needs a separate exact-destination approval and a defined
credential/deployment adapter. A local preview does not publish anything.
General Python, shell or downloaded-package execution is separate future work.

## Acceptance evidence before marking complete

- Native Windows fixture: HTML/CSS produces an actual visible layout; Code and
  Preview switch without losing unsaved edits or changing the selected revision.
- Offline malicious fixtures: script, event handler, network and CSS resource
  loads, form submission, navigation, frames, file URLs, downloads and popups
  cannot escape the proposed boundary. Assert denied network requests with fakes
  and exercise the actual renderer offline, rather than trusting page text.
- Bounded rendering: malformed/oversized documents, timeouts, Stop, New chat,
  replacement previews and closed views leave no stale replies or owned workers.
- A real local-model smoke request creates an Artifact and shows the preview;
  retain refusals and failures. This is separate from the deferred main scorecard.

No runtime code, dependencies, permissions or scorecard results changed in this
notes update. Alexander still owns his threat-model writing and small copy fix.
