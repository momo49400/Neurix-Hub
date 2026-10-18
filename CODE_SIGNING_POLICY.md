# Code signing policy

## Project

Neurix Hub is an open-source Windows application distributed under the MIT license.
Official source repository: https://github.com/momo49400/Neurix-Hub

## Signing status

**Code signing is not yet enabled.** The project is preparing an application for
SignPath Foundation. Any currently available Windows installer must be considered
**unsigned** until its signature is independently verified.

If the project is accepted by SignPath Foundation, the intended attribution is:

> Free code signing provided by SignPath.io, certificate by SignPath Foundation

The above is a *planned* arrangement, not a claim that current binaries are signed.

## Signing roles and release approval

- Maintainer and author: [momo49400](https://github.com/momo49400).
- Reviewer: repository maintainer reviews external contributions before merging.
- Signing approver: repository maintainer; manual approval required for every signing request.

These roles will be reviewed and configured in SignPath before any signing request.

## Build provenance and release verification

Windows installer builds are defined in
[GitHub Actions](.github/workflows/windows-build.yml).
The workflow installs pinned Python dependencies, runs automated tests,
builds the application with PyInstaller, packages it with Inno Setup,
and generates a SHA-256 checksum.

Workflow artifacts are unsigned and are **not** automatically published as releases.
Users should download only official release assets and verify their signature
when a signed release becomes available.

## Privacy and network behavior

Neurix Hub retrieves the release catalogue from the project's documented
GitHub distribution repository to check for updates and, with user consent,
downloads selected installers from GitHub Releases. Startup update checks
may connect to GitHub automatically; refreshes and installer downloads are
otherwise initiated through the interface.

Local cache metadata and downloaded installer files are stored on the user's
device. The app does not require an account for its own interface.

Network requests to GitHub are subject to [GitHub's Privacy Statement](https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement).
Neurix Hub does not automatically run downloaded installers. Refer to the
[README](README.md) for limitations and installation details.

## Installation and removal

The Windows installer installs per user, creates a Start Menu shortcut,
and can optionally create a desktop shortcut. Removal is available through
Windows Settings > Apps > Installed apps. Locally cached data may remain
after uninstalling and can be removed by the user.

## Security

Do not disable Windows security features to run unsigned releases.
Report security issues privately to the repository maintainer;
do not include secrets in public GitHub issues.
