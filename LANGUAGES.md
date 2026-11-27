# Language support

Documentation supports English, Latvian (Latviešu), and Russian
(Русский). Choose **Language** in your Home Assistant profile. The app's
configuration labels, field descriptions, and preparation screen follow that
setting. English is the fallback. The documentation website uses each guide's
available translations in the private documentation package.

Documentation 0.1.10 installs a local frontend module on the app's first
start. After the next Home Assistant Core restart, the sidebar label follows
each profile's language, even when the guide is closed.

| Profile language | Sidebar |
| --- | --- |
| English | Documentation |
| Latvian | Dokumentācija |
| Russian | Документация |

The update gives the app write access to Home Assistant's configuration
folder to copy the module and register it in the existing frontend settings.
The installer saves a copy
of the edited YAML under `.documentation-sidebar-backup` in the configuration
folder. If the YAML layout needs manual review, the app logs that the sidebar
setup was skipped and starts serving the guides.

[Home Assistant app translation files](https://contributors.home-assistant.io/apps/reference/files/#translation-file) · [Home Assistant sidebar title setting](https://contributors.home-assistant.io/apps/reference/configuration/#ingress)
