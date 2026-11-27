from pathlib import Path
from shutil import rmtree
import unittest
from unittest.mock import Mock
from uuid import uuid4

from ruamel.yaml import YAML

from documentation.sidebar_install import (
    BACKUP_DIRECTORY,
    INSTALL_MARKER,
    MODULE_NAME,
    MODULE_URL,
    InstallError,
    install_sidebar,
    setup_sidebar,
)


class SidebarInstallerTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).parent.resolve() / f"sidebar-test-{uuid4().hex}"
        self.root.mkdir()
        self.addCleanup(rmtree, self.root)
        self.config = self.root / "configuration.yaml"
        self.source = self.root / "bundled.js"
        self.source.write_bytes(b"// sidebar helper\n")
        self.destination = self.root / "www" / MODULE_NAME

    def install(self, original):
        self.config.write_bytes(original)
        return install_sidebar(self.root, self.source)

    def test_merge_preserves_configuration_and_is_idempotent(self):
        original = (
            b"# Existing settings\n"
            b"default_config:\n"
            b"frontend:\n"
            b"  themes: !include_dir_merge_named themes  # keep the custom theme\n"
            b"  extra_module_url:\n"
            b"    - '/local/existing.js'  # keep the module\n"
            b"automation: !include automations.yaml\n"
            b"http:\n"
            b"  ssl_key: !secret tls_key\n"
        )
        self.assertEqual(self.install(original), (True, True))
        updated = self.config.read_bytes()
        self.assertIn(b"'/local/existing.js'  # keep the module", updated)
        self.assertIn(b"themes: !include_dir_merge_named themes  # keep the custom theme", updated)
        self.assertIn(b"automation: !include automations.yaml", updated)
        self.assertIn(b"!secret tls_key", updated)
        self.assertEqual(YAML().load(updated)["frontend"]["extra_module_url"], ["/local/existing.js", MODULE_URL])
        self.assertEqual((self.root / BACKUP_DIRECTORY / self.config.name).read_bytes(), original)
        self.assertEqual(self.destination.read_bytes(), self.source.read_bytes())

        self.assertEqual(install_sidebar(self.root, self.source), (False, False))
        self.assertEqual(self.config.read_bytes(), updated)

    def test_adds_frontend_to_standard_configuration(self):
        self.assertEqual(self.install(b"default_config:\r\n"), (True, True))
        result = self.config.read_bytes()
        self.assertIn(b"frontend:\r\n", result)
        self.assertEqual(YAML().load(result)["frontend"]["extra_module_url"], [MODULE_URL])

    def test_updates_included_module_list_only(self):
        frontend_config = self.root / "frontend.yaml"
        frontend_config.write_bytes(b"extra_module_url: !include modules.yaml\n")
        modules = self.root / "modules.yaml"
        original_modules = b"- /local/existing.js\n"
        modules.write_bytes(original_modules)
        original = b"frontend: !include frontend.yaml\n"

        self.assertEqual(self.install(original), (True, True))
        self.assertEqual(self.config.read_bytes(), original)
        self.assertEqual(frontend_config.read_bytes(), b"extra_module_url: !include modules.yaml\n")
        self.assertEqual(YAML().load(modules), ["/local/existing.js", MODULE_URL])
        self.assertEqual((self.root / BACKUP_DIRECTORY / "modules.yaml").read_bytes(), original_modules)

    def test_rejects_unsupported_input_before_installing(self):
        for original in (
            b"",
            b"frontend: !include_dir_merge_named frontend\n",
            b"frontend: {extra_module_url: '/local/file.js'}\n",
            b"frontend: !include ../frontend.yaml\n",
            b"frontend: &settings {extra_module_url: []}\nother: *settings\n",
            b"frontend:\n  <<: {extra_module_url: []}\n",
            b"frontend:\n  themes: [unterminated\n",
        ):
            with self.subTest(original=original):
                with self.assertRaises(InstallError):
                    self.install(original)
                self.assertEqual(self.config.read_bytes(), original)
                self.assertFalse(self.destination.exists())

    def test_update_preserves_an_existing_module_for_rollback(self):
        original = f"frontend: {{extra_module_url: [{MODULE_URL}]}}\n".encode()
        self.destination.parent.mkdir()
        self.destination.write_bytes(b"// former version\n")

        self.assertEqual(self.install(original), (False, True))
        self.assertEqual(self.config.read_bytes(), original)
        self.assertEqual((self.root / BACKUP_DIRECTORY / "www" / MODULE_NAME).read_bytes(), b"// former version\n")

    def test_app_start_installs_only_once(self):
        self.config.write_bytes(b"default_config:\n")
        data_dir = self.root / "data"
        data_dir.mkdir()
        logger = Mock()
        setup_sidebar(data_dir, logger, self.root, self.source)
        self.assertTrue((data_dir / INSTALL_MARKER).is_file())
        self.assertEqual(self.destination.read_bytes(), self.source.read_bytes())
        logger.info.assert_called_once()
        logger.warning.assert_not_called()

        original = self.config.read_bytes()
        self.source.write_bytes(b"// a different module\n")
        setup_sidebar(data_dir, logger, self.root, self.source)
        self.assertEqual(self.config.read_bytes(), original)
        self.assertEqual(self.destination.read_bytes(), b"// sidebar helper\n")

    def test_app_start_skips_unsupported_yaml_and_can_retry(self):
        original = b"frontend: !include_dir_merge_named frontend\n"
        self.config.write_bytes(original)
        data_dir = self.root / "data"
        data_dir.mkdir()
        logger = Mock()
        setup_sidebar(data_dir, logger, self.root, self.source)
        self.assertEqual(self.config.read_bytes(), original)
        self.assertFalse((data_dir / INSTALL_MARKER).exists())
        self.assertFalse(self.destination.exists())
        logger.warning.assert_called_once()

        self.config.write_bytes(b"frontend:\n")
        setup_sidebar(data_dir, logger, self.root, self.source)
        self.assertTrue((data_dir / INSTALL_MARKER).is_file())


if __name__ == "__main__":
    unittest.main()
