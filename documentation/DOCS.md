# Documentation setup

After installation, open Configuration and enter:

- **Documentation repository:** your private GitHub repository, in owner/repository format.
- **GitHub read token:** a fine-grained token for that repository with Actions: Read-only.

Save, then start the app. Enable Start on boot and Show in sidebar.
Open Documentation from the sidebar. If a preparation message appears, allow
the first download to finish and refresh. Residents need no additional login.

The app refreshes documentation on startup and roughly hourly. Restart the app
to check immediately. The saved documentation remains available during internet
outages or failed updates. Tokens must be replaced before their expiration to
keep automatic updates working.

If the logs report that the website package expired, run the documentation
repository's Build private documentation workflow in GitHub Actions, then restart
this app. For access errors, check repository spelling, token expiry, organization
approval, and Actions: Read-only permission.

Do not paste a token into any URL or share it with residents. House passwords and
Home Assistant API tokens are not required.
