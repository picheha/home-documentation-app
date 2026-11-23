import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import zipfile

MODULE = Path(__file__).resolve().parents[1] / "documentation/app.py"
spec = importlib.util.spec_from_file_location("documentation_app", MODULE)
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)

RUN = {"id": 42, "head_sha": "a" * 40}


def website_zip(extra=None, version=None):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("index.html", "<h1>Private documentation</h1>")
        archive.writestr("search/search_index.json", json.dumps({"docs": [{"text": "rename a Zigbee light"}]}))
        archive.writestr("version.json", json.dumps(version or {"commit": RUN["head_sha"], "run_id": "42"}))
        archive.writestr("images/example.png", b"example image")
        for name, content in (extra or {}).items():
            archive.writestr(name, content)
    return stream.getvalue()


def checksum(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()


class FakeGitHub:
    def __init__(self, data, identifier=100, digest=None):
        self.data = data
        self.downloads = 0
        self.artifact = {"id": identifier, "digest": digest or checksum(data), "size_in_bytes": len(data)}

    def latest(self, _active_artifact_id=None):
        return self.artifact, RUN

    def api(self, suffix, binary=False):
        self.downloads += 1
        return self.data


class Response(io.BytesIO):
    pass


class AutomaticSyncTests(unittest.TestCase):
    def test_configuration_and_translations_only_offer_github_settings(self):
        app_dir = MODULE.parent
        expected = {"repository", "github_token"}
        config = json.loads((app_dir / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(set(config["schema"]), expected)
        self.assertEqual(set(config["options"]), expected)
        for language in ("en", "lv", "ru"):
            path = app_dir / "translations" / f"{language}.json"
            labels = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(set(labels["configuration"]), expected)

    def test_checks_repeat_on_schedule_with_or_without_legacy_options(self):
        previous_settings = {"mqtt_host": "broker.example", "mqtt_username": "old-user", "mqtt_password": "old-test-password"}
        for legacy_options in ({}, previous_settings):
            with self.subTest(legacy_options_present=bool(legacy_options)), tempfile.TemporaryDirectory() as folder:
                options = {"repository": "example/docs", "github_token": "test-token"} | legacy_options
                (Path(folder) / "options.json").write_text(json.dumps(options), encoding="utf-8")
                website = Mock(data_dir=Path(folder))
                stop = threading.Event()
                waits = []

                def wait(delay):
                    waits.append(delay)
                    if len(waits) == 2:
                        stop.set()

                with patch.object(stop, "wait", side_effect=wait):
                    app.update_loop(website, stop)
                self.assertEqual(website.sync.call_count, 2)
                self.assertTrue(all(240 <= delay <= 300 for delay in waits))

    def test_rate_limit_delays_the_next_check(self):
        website = Mock()
        website.sync.side_effect = app.GitHubRateLimit(600)
        with patch.object(app.random, "randint", side_effect=[270, 24]):
            self.assertEqual(app.sync_and_get_delay(website, Mock()), 624)


class UpdaterTests(unittest.TestCase):
    def test_safe_package_installs_and_cache_survives_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            website = app.Website(folder)
            github = FakeGitHub(website_zip())
            self.assertTrue(website.sync(github))
            self.assertTrue((website.active / "index.html").is_file())
            restored = app.Website(folder)
            self.assertEqual(restored.artifact_id, "100")
            self.assertFalse(restored.sync(github))
            self.assertEqual(github.downloads, 1)

    def test_corrupt_update_leaves_old_site_and_marker(self):
        with tempfile.TemporaryDirectory() as folder:
            website = app.Website(folder)
            website.sync(FakeGitHub(website_zip()))
            with self.assertRaises(app.UpdateError):
                website.sync(FakeGitHub(website_zip(), 101, "sha256:" + "0" * 64))
            self.assertEqual(website.artifact_id, "100")
            self.assertEqual(app.Website(folder).artifact_id, "100")
            self.assertEqual(list(Path(folder).glob("staging-*")), [])

    def test_commit_and_run_mismatch_rejected(self):
        data = website_zip(version={"commit": "b" * 40, "run_id": "99"})
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(app.UpdateError):
                app.unpack_website(data, folder, checksum(data), RUN)

    def test_archive_path_escape_rejected_before_extraction(self):
        paths = ["../outside.txt", "/outside.txt", "C:/outside.txt"]
        # ZipInfo normalizes backslashes on Windows. The Linux CI also tests the
        # raw backslash path that can actually reach the Home Assistant runtime.
        if os.name != "nt":
            paths.append("images\\outside.txt")
        for path in paths:
            with self.subTest(path=path), tempfile.TemporaryDirectory() as folder:
                data = website_zip({path: "unsafe"})
                with self.assertRaises(app.UpdateError):
                    app.unpack_website(data, folder, checksum(data), RUN)
                self.assertEqual(list(Path(folder).iterdir()), [])

    def test_symlink_rejected(self):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as archive:
            entry = zipfile.ZipInfo("link")
            entry.create_system = 3
            entry.external_attr = 0o120777 << 16
            archive.writestr(entry, "../secret")
        data = stream.getvalue()
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(app.UpdateError):
                app.unpack_website(data, folder, checksum(data), RUN)

    def test_missing_search_index_rejected(self):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as archive:
            archive.writestr("index.html", "website")
        data = stream.getvalue()
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(FileNotFoundError):
                app.unpack_website(data, folder, checksum(data), RUN)

    def test_oversized_archive_rejected(self):
        data = website_zip()
        with tempfile.TemporaryDirectory() as folder, patch.object(app, "MAX_EXPANDED", 10):
            with self.assertRaises(app.UpdateError):
                app.unpack_website(data, folder, checksum(data), RUN)

    def test_missing_checksum_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(app.UpdateError):
                app.unpack_website(website_zip(), folder, None, RUN)


class GitHubTests(unittest.TestCase):
    def test_repository_cannot_be_a_url_or_embed_credentials(self):
        for value in ("https://github.com/owner/repo", "token@github.com/owner/repo", "owner/repo/../other"):
            with self.subTest(value=value), self.assertRaises(app.UpdateError):
                app.GitHub(value, "test-token")

    def test_redirect_download_never_receives_token(self):
        client = app.GitHub("owner/repository", "test-token-secret")
        captured = []

        class API:
            def open(self, request, timeout):
                captured.append(request)
                # Model GitHub's artifact endpoint: an octet-stream API Accept
                # header produces HTTP 415, rather than the ZIP redirect.
                if request.get_header("Accept") != "application/vnd.github+json":
                    raise HTTPError(request.full_url, 415, "Unsupported Media Type", {}, None)
                raise HTTPError(request.full_url, 302, "Found", {"Location": "https://example.blob.core.windows.net/artifact?signature=test"}, None)

        class Storage:
            def open(self, request, timeout):
                captured.append(request)
                return Response(b"zip bytes")

        client.api_opener, client.download_opener = API(), Storage()
        self.assertEqual(client.api("/actions/artifacts/1/zip", binary=True), b"zip bytes")
        self.assertEqual(captured[0].get_header("Authorization"), "Bearer test-token-secret")
        self.assertIsNone(captured[1].get_header("Authorization"))

    def test_rate_limit_uses_github_retry_after_or_reset(self):
        cases = [
            (429, {"Retry-After": "600"}, 600),
            (403, {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1600"}, 601),
        ]
        for code, headers, delay in cases:
            with self.subTest(code=code):
                client = app.GitHub("owner/repository", "test-token")
                client.api_opener = Mock()
                client.api_opener.open.side_effect = HTTPError("https://api.github.com", code, "Limited", headers, None)
                with patch.object(app, "time", return_value=1000), self.assertRaises(app.GitHubRateLimit) as limit:
                    client.api("/actions/runs")
                self.assertEqual(limit.exception.delay, delay)

    def test_unsafe_download_redirects_rejected(self):
        client = app.GitHub("owner/repository", "test-token")
        for location in ("http://example.blob.core.windows.net/file", "https://evil.example/file", "https://api.github.com.evil.example/file", "https://user:pass@example.blob.core.windows.net/file"):
            with self.subTest(location=location), self.assertRaises(app.UpdateError):
                client.download(location)

    def test_pull_request_build_is_not_trusted(self):
        client = app.GitHub("owner/repository", "test-token")
        client.api = lambda suffix, **kwargs: {"workflow_runs": [{"head_branch": "main", "status": "completed", "conclusion": "success", "event": "pull_request", "path": ".github/workflows/build-docs.yml", "head_repository": {"full_name": "owner/repository"}}]}
        with self.assertRaises(app.UpdateError):
            client.latest()

    def test_successful_build_selects_expected_artifact(self):
        client = app.GitHub("owner/repository", "test-token")
        run = dict(RUN, head_branch="main", status="completed", conclusion="success", event="push", path=".github/workflows/build-docs.yml", head_repository={"full_name": "owner/repository"})
        def api(suffix, **kwargs):
            if "/workflows/" in suffix:
                return {"workflow_runs": [run]}
            return {"artifacts": [{"id": 1, "name": "unrelated", "expired": False}, {"id": 2, "name": "documentation-html", "expired": False}]}
        client.api = api
        artifact, selected = client.latest()
        self.assertEqual(artifact["id"], 2)
        self.assertEqual(selected, run)

    def test_unchanged_run_metadata_skips_artifact_lookup_only_after_activation(self):
        client = app.GitHub("owner/repository", "test-token")
        run = dict(RUN, head_branch="main", status="completed", conclusion="success", event="push",
                   path=".github/workflows/build-docs.yml", head_repository={"full_name": "owner/repository"},
                   run_attempt=1)
        artifact = {"id": 100, "name": "documentation-html"}
        artifact_requests = 0

        def open_request(request, timeout):
            nonlocal artifact_requests
            if "/workflows/" in request.full_url:
                etag = f'"attempt-{run["run_attempt"]}"'
                if request.get_header("If-none-match") == etag:
                    raise HTTPError(request.full_url, 304, "Not Modified", {}, None)
                result = Response(json.dumps({"workflow_runs": [run]}).encode())
                result.headers = {"ETag": etag}
                return result
            artifact_requests += 1
            return Response(json.dumps({"artifacts": [artifact]}).encode())

        client.api_opener = SimpleNamespace(open=open_request)
        self.assertEqual(client.latest()[0]["id"], 100)
        self.assertEqual(client.latest()[0]["id"], 100)  # A failed install can retry.
        self.assertEqual(client.latest("100")[0]["id"], 100)
        self.assertEqual(artifact_requests, 2)

        run["run_attempt"] = 2
        artifact["id"] = 101
        self.assertEqual(client.latest("100")[0]["id"], 101)
        self.assertEqual(artifact_requests, 3)


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.website = app.Website(self.folder.name)
        # This file must never be served, even before the first website download.
        (Path(self.folder.name) / "options.json").write_text('{"github_token":"secret"}', encoding="utf-8")
        self.server = app.ThreadingHTTPServer(("127.0.0.1", 0), app.handler_for(self.website))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = "http://127.0.0.1:" + str(self.server.server_port)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.folder.cleanup()

    def test_direct_access_is_forbidden(self):
        with self.assertRaises(HTTPError) as error:
            urlopen(self.url + "/", timeout=3)
        self.assertEqual(error.exception.code, 403)
        error.exception.close()

    def test_initial_page_does_not_expose_options(self):
        with patch.object(app, "SUPERVISOR_IP", "127.0.0.1"):
            with self.assertRaises(HTTPError) as error:
                urlopen(self.url + "/options.json", timeout=3)
            self.assertEqual(error.exception.code, 503)
            self.assertNotIn(b"secret", error.exception.read())
            error.exception.close()

    def test_ingress_can_read_website_but_not_app_configuration(self):
        self.website.sync(FakeGitHub(website_zip()))
        with patch.object(app, "SUPERVISOR_IP", "127.0.0.1"):
            with urlopen(self.url + "/", timeout=3) as response:
                self.assertIn(b"Private documentation", response.read())
            with urlopen(self.url + "/search/search_index.json", timeout=3) as response:
                self.assertIn(b"rename", response.read())
            with self.assertRaises(HTTPError) as error:
                urlopen(self.url + "/../options.json", timeout=3)
            self.assertEqual(error.exception.code, 404)
            error.exception.close()

    def test_theme_assets_are_private_and_served_before_first_download(self):
        path = "/__documentation_theme__/theme.js"
        with self.assertRaises(HTTPError) as error:
            urlopen(self.url + path, timeout=3)
        self.assertEqual(error.exception.code, 403)
        error.exception.close()
        with patch.object(app, "SUPERVISOR_IP", "127.0.0.1"):
            with urlopen(self.url + path, timeout=3) as response:
                self.assertIn("javascript", response.headers["Content-Type"])
                self.assertIn(b"window.frameElement", response.read())
            with urlopen(self.url + "/__documentation_theme__/theme.css", timeout=3) as response:
                self.assertIn(b"--doc-background", response.read())

    def test_html_is_themed_and_head_has_same_length_as_get(self):
        self.website.sync(FakeGitHub(website_zip()))
        with patch.object(app, "SUPERVISOR_IP", "127.0.0.1"):
            with urlopen(self.url + "/index.html", timeout=3) as response:
                data = response.read()
                self.assertIn(b'data-ha-doc-theme', data)
                self.assertIn(b'__documentation_theme__/theme.css', data)
                self.assertIn(b'__documentation_theme__/theme.js', data)
            with urlopen(Request(self.url + "/index.html", method="HEAD"), timeout=3) as response:
                self.assertEqual(int(response.headers["Content-Length"]), len(data))
                self.assertEqual(response.read(), b"")

    def test_nested_html_uses_ingress_safe_relative_theme_paths(self):
        data = website_zip({"guides/nested/index.html": "<html><head></head><body>Guide</body></html>"})
        self.website.sync(FakeGitHub(data))
        with patch.object(app, "SUPERVISOR_IP", "127.0.0.1"):
            with urlopen(self.url + "/guides/nested/", timeout=3) as response:
                html = response.read()
                self.assertIn(b'../../__documentation_theme__/theme.css', html)
                self.assertIn(b'</script></head>', html)

    def test_screenshot_bytes_remain_unchanged(self):
        self.website.sync(FakeGitHub(website_zip()))
        with patch.object(app, "SUPERVISOR_IP", "127.0.0.1"):
            with urlopen(self.url + "/images/example.png", timeout=3) as response:
                self.assertEqual(response.read(), b"example image")

    def test_language_targets_use_existing_pages_and_ingress_safe_relative_paths(self):
        data = website_zip({"lv/index.html": "<html><head></head><body>LV</body></html>",
                            "ru/index.html": "<html><head></head><body>RU</body></html>"})
        self.website.sync(FakeGitHub(data))
        with patch.object(app, "SUPERVISOR_IP", "127.0.0.1"):
            with urlopen(self.url + "/lv/index.html", timeout=3) as response:
                document = response.read().decode()
                self.assertIn('data-doc-language="lv"', document)
                self.assertIn('../__documentation_theme__/language.js', document)
                import html
                import re
                targets = json.loads(html.unescape(re.search(r'data-doc-targets="([^"]+)"', document)[1]))
                self.assertEqual(targets, {"en": "../index.html", "lv": "index.html", "ru": "../ru/index.html"})
            with urlopen(self.url + "/__documentation_theme__/language.js", timeout=3) as response:
                self.assertIn(b"document.documentElement.lang", response.read())

    def test_old_package_offers_only_english_language_target(self):
        self.website.sync(FakeGitHub(website_zip()))
        with patch.object(app, "SUPERVISOR_IP", "127.0.0.1"):
            with urlopen(self.url + "/index.html", timeout=3) as response:
                document = response.read()
                self.assertIn(b'&quot;en&quot;: &quot;index.html&quot;', document)
                self.assertNotIn(b'&quot;lv&quot;', document)


if __name__ == "__main__":
    unittest.main()
