# Documentation for Home Assistant

A pilot Home Assistant OS app that displays a private MkDocs website using the
existing Home Assistant login. Residents need no GitHub account or separate
documentation password. The app opens in the Home Assistant sidebar.

Installer repository URL: https://github.com/picheha/home-documentation-app

[Add this app repository to Home Assistant](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fpicheha%2Fhome-documentation-app)

This repository contains application code and the approved PICHE app icon/logo.
Do not add private articles, screenshots, built HTML, tokens, or Home Assistant
credentials here.

## Status

Version 0.1.7 is prepared for a one-device pilot. Python behavior is covered by
automated tests. A Home Assistant Green installation and ARM container build
still need verification before rollout to other houses.

## Installation after this repository is hosted

1. In Settings > Apps > Install app, open the three-dot menu > Repositories.
2. Add this installer's GitHub repository URL, then refresh the store.
3. Select Documentation and Install.
4. In Configuration, enter the private documentation repository as owner/repository
   and its GitHub read token. Save.
5. Enable Start on boot and Show in sidebar, then Start.
6. Open Documentation. The initial download may take a moment; refresh if the
   preparation message is still visible. Look in the app's Log tab if needed.

Older Home Assistant versions call Apps "Add-ons" and Install app "Add-on Store".
The app repository URL must be readable by Home Assistant. Do not embed tokens
in a repository URL. The easiest distribution uses a public code-only installer
repository and a separate private documentation repository.

## Required documentation build

The private repository must have a workflow named `.github/workflows/build-docs.yml`
that runs on the `main` branch and uploads a ZIP artifact named `documentation-html`
using the current GitHub upload-artifact action. The app only accepts completed,
successful push, manual, or scheduled runs from that repository and workflow.
The archive must have `index.html`, `search/search_index.json` with nonempty docs,
and `version.json` at its root. `version.json` must contain the build's commit SHA
and run ID, for example:

```json
{"commit": "THE_FULL_BUILD_COMMIT_SHA", "run_id": "THE_BUILD_RUN_ID"}
```

The artifact's GitHub SHA-256 digest is verified before extraction. All website
links and assets must use relative URLs for Ingress. MkDocs with
`use_directory_urls: false` is suitable.

## Language selection

See [language support](LANGUAGES.md) for translated app settings, the preparation
screen, and how Home Assistant displays the sidebar title.

The app follows the active Home Assistant user's language by reading the surrounding
page's language attribute. English is the default. Latvian and Russian pages are
selected automatically when present at matching `lv/` and `ru/` paths in the private
website package. Each language should have its own search index and translated
navigation. Missing languages or pages fall back to English. Isolated frames and
standalone pages use English. No Home Assistant API permission is required.

The app selects existing translations; it does not generate translations or send
private documentation to an external service. New articles need translated sources
in the private repository. Original screenshots and identifiers are preserved.

## One-time GitHub authorization

Create a fine-grained personal access token in GitHub, select only the private
documentation repository, and grant repository permission **Actions: Read-only**.
GitHub includes Metadata read access automatically. No write access, house ID,
Home Assistant password, or Home Assistant API token is needed. An organization
may require an owner to approve the token. Set an appropriate expiration and
replace the token in Configuration before it expires. Do not post it in issues,
screenshots, source code, or chat. The token is saved in Home Assistant app
options; handle Home Assistant backups as sensitive.

For a larger fleet, provision an independently revocable credential per
installation or use a managed delivery service. The pilot does not implement
fleet credential lifecycle management.

## Updates and offline use

The app checks GitHub on startup and every four to five minutes. Optional MQTT
notifications trigger an immediate check. For the local
Mosquitto broker, enter only the MQTT username and password. See the
[notification pilot setup](documentation/DOCS.md#test-updates-triggered-by-github).
New HTML, images, and search files are installed together, without rebuilding the
app container. A failed download or validation leaves the saved website available.
Downloaded files survive app restarts. Uninstalling the app can remove its data.

GitHub Actions artifacts expire according to the build's retention policy.
If there is no unexpired package for a new installation, run the documentation
workflow again. Existing installations continue serving their saved copy.
For the 60-house rollout, plan durable versioned delivery rather than relying
on short-lived artifacts alone.

## Appearance

The website follows colours and fonts from the same-origin Home Assistant frame,
with system light/dark fallback for standalone or isolated frames. It reads only
an explicit list of CSS presentation variables; it does not inspect Home Assistant
state, credentials or API connections. Screenshots are not recoloured.

The sun/moon button switches documentation between light and dark and remembers
the choice in this browser. Auto returns to following Home Assistant.

The approved PICHE brand image is included as `documentation/icon.png` and
`documentation/logo.png` for the app list and app information page. The sidebar
continues using a Material Design book icon, which is a separate Home Assistant
setting.

## Security and access

Only the Supervisor's internal Ingress address (`172.30.32.2`) may access the
web server. There is no exposed host port, privileged mode, host folder mapping,
or Home Assistant API permission. All signed-in Home Assistant users can see the
panel (`panel_admin: false`); it is not per-document or per-house authorization.
The published material should be appropriate for every user on that installation.

GitHub credentials are sent only to `api.github.com`, never to redirected download
storage hosts. The website server serves only a validated package, never the app
options or download state. Updates reject traversal paths, symlinks, invalid
checksums, oversized archives, empty search indexes, and mismatched build versions.
The app trusts the documentation repository's approved build and HTML content.

## Development

Run `python -m unittest discover -s tests -v`. The included CI also builds the
container on an amd64 Linux runner. It does not replace an ARM Green pilot test.

The container uses the official Home Assistant base image and Paho for MQTT
notifications. No private documentation content is bundled in the installer.

References: [Home Assistant Ingress](https://contributors.home-assistant.io/apps/guides/ingress/),
[app configuration](https://contributors.home-assistant.io/apps/reference/configuration/),
[GitHub artifacts API](https://docs.github.com/en/rest/actions/artifacts).
