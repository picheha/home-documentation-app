"""Install the Documentation sidebar helper into Home Assistant's frontend."""

import argparse
from dataclasses import dataclass
from io import StringIO
import os
from pathlib import Path
import stat
import sys
from tempfile import NamedTemporaryFile

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq, TaggedScalar
from ruamel.yaml.error import YAMLError
from ruamel.yaml.util import load_yaml_guess_indent


MODULE_NAME = "piche-documentation-sidebar.js"
MODULE_URL = f"/local/{MODULE_NAME}"
BACKUP_DIRECTORY = ".documentation-sidebar-backup"
INSTALL_MARKER = "sidebar-translation-v1"


class InstallError(Exception):
    """Configuration needs manual review before it can be changed."""


@dataclass
class ConfigDocument:
    path: Path
    original: bytes
    yaml: YAML
    value: object

    @classmethod
    def read(cls, path):
        original = path.read_bytes()
        yaml = YAML()
        yaml.preserve_quotes = True
        try:
            source = original.decode("utf-8-sig")
            value, indent, sequence_offset = load_yaml_guess_indent(source, yaml=yaml)
        except (UnicodeError, YAMLError):
            # A parser exception can quote YAML values from the configuration.
            raise InstallError(f"Cannot read {path.name} as UTF-8 YAML.") from None
        yaml.indent(
            mapping=2,
            sequence=indent or 4,
            offset=sequence_offset if sequence_offset is not None else 2,
        )
        yaml.line_break = "\r\n" if b"\r\n" in original else "\n"
        return cls(path, original, yaml, value)

    def render(self):
        output = StringIO()
        try:
            self.yaml.dump(self.value, output)
        except YAMLError:
            raise InstallError(f"Cannot write {self.path.name} as YAML.") from None
        encoding = "utf-8-sig" if self.original.startswith(b"\xef\xbb\xbf") else "utf-8"
        return output.getvalue().encode(encoding)


def checked_path(root, path):
    absolute = Path(os.path.abspath(path))
    if not absolute.is_relative_to(root) or absolute.resolve() != absolute:
        raise InstallError(f"Cannot use a linked path or a path outside Home Assistant's configuration: {path.name}.")
    return absolute


def follow_include(root, document, value):
    if not isinstance(value, TaggedScalar) or value.tag.value != "!include":
        return document, value
    relative = Path(value.value)
    if relative.is_absolute():
        raise InstallError("Use a relative path for the frontend include.")
    included = ConfigDocument.read(checked_path(root, document.path.parent / relative))
    return included, included.value


def editable_mapping(value, field):
    if not isinstance(value, CommentedMap) or value.tag.value or value.yaml_anchor():
        raise InstallError(f"{field} must be a plain YAML mapping or a direct file include.")
    return value


def mapping_property(value, key):
    if key in value and key not in dict(value.non_merged_items()):
        raise InstallError(f"{key} comes from a YAML merge and needs manual review.")
    return value.get(key)


def configure_module(root):
    document = ConfigDocument.read(checked_path(root, root / "configuration.yaml"))
    config = editable_mapping(document.value, "configuration.yaml")
    frontend_option = mapping_property(config, "frontend")
    document, frontend = follow_include(root, document, frontend_option)
    if frontend is None:
        frontend = CommentedMap()
        if frontend_option is None:
            config["frontend"] = frontend
        else:
            document.value = frontend
    frontend = editable_mapping(frontend, "frontend")

    module_option = mapping_property(frontend, "extra_module_url")
    document, modules = follow_include(root, document, module_option)
    if modules is None:
        modules = CommentedSeq()
        if module_option is None:
            frontend["extra_module_url"] = modules
        else:
            document.value = modules
    if not isinstance(modules, CommentedSeq) or modules.tag.value or modules.yaml_anchor():
        raise InstallError("frontend.extra_module_url must be a plain YAML list or a direct file include.")
    if MODULE_URL in modules:
        return None
    modules.append(MODULE_URL)
    return document


def atomic_write(path, content, mode):
    with NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        try:
            handle.write(content)
        except BaseException:
            handle.close()
            temporary.unlink(missing_ok=True)
            raise
    try:
        temporary.chmod(mode)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def backup(root, path, original):
    destination = checked_path(root, root / BACKUP_DIRECTORY / path.relative_to(root))
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        atomic_write(destination, original, 0o600)


def install_sidebar(config_dir, module_path):
    """Return (configuration_changed, module_changed) without restarting Core."""
    root = Path(config_dir).resolve(strict=True)
    module = Path(module_path).read_bytes()
    if not module:
        raise InstallError("The bundled sidebar module is empty.")

    document = configure_module(root)
    destination = checked_path(root, root / "www" / MODULE_NAME)
    original_module = destination.read_bytes() if destination.exists() else None
    module_changed = module != original_module
    if document:
        updated = document.render()
        if document.path.read_bytes() != document.original:
            raise InstallError(f"{document.path.name} changed while being read. Run the installer again.")
        backup(root, document.path, document.original)
    if module_changed:
        if original_module is not None:
            backup(root, destination, original_module)
        destination.parent.mkdir(exist_ok=True)
        atomic_write(destination, module, 0o644)
    if document:
        if document.path.read_bytes() != document.original:
            raise InstallError(f"{document.path.name} changed while being read. Run the installer again.")
        atomic_write(document.path, updated, stat.S_IMODE(document.path.stat().st_mode))
    return document is not None, module_changed


def setup_sidebar(data_dir, logger, config_dir=Path("/homeassistant"), module_path=Path(__file__).with_name(MODULE_NAME)):
    """Run on the first app start after the update, before starting the guide server."""
    marker = data_dir / INSTALL_MARKER
    if marker.exists():
        return
    try:
        config_changed, module_changed = install_sidebar(config_dir, module_path)
        marker.touch()
    except (InstallError, OSError) as error:
        logger.warning("Sidebar translation setup skipped. %s", error)
        return
    if config_changed:
        logger.info("Sidebar translation is configured and will activate on the next Home Assistant Core restart.")
    elif module_changed:
        logger.info("Sidebar translation module installed. Reload Home Assistant to use it.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config-dir", type=Path, default=Path("/homeassistant"))
    parser.add_argument("--module", type=Path, default=Path(__file__).with_name(MODULE_NAME))
    arguments = parser.parse_args()
    try:
        config_changed, module_changed = install_sidebar(arguments.config_dir, arguments.module)
    except (InstallError, OSError) as error:
        print(f"Sidebar setup stopped. {error}", file=sys.stderr)
        return 1
    if config_changed:
        print("Sidebar helper configured. Validate the configuration and restart Home Assistant Core to enable it.")
    elif module_changed:
        print("Sidebar helper copied. Refresh Home Assistant to load the new module.")
    else:
        print("Sidebar helper is already installed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
