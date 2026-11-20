# Documentation sidebar language

The Documentation entry follows each user's Home Assistant language. It shows
**Documentation** in English, **Dokumentācija** in Latvian, and
**Документация** in Russian. Other languages use English.

Enable the module once on each Home Assistant installation:

1. Download [piche-documentation-sidebar.js](piche-documentation-sidebar.js)
   using GitHub's **Download raw file** button. Copy it to Home Assistant as
   `/config/www/piche-documentation-sidebar.js`. Create `www` if needed.
2. Add the following to `configuration.yaml`. If there is already a `frontend`
   or `extra_module_url` section, add the URL to that existing section.

   ```yaml
   frontend:
     extra_module_url:
       - /local/piche-documentation-sidebar.js
   ```

3. Restart Home Assistant once and refresh the browser or reopen the Home
   Assistant app. Change **Language** in your Home Assistant profile to check
   the label. Enable **Show in sidebar** for the Documentation app if needed.

This module targets the sidebar entry for the app installed from
`https://github.com/picheha/home-documentation-app`. It uses Home Assistant's
sidebar markup, which may change with frontend updates. The file is loaded
locally and needs no additional credentials. See [Home Assistant’s frontend
module setup](https://www.home-assistant.io/integrations/frontend/#loading-extra-javascript).
