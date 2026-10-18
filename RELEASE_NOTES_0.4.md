# Neurix Hub Alpha 0.4 — first public source release

**Status:** Open-source alpha, Windows, unsigned build. Not yet signed by SignPath Foundation.

## Highlights

- Check the global GitHub catalogue for available Neurix AI releases.
- Compare available releases against locally cached installers.
- Download selected official installers with consent and validate SHA-256 and size.
- Preserve local installer cache and allow manual rollback to a cached installer.
- Continue working with locally cached installers while offline.
- Build and test the Windows application using GitHub Actions.

## Important limitations

- Neurix Hub does **not** determine which Neurix AI version is installed on Windows.
- Cached installers do not imply an application is installed.
- Neurix Hub does not automatically run downloaded installers.
- Windows installer builds are **unsigned** pending a future code-signing approval.
  Do not bypass Windows security warnings to run unsigned software.

## Installation

For this initial public source release, use the GitHub **Source code (zip)**
download. Build instructions are in the [README](README.md).
The CI workflow generates an unsigned Windows installer artifact for verification;
it is not a signed official binary release.

## Code signing policy

See [Code signing policy](CODE_SIGNING_POLICY.md).

## License

MIT — see [LICENSE](LICENSE).
