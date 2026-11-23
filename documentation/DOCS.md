# Documentation setup

After installation, open Configuration and enter:

- **Documentation repository:** your private GitHub repository, in owner/repository format.
- **GitHub read token:** a fine-grained token for that repository with Actions: Read-only.

Save, then start the app. Enable Start on boot and Show in sidebar.
Open Documentation from the sidebar. If a preparation message appears, allow
the first download to finish and refresh. Residents need no additional login.

The app checks GitHub on startup and every four to five minutes. It downloads
the documentation when a new website package is available.
The saved documentation remains available during internet
outages or failed updates. Tokens must be replaced before their expiration to
keep automatic updates working.

If the logs report that the website package expired, run the documentation
repository's Build private documentation workflow in GitHub Actions and allow
the app to pick it up. For access errors, check repository spelling, token expiry, organization
approval, and Actions: Read-only permission.

Do not paste a token into any URL or share it with residents. House passwords and
Home Assistant API tokens are not required.

## Test an automatic update

1. In the private repository, wait for **Build private documentation** to finish successfully on `main`.
2. Open the app's **Log** tab. After the next scheduled check, look for **Documentation updated successfully** with the run ID from GitHub Actions.
3. Refresh the Documentation page to see the update.

If GitHub asks the app to slow down, it waits before checking again and keeps the saved website available.

## Language

The app follows the language selected by the current Home Assistant user. English
is the fallback; Latvian and Russian are selected automatically when their pages
are included in the private documentation package. Changing language in Home
Assistant also changes the open documentation article. No additional login,
translation API, token permission, or per-house language configuration is needed.

Standalone or isolated frames use English. Screenshots and technical identifiers
retain their original content. Future articles need their own translated source
files in the private repository; this app selects existing translations and does
not send private articles to an external translation service.

## Appearance

The documentation uses the surrounding Home Assistant frame's colours and font,
including custom themes. Theme changes are picked up while the page is open.
Standalone or isolated frames fall back to the device's light/dark preference.
Screenshots retain their original colours. No additional permissions are needed.

Use the sun/moon button to switch this documentation between light and dark.
The selection is remembered in this browser. Select Auto to follow Home Assistant
again; this does not change the rest of Home Assistant's theme.

The approved PICHE image appears in the app list and on the app information page.
Home Assistant's sidebar uses its separate book icon; the sidebar panel icon
setting does not accept a PNG image.
