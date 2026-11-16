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
