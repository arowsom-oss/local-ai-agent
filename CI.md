# Reproducible Windows offline tests

.github/workflows/offline-windows.yml runs on every pull request and pushes to
main, using Windows and Python 3.12. It installs requirements-ci.txt, then runs
scripts/run_offline_tests.py without -O. No GPU packages, model weights or
Chromium download are required.

The runner executes all twenty-one classified offline suites in separate
processes. It refuses unclassified new test files, so adding a suite requires
an explicit offline/native classification. Thirteen native/GUI suites are excluded
because they require actual applications or desktop integration. These checks
do not run the scorecard or assess model quality.

Each test process gets a Python audit hook rejecting real socket/DNS
operations. A startup probe confirms it is active. This is a test tripwire,
not an OS network sandbox against arbitrary native libraries. Dependencies
are installed with Internet access before offline tests start.

Each suite has a sixty-second limit; failures are retained and all suites are
attempted. The job has a ten-minute limit. Summary JSON, per-suite logs and the
eight-page attack report are uploaded even on test failure.

The workflow uses full commit pins for actions, a read-only contents token,
no checked-out credentials, no deployment/secrets and a hosted runner. It uses
pull_request rather than pull_request_target. GitHub's security guidance:
https://docs.github.com/en/actions/reference/security/secure-use

Local equivalent:

    py -3.12 -m venv .venv
    .venv\Scripts\python.exe -m pip install -r requirements-ci.txt
    .venv\Scripts\python.exe -B scripts/run_offline_tests.py

Choose a fresh --output directory for each retained local run. Old injection
reports are never overwritten. A published workflow file alone is not evidence
of a successful hosted run: inspect its actual Actions result.
