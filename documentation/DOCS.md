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

## Test updates triggered by GitHub

Configure the following in the app's **Configuration** tab. Save and restart
the app once so it can connect with the new configuration.

| Option | Value |
| --- | --- |
| `mqtt_host` | Broker hostname or IPv4 address |
| `mqtt_port` | 8883 for the default TLS listener, or the port your broker uses |
| `mqtt_tls` | Keep enabled for the shared broker. Disable only for a trusted local pilot listener that uses plain MQTT. |
| `mqtt_topic` | Optional. Default is `piche/documentation/ready`. |
| `mqtt_username`, `mqtt_password` | Subscriber credentials for this topic |

Give each house subscription access only. Use a separate publisher credential
for GitHub. The broker message contains only the GitHub Actions build run ID.
The app downloads and verifies the website using its existing GitHub read token.

**Local pilot test**

1. Point the app at an MQTT broker reachable by the Green. Open the app log and
   look for **Document update notifications connected**.
2. Change a test line in the private documentation repository and wait for
   **Build private documentation** to succeed. The number after `/actions/runs/`
   in the build's URL is the run ID.
3. Publish that number as plain text on the configured topic, with QoS 1 and
   retain enabled. For an existing Home Assistant MQTT integration connected to
   the same broker, use the **MQTT: Publish** action under Developer Tools.
4. Confirm the new build appears in the app log. Reload the Documentation page
   and confirm the edit appears. Repeat with the app disconnected and reconnect
   it after publishing to test catch-up.

**Automatic test from GitHub**

Copy [the notification workflow example](https://github.com/picheha/home-documentation-app/blob/main/documentation/github-notify.example.yml) into
`.github/workflows/notify-documentation.yml` in the private documentation
repository. Set the repository variable `DOCS_MQTT_HOST` to a TLS broker
reachable from GitHub Actions and the houses. Set the Actions secrets
`DOCS_MQTT_USERNAME` and `DOCS_MQTT_PASSWORD` to the broker publisher
credentials. Set `DOCS_MQTT_TOPIC` and `DOCS_MQTT_PORT` as repository variables
if you use different values from the defaults.

An empty `mqtt_host` keeps the hourly schedule. With a broker configured, the
app checks on startup, after reconnecting, or when it receives a new build
notification. It retries short-lived download failures and keeps the cached
site if GitHub or the broker is unavailable.

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
