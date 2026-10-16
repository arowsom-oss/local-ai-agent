# Local AI Agent with Code-Enforced Restrictions

A small AI agent that runs entirely on my laptop with [Ollama](https://ollama.com) and a local Gemma model.
It can browse two approved websites, download files, and read files I give it.
**Every restriction is enforced in Python code, not in the prompt**, because a model can be talked out of
its instructions (prompt injection) but it can't talk its way past an `if` statement.

## What it can and can't do

| Can | Can't |
|---|---|
| Read pages from an allowlist of sites | Open apps, change settings, run commands |
| Download files into its own folder | Delete anything (it has no delete tool at all) |
| Read files I attach, inside a sandbox folder | Read files outside the sandbox |
| Do math with built-in tools | Use any tool not on the allowlist |

Anything risky (reading a file, contacting the internet, saving a download) shows a **Yes/No popup with No as the default**.

## Security design (and why)

- **Deny by default.** Tools, models, websites and file types are all allowlists. Anything not listed is refused.
- **The gate lives in the core, not the UI.** `agent_core.run_turn` asks for approval before any risky tool runs,
  so neither the terminal version nor the window can skip it.
- **Path jail.** `read_file` resolves the path and refuses anything outside `sandbox/`, so `../secret.txt` fails.
- **URL checks that can't be fooled by tricks** like `https://en.wikipedia.org@evil.com` (the real host is `evil.com`),
  wrong ports, or redirects (redirects are never followed).
- **Downloads:** own folder only, never overwrite (`open(..., "xb")` fails if the file exists), filename chosen by
  code not the model, Windows device names like `CON` blocked, 200 MB cap counted while streaming
  (the server's `Content-Length` isn't trusted).
- **Attach file:** I pick the file in a normal file dialog, so the model never chooses a path. Text types only,
  1 MB cap. The size is checked on the bytes actually read, not on an earlier size lookup, to avoid a
  **TOCTOU** (time-of-check to time-of-use) gap.
- **File contents are labelled as data**, not instructions. That helps a little; the popup is the real defense.
  `sandbox_examples/evil.txt` and `evil2.txt` are prompt-injection test files I used.
- **Audit log.** Every tool request is written to `audit.log` as JSON Lines: `approved` *before* a tool runs and
  `result` after, so a crash mid-tool still leaves evidence. `json.dumps` escapes newlines, which blocks
  **log injection** (faking an extra log line). The log sits outside the sandbox, so the agent can't read it.
- **Auto-compactor.** Long chats are summarized to fit the model's context window. The summary is inserted as a
  labelled *user* message, never a *system* message, because promoting model-written text to the highest
  authority would be privilege escalation.
- **No network exposure.** Ollama has no login, so its port stays on `127.0.0.1`.

- **Stop button.** Pressing Stop (or Esc) sets a flag that the loop checks before every model call and right
  before every tool runs, so a reply that asks for several tools can't sneak the rest through.
- **New websites need a popup.** A site that is not on the allowlist can be approved read-only, for this chat only.
  The site name in the popup is read by code from the URL, never written by the model, and the list of approved
  sites is not a tool parameter, so the model has no way to add one itself. Raw IP addresses, `localhost`, `.local`
  and similar names are refused before any popup (that attack is called SSRF).
- **DNS rebinding blocked.** Before fetching or downloading, the code looks the site up once, refuses it if *any*
  address is private or local, then connects to the exact IP it checked while still verifying the HTTPS certificate
  against the real site name.
- **Refusals show in the chat.** When code blocks something, an orange "Blocked:" line says so, so a code refusal
  can't be mistaken for the model refusing on its own.

## Run it

1. Install [Ollama](https://ollama.com) and pull a model: `ollama pull gemma4:e2b`
2. `pip install -r requirements.txt`
3. Copy `identity.example.py` to `identity.py` and fill in your details.
4. Edit the folder paths at the top of `agent_core.py` and `download.py` if yours aren't `C:\dev\agent`.
5. Double-click `start_chat.bat`, or run `python chat_window.py`. (`python agent.py` is the terminal version.)

## Known limits

- The approval popup only works if the person reads it. Too many popups train people to click Yes (approval fatigue).
- Labelling file contents as data does not stop prompt injection; it only makes it less likely to work.
- Summaries lose detail, so the agent can forget things from long ago in a long chat.

## How it was built

I built this with help from an AI assistant (Claude), step by step. I tested each feature on my own machine and
can explain each security decision above.
