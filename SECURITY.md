# Security reporting and checks

Do not publish credentials, private datasets, or exploit details in public
issues or PRs. Private vulnerability reporting was **disabled** when checked
on 2026-10-31. Arrange a private channel with the maintainer before sending
sensitive details; no reporting email or response-time guarantee is advertised.

Once GitHub private reporting is enabled and verified, this document will link
to that channel. Do not interpret this pending setup as an invitation to post
sensitive reports publicly.

Run `make audit` to check dependency compatibility and known advisories using
the locked dependency set. The vulnerability audit requires network access,
uses uv 0.11.19, and targets Python 3.12/Linux, including development dependencies.
uv still labels its audit command experimental, so CI pins its version.
No advisories are currently suppressed. Any future exception must record its
exact ID, reason, owner, and review date beside the audit configuration.

The CI workflow runs this audit for PRs, integration/release pushes, and weekly
after the workflow reaches the default branch. Dependency/service failures
fail the job; they are not clean audit results. Review Dependabot PRs manually.

Secret scanning and push protection were enabled when checked on 2026-10-31.
CodeQL default setup and Dependabot security updates were not enabled; their
activation remains pending. Scans cannot guarantee that code or packages are
safe. A leaked credential needs rotation even if its file is later ignored.
