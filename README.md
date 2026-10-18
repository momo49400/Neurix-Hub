# Neurix Hub Alpha 0.4 — Update Manager Engine

Preserves Alpha 0.3 global GitHub catalogue, verified downloads, local installer cache and manual rollback.

## New in Alpha 0.4

- Non-blocking **check for available releases at startup**, plus manual GitHub refresh.
- Compare the newest public release to the **newest locally cached installer**, not the installed application version.
- Friendly update messages and a direct button to select the newest release.
- Button shows **already in cache** when downloaded; no needless second download.
- Consent required before downloading. SHA-256 and size checked before caching. No automatic Setup execution.
- If offline, local library and previous installers remain available.

**Important:** A copy of an installer in the cache does **not** prove that Neurix AI is installed. Alpha 0.4 does not inspect the Windows registry or detect installed versions. The word "update" is a comparison of available versions and cached installers, not an automatic updater. Save SQLite conversations before downgrades.

## Security and code signing

- **Code signing policy:** [CODE_SIGNING_POLICY.md](CODE_SIGNING_POLICY.md)
- **Alpha 0.4 release notes:** [RELEASE_NOTES_0.4.md](RELEASE_NOTES_0.4.md)
- Current Windows installer artifacts are **unsigned**. SignPath Foundation approval is pending. Do not bypass Windows security protections to run unsigned builds.

## Installation / Windows build

1. Extract this ZIP to Downloads.
2. In PowerShell, run:

```powershell
cd "$env:USERPROFILE\Downloads\NeurixHub_Alpha_0_4_Source"
powershell -ExecutionPolicy Bypass -File .\build.ps1
powershell -ExecutionPolicy Bypass -File .\make_setup.ps1
explorer "$env:USERPROFILE\NH04\release"
```

This ZIP has an outer `NeurixHub_Alpha_0_4_Source/` directory; if extracted into a named folder, include the extra directory in the `cd` path.

The scripts build in `%USERPROFILE%\NH04` to avoid long-path problems; Inno Setup 6/7 is required for Setup generation. The installer runs per user without elevation, creates Start Menu shortcut, offers optional desktop shortcut. Cached data is stored under `%APPDATA%\NeurixHub` and is not cleaned during upgrade.

## Run checks without the GUI

```powershell
py -3 -m unittest test_cache test_distribution test_update -v
```

**Safety:** Never bypass Smart App Control or Windows security blocks to run an unsigned installer. Review and sign binaries before distributing widely.
