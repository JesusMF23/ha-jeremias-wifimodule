# Releases and maintenance

The user-approved channel is normal GitHub releases, including during initial development before 1.0.0. Do not label a beta tag as a stable version, retag an existing release, or move a published tag.

1. Update `manifest.json`, `const.py` VERSION and CHANGELOG to the same plain `X.Y.Z` version. No `v`, beta or rc suffix.
2. Open a PR and pass Validate. It tests the minimum supported HA and latest stable HA, Python/frontend tests and formatting, hassfest and HACS. Review any hardware limitations in VALIDATION before merging.
3. Merge into main, then push the immutable matching tag at that commit, e.g. `git tag 0.6.0` and `git push origin 0.6.0`.
4. The Release workflow calls Validate on that exact tag. Only after every job passes does it verify that the commit belongs to main, validate all version sources, build the install ZIP/checksum and create a normal release with `--prerelease=false --latest`. Failed validation publishes nothing. A rerun cannot silently overwrite an existing release.
5. Install that release through HACS and restart HA. Confirm installed/available versions match and the update entity is off, not merely that the custom panel displays the expected assets. Record any live acceptance separately.

Local packaging: `python scripts/release.py --tag 0.6.0 --output dist`. This validates and packages without publishing. The ZIP retains the previous distribution structure: `custom_components/wifimodule/` plus LICENSE, extracted into the HA configuration directory. HACS downloads the tagged integration directory, with main hidden from its selector. GitHub release notes are generated from the merged PRs.

## Update notification investigation

The repository previously contained only prereleases. In HACS, when beta display is off and no normal release is available, `display_available_version` can fall back to `last_commit`, while `display_installed_version` remains the installed beta tag. Thus having the latest integration code does not necessarily make the update entity compare equal. Tracking main can also expose documentation-only commits as updates. This path was reproduced against the upstream HACS version-selection code; it is not proof of a particular installation’s persisted metadata.

Publishing a normal release gives HACS an unambiguous release channel for both beta settings. Canonical tag/manifest/VERSION checks prevent a second source of drift. Hiding main reduces accidental branch tracking, but existing installations that explicitly selected main must choose the normal release once. Never edit HACS storage or disable its update entity as a workaround. If the notice persists after installing the normal release and restarting, collect the update entity’s installed_version/latest_version and HACS repository details via its UI.

## Maintenance

Dependabot checks pip development tools, npm formatting tools and GitHub Actions weekly, opening reviewable PRs. Actions are pinned to commit hashes. CI tests both HA 2026.9.0 (minimum) and latest stable, and runs every Monday even without source changes. Dependabot PRs are not auto-merged. Dependency alerts and security updates are enabled in repository settings where the authenticated owner has access. Code owners remain responsible for review.

The integration declares no extra runtime Python packages. Development dependency updates must not silently raise the minimum supported HA version. The owner has authorized HACS catalogue submission with 1.0.0; these workflows do not submit a listing PR automatically.
