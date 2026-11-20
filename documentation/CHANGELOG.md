# 0.1.6

- Show configuration labels, help text, and the preparation screen in English, Latvian, or Russian. English is the fallback.

# 0.1.5

- Enter only an MQTT username and password to use the Green's local Mosquitto broker. The app supplies the host, port, TLS setting, and default topic.
- Keep hourly updates when the local MQTT login is blank. Installations with a custom broker host keep their saved connection settings.

# 0.1.4

- Add optional MQTT notifications to fetch new private documentation after a successful GitHub build.
- Check GitHub on startup and broker reconnect in notification mode, and keep the saved copy if an update fails.
- Use the existing automatic hourly schedule when no notification broker is configured.

# 0.1.3

- Follow the active user's Home Assistant language: English, Latvian or Russian when the private website contains that translation.
- Keep readers on the same article when the Home Assistant language changes; use English when a language or page is unavailable.
- Read only the surrounding page's language attribute, without Home Assistant API access or a translation service.
- Translate the sun/moon and Auto button labels to match the documentation language.

# 0.1.2

- Use the supplied PICHE brand image as the app icon and information-page logo.
- Match documentation colours and fonts to the surrounding Home Assistant interface, including light and dark modes.
- Use system light/dark colours when the Home Assistant frame is unavailable.
- Add a sun/moon button, remember the selected mode in this browser, and offer Auto to follow Home Assistant again.
- Preserve original screenshot colours and the existing search behavior.

# 0.1.1

- Fix HTTP 415 on GitHub artifact downloads by requesting the API's JSON media type before following its ZIP download redirect.
- Keep authentication restricted to the GitHub API when following download redirects.

# 0.1.0

- First pilot version with Home Assistant Ingress and sidebar access.
- Private GitHub artifact downloads, hourly checks, and persistent offline copy.
- Checksum and build version validation before activation.
