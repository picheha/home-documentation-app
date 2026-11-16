# 0.1.1

- Fix HTTP 415 on GitHub artifact downloads by requesting the API's JSON media type before following its ZIP download redirect.
- Keep authentication restricted to the GitHub API when following download redirects.

# 0.1.0

- First pilot version with Home Assistant Ingress and sidebar access.
- Private GitHub artifact downloads, hourly checks, and persistent offline copy.
- Checksum and build version validation before activation.
